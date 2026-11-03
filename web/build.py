"""Build docs/walkthrough.js (and a local preview page) from web/page.js.

    python web/build.py

The page embeds agent/__init__.py, agent/loop.py and web/driver.py byte for byte and
runs them in the browser with Pyodide. tests/test_web_demo.py fails if the built page
is out of date with those files.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Path inside the browser's Python filesystem -> source file in this repo.
EMBED = {
    "/home/pyodide/agent/__init__.py": "agent/__init__.py",
    "/home/pyodide/agent/loop.py": "agent/loop.py",
    "/home/pyodide/demo_driver.py": "web/driver.py",
}

PREVIEW = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Privacy-Safe AI Assistant: live demo</title>
<style>body{margin:0;background:#05070d}</style>
</head><body>
<div id="ps-walkthrough" style="min-height:600px;background:#05070d"></div>
<script src="walkthrough.js"></script>
</body></html>
"""


def embedded_files() -> dict:
    return {dest: (ROOT / src).read_text() for dest, src in EMBED.items()}


def build() -> str:
    template = (ROOT / "web" / "page.js").read_text()
    assert template.count("__FILES__") == 1
    return template.replace("__FILES__", json.dumps(embedded_files(), indent=None))


def main() -> None:
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    (out / "walkthrough.js").write_text(build())
    (out / "walkthrough.html").write_text(PREVIEW)
    print("Wrote docs/walkthrough.js and docs/walkthrough.html")


if __name__ == "__main__":
    main()
