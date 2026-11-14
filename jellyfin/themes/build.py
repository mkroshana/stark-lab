"""Build neutralfin.min.css from neutralfin.css.

Usage:
    python build.py                 # writes neutralfin.min.css next to this script
    python build.py --out PATH      # writes the minified CSS to PATH instead

Strings are protected and comments dropped in a single pass, so a quote inside
a comment or a "/*" inside a url() cannot confuse the minifier. Whitespace
before ":" is kept, because in a selector it is a descendant combinator:
".card :hover" and ".card:hover" match different elements.
"""

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "neutralfin.css"
OUT = HERE / "neutralfin.min.css"

# A double- or single-quoted string, or a comment. Strings are kept, comments dropped.
STRING_OR_COMMENT = re.compile(
    r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|/\*[\s\S]*?\*/'
)


def minify(css: str) -> str:
    strings = []

    def protect(match):
        if match.group(1) is None:  # a comment
            return ""
        strings.append(match.group(1))
        return f"___STR_{len(strings) - 1}___"

    out = STRING_OR_COMMENT.sub(protect, css)
    out = re.sub(r"\s+", " ", out)
    # Drop whitespace around { } ; , and after ":" (never before it, see above).
    out = re.sub(r"\s*([{};,])\s*", r"\1", out)
    out = re.sub(r":\s+", ":", out)
    out = out.replace(";}", "}")

    for i, s in enumerate(strings):
        out = out.replace(f"___STR_{i}___", s)
    return out.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    raw = args.src.read_text(encoding="utf-8")
    minified = minify(raw)
    args.out.write_bytes(minified.encode("utf-8"))
    print(f"{args.src.name}: {len(raw):,} -> {len(minified):,} chars, written to {args.out}")


if __name__ == "__main__":
    main()
