"""Compare two versions of the theme declaration by declaration.

    python tools/css_equiv.py OLD.css NEW.css [--dead TOKEN ...]

Both files are minified with build.py, then flattened into one entry per
(at-rule context, single selector, property). For each key the winning value is
kept: !important beats normal, and a later declaration beats an earlier one of
the same importance. @keyframes and @font-face blocks are compared whole.

The report lists keys only in OLD, keys only in NEW and keys whose winning value
changed. With --dead, keys only in OLD whose selector contains one of the given
tokens (outside :not()) are counted as expected removals rather than differences.

This does not see cascade order between *different* selectors, so a move can
still change which rule wins on a real element. The in-browser computed-style
diff covers that.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build import minify  # noqa: E402

OPAQUE = ("@keyframes", "@-webkit-keyframes", "@font-face", "@page")


def split_top(text, sep):
    """Split on sep outside (), [] and quotes."""
    parts, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(text):
        if quote:
            if ch == "\\":
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def block_end(css, i):
    """Index of the } matching the { at css[i]."""
    depth, quote = 0, None
    for j in range(i, len(css)):
        ch = css[j]
        if quote:
            if ch == quote and css[j - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError("unbalanced braces")


def flatten(css, ctx=(), out=None):
    """Yield (ctx, selector, prop, value, important) in source order."""
    out = [] if out is None else out
    i = 0
    while i < len(css):
        brace, semi = css.find("{", i), css.find(";", i)
        if brace == -1 or (semi != -1 and semi < brace and css[i:semi].lstrip().startswith("@")):
            if semi == -1:
                break
            out.append((ctx, css[i:semi].strip(), "@statement", "", False))
            i = semi + 1
            continue
        prelude = css[i:brace].strip()
        end = block_end(css, brace)
        body = css[brace + 1:end]
        if prelude.startswith(OPAQUE):
            out.append((ctx, prelude, "@block", body, False))
        elif prelude.startswith("@"):
            flatten(body, ctx + (prelude,), out)
        else:
            for sel in split_top(prelude, ","):
                for decl in split_top(body, ";"):
                    if ":" not in decl:
                        continue
                    prop, val = decl.split(":", 1)
                    imp = bool(re.search(r"!\s*important\s*$", val))
                    val = re.sub(r"\s*!\s*important\s*$", "", val).strip()
                    out.append((ctx, sel, prop.strip().lower(), val, imp))
        i = end + 1
    return out


def winners(entries):
    win = {}
    for ctx, sel, prop, val, imp in entries:
        key = (ctx, sel, prop)
        if key in win and win[key][1] and not imp:
            continue  # an earlier !important beats a later normal declaration
        win[key] = (val, imp)
    return win


def has_dead(sel, dead):
    positive = re.sub(r":not\((?:[^()]|\([^()]*\))*\)", "", sel)
    return any(re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", positive) for t in dead)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--dead", nargs="*", default=[])
    args = ap.parse_args()
    old = winners(flatten(minify(Path(args.old).read_text(encoding="utf-8"))))
    new = winners(flatten(minify(Path(args.new).read_text(encoding="utf-8"))))

    removed = [k for k in old if k not in new]
    expected = [k for k in removed if has_dead(k[1], args.dead)]
    unexpected = [k for k in removed if not has_dead(k[1], args.dead)]
    added = [k for k in new if k not in old]
    changed = [k for k in old if k in new and old[k] != new[k]]

    print(f"keys: old {len(old)}, new {len(new)}")
    print(f"removed with a --dead token: {len(expected)} "
          f"({len({k[1] for k in expected})} selectors)")
    for title, keys, src in (("REMOVED (unexpected)", unexpected, old), ("ADDED", added, new),
                             ("CHANGED", changed, None)):
        print(f"{title}: {len(keys)}")
        for k in keys[:25]:
            ctx = " > ".join(k[0]) or "-"
            detail = f"{old[k]} -> {new[k]}" if src is None else str(src[k])
            print(f"   [{ctx}] {k[1]} {{ {k[2]} }}  {detail[:120]}")
    sys.exit(1 if (unexpected or added or changed) else 0)


if __name__ == "__main__":
    main()
