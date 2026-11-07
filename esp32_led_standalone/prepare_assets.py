#!/usr/bin/env python3
"""Embed panel.html into page.h; run before compiling after a UI change."""
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    html = (root / "panel.html").read_text(encoding="utf-8")
    if ')HTMLPAGE"' in html:
        raise ValueError("HTML contains the C++ raw string delimiter")
    result = 'static const char PAGE[] PROGMEM = R"HTMLPAGE(' + html + ')HTMLPAGE";\n'
    target = root / "page.h"
    if not target.exists() or target.read_text(encoding="utf-8") != result:
        target.write_text(result, encoding="utf-8")
        print("Generated:", target)
    else:
        print("page.h is up to date")

if __name__ == "__main__":
    main()
