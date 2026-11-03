"""Preserve per-header SIMDe copyright/license comments in the binary package."""
from pathlib import Path
import re
import sys


def notices(source):
    blocks = []
    seen = set()
    for path in sorted(source.rglob("*.h")):
        for match in re.finditer(r"/\*[\s\S]*?\*/|(?://[^\n]*(?:\n|$))+", path.read_text(encoding="utf-8")):
            block = match.group()
            if re.search(r"copyright|permission|licen[cs]e|SPDX", block, re.I) and block not in seen:
                seen.add(block)
                blocks.append(path.relative_to(source).as_posix() + "\n" + block)
    if not blocks:
        raise RuntimeError("No SIMDe header notices found")
    return "SIMDe header notices, preserved from pinned upstream source\n\n" + "\n\n".join(blocks) + "\n"


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(notices(Path(sys.argv[1])), encoding="utf-8")
