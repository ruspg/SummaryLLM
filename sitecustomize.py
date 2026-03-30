"""Allow running ``python -m digest_core.cli`` from the monorepo root."""

from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_SRC = Path(__file__).resolve().parent / "digest-core" / "src"

if PACKAGE_SRC.exists():
    package_src_str = str(PACKAGE_SRC)
    if package_src_str not in sys.path:
        sys.path.insert(0, package_src_str)
