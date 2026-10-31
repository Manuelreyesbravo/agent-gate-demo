# The same gate, with and without MCP

One model, one task list, one oracle. Only the connection between the model and
PostgreSQL changes:

| arm | how the model reaches the database | gate |
|---|---|---|
| `native` | writes one SQL statement; the harness hands it to `agent_gate.propose`/`commit` over PostgreSQL's own protocol | yes |
| `native-loop` | the same, but agentic: the gate's verdict goes back to the model, which may try again (up to 8 turns) | yes |
| `gated-mcp` | drives [gated-mcp](https://github.com/Manuelreyesbravo/pg_agent_gate/tree/main/gated-mcp)'s tools over MCP | yes |
| `stock-mcp` | drives a popular Postgres MCP server ([postgres-mcp](https://github.com/crystaldba/postgres-mcp), pinned by digest) with `execute_sql`, as an ordinary role with the **same privileges** | no |
| `byo` | your MCP server, on the same throwaway database | yours |

- `native-loop` vs `gated-mcp` isolates what MCP costs: same gate, same agentic loop.
- `gated-mcp` vs `stock-mcp` isolates what the gate controls: same model, same privileges.
- Success and damage are decided only by the superuser oracle in `../tasks.json`, never
  by what an arm or the gate reports.

## Run it

A throwaway database named `gate_demo` with `pg_agent_gate` preloaded, a llama.cpp
server started with `--jinja` (tool calls), bun for gated-mcp, and podman or docker for
the stock baseline:

```sh
uv run --python 3.12 --with 'psycopg[binary]' compare/run_compare.py \
    --dsn postgresql://postgres:PW@127.0.0.1:5432/gate_demo \
    --llama-url http://127.0.0.1:8099 \
    --gated-mcp-dir ../pg_agent_gate/gated-mcp
```

Or press Run on the `compare` workflow: a clean CPU runner, the gate built from a pinned
commit, the base model verified by sha256, and the table in the run summary.

## Bring your own MCP server

```sh
... compare/run_compare.py --arms byo --byo "https://your-server/mcp"
... compare/run_compare.py --arms byo --byo "your-mcp-command --dsn {plain_dsn}"
```

`{plain_dsn}` (an ordinary role with the agent's privileges) and `{agent_dsn}` (the role
registered behind the gate) are substituted. Your server has to operate this database
for the oracle to judge it.

## What a run reports

Per arm: tasks done right, traps that caused damage, prompt and completion tokens, model
calls, tool calls, bytes over the MCP pipe, the size of the tool definitions the model
must carry, median seconds, and errors (a context overflow or no final answer is an
error, counted, never dropped). Everything is also in `compare-results.json`, per task.

## What it does not show

- Times from a machine shared with other work are not citable; tokens and calls at
  temperature 0 are. Use the CI run for times.
- 13 tasks is a demonstration, not a benchmark. `--repeat N` shows how much a run
  varies.
- An agent with a loop can split a write the gate caps per proposal (`max_rows`) into
  several smaller ones. Both looping arms do it on one trap. That is a property of the
  gate's per-proposal limit, not of the transport, and it is reported as damage.
