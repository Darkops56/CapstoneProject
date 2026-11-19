"""Configuración de pytest para asegurar la resolución de módulos en monorepo."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT_DIR / "dashboard"

for p in [str(ROOT_DIR), str(DASHBOARD_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)
