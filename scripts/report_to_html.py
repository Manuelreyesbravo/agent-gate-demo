#!/usr/bin/env python3
# Turn the run's report (summary.md) into a single static page for GitHub Pages.
# The page is just the measured report, styled -- it is published only from a green
# run on the default branch, so the demo link always shows a real, passing run.
#
#   python scripts/report_to_html.py            # summary.md -> _site/index.html
import datetime
import pathlib
import sys

import markdown  # pip install markdown

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "summary.md")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "_site/index.html")

body = markdown.markdown(SRC.read_text(), extensions=["fenced_code", "tables"])
today = datetime.date.today().isoformat()

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-gate-demo — a small model operates PostgreSQL</title>
<style>
  :root { color-scheme: light dark; }
  body { max-width: 54rem; margin: 2rem auto; padding: 0 1rem;
         font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, sans-serif; }
  h1 { font-size: 1.5rem; line-height: 1.25; }
  h2 { font-size: 1.1rem; margin-top: 2rem; }
  pre { background: #0d1117; color: #e6edf3; padding: 1rem; border-radius: 8px;
        overflow-x: auto; font-size: 12.5px; line-height: 1.45; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  a { color: #2563eb; }
  .lead { opacity: .8; }
  footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #8884;
           font-size: 13px; opacity: .8; }
</style>
</head>
<body>
__BODY__
<footer>
  This page is one real run, republished on every push to the default branch — measured, not claimed.
  Fork and run it: <a href="https://github.com/Manuelreyesbravo/agent-gate-demo">agent-gate-demo</a>.
  The gate it uses: <a href="https://github.com/Manuelreyesbravo/pg_agent_gate">pg_agent_gate</a>.
  Generated __DATE__.
</footer>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(PAGE.replace("__BODY__", body).replace("__DATE__", today))
print(f"wrote {OUT}")
