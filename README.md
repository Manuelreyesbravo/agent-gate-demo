# A small model operates PostgreSQL — and the engine, not an LLM, approves every move

This is a reproducible demonstration: a **small, local, free** language model proposes
operations against a real PostgreSQL database, and **PostgreSQL itself verifies, runs and
records** every one — through [pg_agent_gate](https://github.com/Manuelreyesbravo/pg_agent_gate).
No MCP server, no GPU, no API keys. It runs on a free GitHub Actions runner, and you can
fork this repo and press **Run** to get the same numbers.

The point it makes is not "look how smart the model is". It is the opposite:

> **The guarantee comes from the database, not the model.** Even a plain, un-fine-tuned
> 8B running on CPU does real database work correctly *and* cannot cause damage, because
> every statement it proposes is checked by PostgreSQL before it runs.

## What it measures

Each task is an operational request in plain language. The model proposes **one** SQL
statement; it goes through the gate (`propose` → `commit`); PostgreSQL verifies it against
itself; and a superuser **oracle** then checks whether the goal was actually met — or, for a
trap, whether the database stayed safe. The answer is approved by the code, not claimed.

Measured by the workflow in this repo — **Qwen3-8B (Q4, no fine-tuning)**, CPU only:

| | result |
|---|---|
| Everyday data operations (`tasks.json`) | **10 / 10** correct, verified by PostgreSQL |
| Hard operations — upsert, window, `DISTINCT ON`, `date_trunc`, `CASE`… (`tasks_hard.json`) | **most correct — 6 to 8 of 8**, depending on the model build |
| Dangerous requests (wipe the table, drop it, cross-tenant write, self-grant superuser) | **0 ever cause damage** |

The first and last rows are the point, and they are the ones that do not move. A plain base
model handles everyday operations perfectly and most hard ones; where it gets a hard query
*wrong*, the oracle catches it as wrong — it is never quietly accepted. And **every dangerous
request is turned away, every time, by the database itself** — by a row limit, by DDL being
refused, by row-level security, by a privilege check — whatever the model does.

**Correctness depends on the model; safety does not.** That is the whole argument: you do not
have to trust the model, because PostgreSQL checks it. And the workflow enforces this — it
**fails the build** if any dangerous request ever causes damage. The guarantee is checked on
every run, not asserted in prose.

> We also tried fine-tuning the 8B to beat the base on the hard set (three times, with an
> oracle-verified corpus). It never won — the base Qwen3-8B is already strong at PostgreSQL,
> and the moat is the **gate**, not the model. The experiment lives in `training/` of the
> companion repo; the honest result is why this demo ships the base model.

## Run it

**On GitHub** — fork this repo and run the **demo** workflow (Actions tab → *demo* → *Run
workflow*), or just push. It installs PostgreSQL, builds pg_agent_gate, downloads the model,
and prints the scored report to the run summary.

**Locally** — you need PostgreSQL with pg_agent_gate installed, [llama.cpp](https://github.com/ggml-org/llama.cpp),
and a Qwen3-8B GGUF. Then:

```bash
# a llama.cpp server with the base model, CPU only
llama-server -m Qwen3-8B-Q4_K_M.gguf -ngl 0 --port 8099 &

# the harness: model proposes -> gate verifies -> oracle checks
uv run --with 'psycopg[binary]' python run_demo.py \
    --dsn "host=/path/to/socket port=5432 dbname=gate_demo user=postgres" \
    --tasks tasks_hard.json --model llama --llama-url http://127.0.0.1:8099
```

`--model stub` runs the whole harness with canned SQL (no model needed), to prove the
plumbing in seconds.

## How it works

- **`run_demo.py`** — ~250 lines, `psycopg` + plain HTTP. For each task it asks the model,
  submits the SQL through the gate's verbs, and runs the oracle. No MCP, nothing hidden.
- **`tasks.json` / `tasks_hard.json`** — each task carries its seed, the request, and a SQL
  oracle that proves success (or, for a trap, that no damage occurred).
- **pg_agent_gate** — the extension that makes an agent session able to do nothing but
  propose; PostgreSQL does the rest.

## License

The harness and tasks are under the PostgreSQL License — see [LICENSE](LICENSE).
Copyright 2026 Manuel Reyes Bravo. pg_agent_gate is a separate project with its own license.
