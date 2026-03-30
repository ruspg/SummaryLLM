"""Namespace shim so ``python -m digest_core.cli`` works from the repo root."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)

SOURCE_PACKAGE = (
    Path(__file__).resolve().parent.parent / "digest-core" / "src" / "digest_core"
)
if SOURCE_PACKAGE.exists():
    __path__.append(str(SOURCE_PACKAGE))
