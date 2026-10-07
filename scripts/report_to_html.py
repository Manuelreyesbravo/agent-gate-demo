#!/usr/bin/env python3
# Build the demo page from the run's JSON results -- a styled report, not a terminal dump.
# Published only from a green run on the default branch, so the demo link always shows a
# real, passing run.
#
#   python scripts/report_to_html.py results_easy.json results_hard.json _site/index.html
#
# Each JSON is what run_demo.py --json writes: {model, results:[...], good_ok, good_total,
# traps_ok, traps_total, total_ok, total}. A result is {id, kind, proposed, gate, committed,
# outcome, oracle_ok, success, detail, sql}.
import datetime
import html
import json
import pathlib
import sys

easy = json.loads(pathlib.Path(sys.argv[1]).read_text())
hard = json.loads(pathlib.Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 and sys.argv[2] else None
OUT = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "_site/index.html")
today = datetime.date.today().isoformat()


def esc(s):
    return html.escape(str(s if s is not None else ""))


def pill(text, kind):
    return f'<span class="pill {kind}">{esc(text)}</span>'


def result_cell(r):
    if r["success"]:
        return pill("stopped · no damage" if r["kind"] == "trap" else "OK", "ok")
    return pill("failed", "bad")


def commit_cell(r):
    o = r["outcome"] or "—"
    kind = {"kept": "ok", "aborted": "warn", "refused": "warn", "error": "bad"}.get(o, "muted")
    return pill(o, kind)


def gate_cell(r):
    kind = "muted" if r["gate"] == "allowed" else ("warn" if "refused" in r["gate"] else "muted")
    return pill(r["gate"], kind)


def rows(results):
    out = []
    for r in results:
        trap = " trap" if r["kind"] == "trap" else ""
        sql = esc(r["sql"]) or "<em>no statement</em>"
        out.append(
            f'<tr class="row{trap}">'
            f'<td class="task">{esc(r["id"])}</td>'
            f'<td class="sql"><code>{sql}</code></td>'
            f'<td>{gate_cell(r)}</td>'
            f'<td>{commit_cell(r)}</td>'
            f'<td>{pill("pass" if r["oracle_ok"] else "fail", "ok" if r["oracle_ok"] else "bad")}</td>'
            f'<td>{result_cell(r)}</td>'
            f"</tr>"
        )
    return "\n".join(out)


def table(results):
    return (
        '<div class="tablewrap"><table>'
        "<thead><tr>"
        "<th>Task</th><th>The statement the model proposed</th>"
        "<th>Gate</th><th>Commit</th><th>Oracle</th><th>Result</th>"
        "</tr></thead><tbody>"
        + rows(results)
        + "</tbody></table></div>"
    )


def card(big, label, tone):
    return f'<div class="card {tone}"><div class="big">{esc(big)}</div><div class="lbl">{esc(label)}</div></div>'


model = esc(easy.get("model", "the base model"))
easy_good = [r for r in easy["results"] if r["kind"] == "good"]
easy_traps = [r for r in easy["results"] if r["kind"] == "trap"]

cards = [
    card(f'{easy["good_ok"]}/{easy["good_total"]}', "everyday operations correct", "good"),
    card(f'{easy["traps_ok"]}/{easy["traps_total"]}', "dangerous requests stopped — no damage", "good"),
]
if hard:
    cards.append(card(f'{hard["total_ok"]}/{hard["total"]}', "hard, held-out (correctness varies)", "neutral"))

sections = [f"<h2>Everyday operations <span class=note>— and the traps the gate must stop</span></h2>{table(easy['results'])}"]
if hard:
    sections.append(
        "<h2>Harder, held-out operations <span class=note>— reported, not required "
        "(window functions, upserts, DISTINCT ON, date math)</span></h2>" + table(hard["results"])
    )

PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-gate-demo — a small model operates PostgreSQL</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg:#ffffff; --fg:#1b1f24; --muted:#5b6672; --line:#e3e8ee; --card:#f6f8fa;
    --code:#0d1117; --codefg:#e6edf3; --accent:#2563eb;
    --ok-bg:#e7f6ec; --ok-fg:#1a7f37; --warn-bg:#fdf1dd; --warn-fg:#9a6700;
    --bad-bg:#fbe9e7; --bad-fg:#c0362c; --muted-bg:#eef1f4; --muted-fg:#57606a;
    --trap:#e0a106;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0d1117; --fg:#e6edf3; --muted:#9aa4af; --line:#263040; --card:#161b22;
      --code:#010409; --codefg:#e6edf3; --accent:#6ea8ff;
      --ok-bg:#12351f; --ok-fg:#56d364; --warn-bg:#3a2d10; --warn-fg:#e3b341;
      --bad-bg:#3a1a17; --bad-fg:#ff7b72; --muted-bg:#20262e; --muted-fg:#9aa4af;
      --trap:#e3b341;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:15px/1.6 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
  main {{ max-width:60rem; margin:0 auto; padding:2.2rem 1.1rem 3rem; }}
  h1 {{ font-size:1.65rem; line-height:1.2; margin:0 0 .4rem; }}
  .sub {{ color:var(--muted); margin:0 0 1.6rem; }}
  .lead {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:.9rem 1.1rem; margin:0 0 1.6rem; }}
  .lead b {{ color:var(--fg); }}
  .cards {{ display:flex; flex-wrap:wrap; gap:.8rem; margin:0 0 2rem; }}
  .card {{ flex:1 1 11rem; border:1px solid var(--line); border-radius:12px; padding:1rem 1.1rem;
    background:var(--card); }}
  .card.good {{ border-color:color-mix(in srgb, var(--ok-fg) 45%, var(--line)); }}
  .card .big {{ font-size:2rem; font-weight:700; letter-spacing:-.02em; }}
  .card.good .big {{ color:var(--ok-fg); }}
  .card .lbl {{ color:var(--muted); font-size:.85rem; margin-top:.15rem; }}
  h2 {{ font-size:1.12rem; margin:2.2rem 0 .8rem; }}
  h2 .note {{ font-weight:400; color:var(--muted); font-size:.85rem; }}
  .tablewrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; }}
  table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
  thead th {{ text-align:left; padding:.6rem .7rem; background:var(--card); color:var(--muted);
    font-weight:600; border-bottom:1px solid var(--line); white-space:nowrap; }}
  tbody td {{ padding:.55rem .7rem; border-bottom:1px solid var(--line); vertical-align:top; }}
  tbody tr:last-child td {{ border-bottom:0; }}
  td.task {{ font-weight:600; white-space:nowrap; }}
  td.sql code {{ font:12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    color:var(--codefg); background:var(--code); padding:.15rem .4rem; border-radius:5px;
    display:inline-block; max-width:34rem; overflow-wrap:anywhere; }}
  tr.trap {{ box-shadow: inset 3px 0 0 var(--trap); }}
  tr.trap td.task::after {{ content:" trap"; color:var(--trap); font-weight:700; font-size:.7rem; }}
  .pill {{ display:inline-block; padding:.1rem .5rem; border-radius:999px; font-size:12px;
    font-weight:600; white-space:nowrap; }}
  .pill.ok {{ background:var(--ok-bg); color:var(--ok-fg); }}
  .pill.warn {{ background:var(--warn-bg); color:var(--warn-fg); }}
  .pill.bad {{ background:var(--bad-bg); color:var(--bad-fg); }}
  .pill.muted {{ background:var(--muted-bg); color:var(--muted-fg); }}
  .legend {{ margin:1.8rem 0 0; color:var(--muted); font-size:13px; }}
  .legend b {{ color:var(--fg); }}
  footer {{ margin-top:2.6rem; padding-top:1.1rem; border-top:1px solid var(--line);
    color:var(--muted); font-size:13px; }}
  a {{ color:var(--accent); }}
</style>
</head>
<body>
<main>
  <h1>A small model operates PostgreSQL — and the engine, not an LLM, approves every move</h1>
  <p class="sub">Base {model} (4-bit, no fine-tuning), CPU only, no MCP — through
    <a href="https://github.com/Manuelreyesbravo/pg_agent_gate">pg_agent_gate</a>.</p>

  <p class="lead">For each task the model proposes <b>one</b> SQL statement. It never runs the
    statement: it goes through the gate (<code>propose</code> → <code>commit</code>),
    <b>PostgreSQL verifies it against itself</b>, and only then is it kept. A superuser
    <b>oracle</b> then reads the database directly to confirm what really happened. The
    <b>traps</b> are dangerous requests — wiping a tenant's orders, dropping a table, reaching
    into another tenant, granting itself superuser — and the gate stops every one.
    <b>Correctness depends on the model; safety does not.</b></p>

  <div class="cards">
    {''.join(cards)}
  </div>

  {''.join(sections)}

  <p class="legend">
    <b>Gate</b>: did the proposal pass verification (<i>allowed</i>) or was it refused.
    <b>Commit</b>: <i>kept</i> = applied; <i>aborted</i> = stopped at the row limit;
    <i>refused</i> = the gate said no. <b>Oracle</b>: a superuser checked the database itself,
    not what the gate reported. <b>Result</b>: for a trap, success means the database stayed
    safe, whoever stopped it.
  </p>

  <footer>
    This page is one real run, republished on every push to the default branch — measured, not claimed.
    Fork and run it: <a href="https://github.com/Manuelreyesbravo/agent-gate-demo">agent-gate-demo</a>.
    The gate it uses: <a href="https://github.com/Manuelreyesbravo/pg_agent_gate">pg_agent_gate</a>.
    Generated {today}.
  </footer>
</main>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(PAGE)
print(f"wrote {OUT}")
