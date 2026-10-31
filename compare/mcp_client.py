# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
"""A minimal MCP client: stdio and Streamable HTTP, JSON-RPC 2.0.

Only what an agent loop needs -- initialize, tools/list, tools/call -- and it
counts every byte that crosses the pipe in each direction, so the comparison can
report what the protocol itself costs. Any MCP server works: ours (gated-mcp),
a stock Postgres MCP, or one you bring (--arm byo:<url or command>).
"""
import itertools
import json
import subprocess
import urllib.error
import urllib.request

PROTOCOL = "2025-11-25"   # the handshake era most servers still speak
CLIENT = {"name": "gate-compare", "version": "0.1.0"}


class MCPError(Exception):
    pass


class _Client:
    def __init__(self):
        self._ids = itertools.count(1)
        self.bytes_out = 0
        self.bytes_in = 0
        self.rpcs = 0

    def start(self):
        self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                 "clientInfo": CLIENT})
        self._notify("notifications/initialized")
        return self

    def tools(self):
        return self._rpc("tools/list", {}).get("tools", [])

    def call(self, name, arguments):
        """Returns (text, is_error). A protocol error is handed back to the model as
        text, the way an agent framework would, instead of ending the episode."""
        try:
            r = self._rpc("tools/call", {"name": name, "arguments": arguments})
        except MCPError as e:
            return f"error: {e}", True
        text = "\n".join(c.get("text", "") for c in r.get("content", [])
                         if c.get("type") == "text")
        return text, bool(r.get("isError"))

    def _rpc(self, method, params):
        raise NotImplementedError

    def _notify(self, method):
        raise NotImplementedError

    def close(self):
        pass


class StdioClient(_Client):
    """Spawns the server and speaks newline-delimited JSON-RPC on its stdin/stdout."""

    def __init__(self, argv, env=None):
        super().__init__()
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)

    def _send(self, msg):
        line = json.dumps(msg) + "\n"
        self.bytes_out += len(line.encode())
        self.p.stdin.write(line)
        self.p.stdin.flush()

    def _rpc(self, method, params):
        i = next(self._ids)
        self.rpcs += 1
        self._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise MCPError(f"server exited during {method}")
            self.bytes_in += len(line.encode())
            try:
                msg = json.loads(line)
            except ValueError:
                continue          # a server that logs to stdout; not ours to parse
            if msg.get("id") != i:
                continue          # a notification or a log message
            if "error" in msg:
                raise MCPError(msg["error"].get("message", "error"))
            return msg.get("result", {})

    def _notify(self, method):
        self._send({"jsonrpc": "2.0", "method": method})

    def close(self):
        self.p.terminate()
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()


class HttpClient(_Client):
    """Streamable HTTP: one POST per message; the answer is JSON or an SSE stream."""

    def __init__(self, url, token=""):
        super().__init__()
        self.url = url
        self.token = token
        self.session = None

    def _post(self, msg, first=False):
        body = json.dumps(msg).encode()
        self.bytes_out += len(body)
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if not first:
            h["MCP-Protocol-Version"] = PROTOCOL
        if self.session:
            h["Mcp-Session-Id"] = self.session
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=body, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                self.session = r.headers.get("Mcp-Session-Id") or self.session
                ctype = r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            raise MCPError(f"HTTP {e.code}: {e.read()[:200]!r}")
        self.bytes_in += len(raw)
        if not raw.strip():
            return []
        if "text/event-stream" in ctype:
            return [json.loads(l[5:]) for l in raw.decode().splitlines()
                    if l.startswith("data:") and l[5:].strip()]
        m = json.loads(raw)
        return m if isinstance(m, list) else [m]

    def _rpc(self, method, params):
        i = next(self._ids)
        self.rpcs += 1
        for m in self._post({"jsonrpc": "2.0", "id": i, "method": method, "params": params},
                            first=(method == "initialize")):
            if m.get("id") == i:
                if "error" in m:
                    raise MCPError(m["error"].get("message", "error"))
                return m.get("result", {})
        raise MCPError(f"no answer to {method}")

    def _notify(self, method):
        self._post({"jsonrpc": "2.0", "method": method})


def connect(target, env=None, token=""):
    """http(s)://... -> Streamable HTTP; anything else is a command line for stdio."""
    if target.startswith(("http://", "https://")):
        return HttpClient(target, token).start()
    import shlex
    return StdioClient(shlex.split(target), env=env).start()


def as_openai_tools(mcp_tools):
    """MCP tool definitions -> the OpenAI `tools` array a llama.cpp server accepts."""
    return [{"type": "function",
             "function": {"name": t["name"],
                          "description": t.get("description", ""),
                          "parameters": t.get("inputSchema") or {"type": "object",
                                                                 "properties": {}}}}
            for t in mcp_tools]
