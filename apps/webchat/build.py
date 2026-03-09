#!/usr/bin/env python3
"""Build dist/systemx-chat.js — single-file widget bundle.

Injects widget.css as a dynamic <style> tag inside widget.js so callers
only need a single <script> tag with no separate CSS link.

Run::

    python apps/webchat/build.py

Output: apps/webchat/dist/systemx-chat.js
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent


def build() -> None:
    css_text = (ROOT / "widget.css").read_text(encoding="utf-8")
    js_text = (ROOT / "widget.js").read_text(encoding="utf-8")

    # Escape for template literal: backslashes and backticks
    css_escaped = css_text.replace("\\", "\\\\").replace("`", "\\`")

    # Self-contained CSS injector IIFE — guard prevents double-injection if
    # the bundle script is accidentally loaded twice on the same page.
    css_injector = (
        "(function(){\n"
        "  if(document.getElementById('sx-bundle-style'))return;\n"
        "  var s=document.createElement('style');\n"
        "  s.id='sx-bundle-style';\n"
        f"  s.textContent=`{css_escaped}`;\n"
        "  (document.head||document.documentElement).appendChild(s);\n"
        "})();\n"
    )

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)

    output = css_injector + "\n" + js_text
    out_path = dist_dir / "systemx-chat.js"
    out_path.write_text(output, encoding="utf-8")
    print(f"Built: {out_path} ({len(output):,} bytes)")


if __name__ == "__main__":
    build()
