"""
fix_py314.py -- Make all .py files compatible with Python 3.14

Changes made:
  - Removes deprecated typing aliases (List, Dict, Set, Tuple, Optional, Union)
    from 'from typing import ...' statements
  - Replaces their usages in code bodies with built-in equivalents:
      list[X]       -> list[X]
      dict[X, Y]    -> dict[X, Y]
      set[X]        -> set[X]
      tuple[X, ...]  -> tuple[X, ...]
      X | None   -> X | None
      X | Y   -> X | Y
  - Adds 'from __future__ import annotations' to each file if missing
    (ensures all annotations are lazily evaluated, same as PEP 563)

Usage:
    python fix_py314.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent

REMOVE_FROM_TYPING = {"List", "Dict", "Set", "Tuple", "Optional", "Union", "Any"}

BODY_FIXES = [
    (r"\bList\[",      "list["),
    (r"\bDict\[",      "dict["),
    (r"\bSet\[",       "set["),
    (r"\bTuple\[",     "tuple["),
    (r"\bUnion\[([^,\]]+),\s*([^\]]+)\]", r"\1 | \2"),
]

def fix_typing_import(match: re.Match) -> str:
    """Remove deprecated typing aliases from a 'from typing import' line."""
    names = [n.strip() for n in match.group(1).split(",")]
    kept = [n for n in names if n not in REMOVE_FROM_TYPING]
    if kept:
        return "from typing import " + ", ".join(kept)
    return ""   # drop the whole import line

def fix_optional(src: str) -> str:
    """Replace X | None with X | None, handling nested types iteratively."""
    for _ in range(8):
        new = re.sub(r"\bOptional\[([^\[\]]+)\]", r"\1 | None", src)
        if new == src:
            break
        src = new
    return src

def ensure_future_annotations(src: str) -> str:
    """Insert 'from __future__ import annotations' near the top if missing."""
    if "from __future__ import annotations" in src:
        return src
    lines = src.split("\n")
    insert_at = 0
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_docstring and (stripped.startswith("#") or stripped == ""):
            insert_at = i + 1
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_docstring:
                in_docstring = False
                insert_at = i + 1
            else:
                in_docstring = True
            continue
        if in_docstring:
            continue
        break
    lines.insert(insert_at, "from __future__ import annotations")
    return "\n".join(lines)

def process_file(path: pathlib.Path) -> bool:
    """Process a single .py file. Returns True if changed."""
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [SKIP] {path.name}: {e}")
        return False

    original = src

    # 1. Fix typing imports
    src = re.sub(r"from typing import ([^\n]+)", fix_typing_import, src)

    # 2. Fix body usages
    for pattern, replacement in BODY_FIXES:
        src = re.sub(pattern, replacement, src)

    # 3. Fix X | None -> X | None
    src = fix_optional(src)

    # 4. Clean up extra blank lines left by dropped imports
    src = re.sub(r"\n{3,}", "\n\n", src)

    # 5. Ensure from __future__ import annotations
    src = ensure_future_annotations(src)

    if src == original:
        return False

    path.write_text(src, encoding="utf-8")
    return True

def main():
    py_files = list(ROOT.rglob("*.py"))
    # Exclude __pycache__ and build dirs
    py_files = [f for f in py_files if "__pycache__" not in str(f)
                and "build" not in str(f) and "GuideSenseApp" not in str(f)]

    changed = []
    errors = []

    for f in sorted(py_files):
        try:
            if process_file(f):
                changed.append(f.relative_to(ROOT))
                print(f"  [FIXED] {f.relative_to(ROOT)}")
            else:
                print(f"  [OK]    {f.relative_to(ROOT)}")
        except Exception as e:
            errors.append((f.name, str(e)))
            print(f"  [ERROR] {f.relative_to(ROOT)}: {e}")

    print(f"\nDone. {len(changed)} files updated, {len(errors)} errors.")
    if errors:
        for name, err in errors:
            print(f"  ERROR: {name}: {err}")

    # Quick syntax check on changed files
    import ast
    print("\nSyntax check on changed files...")
    for f in [ROOT / str(p) for p in changed]:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
            print(f"  [OK] {f.name}")
        except SyntaxError as e:
            print(f"  [SYNTAX ERROR] {f.name}: {e}")

if __name__ == "__main__":
    main()
