#!/bin/bash

# Pre-deploy checks: format, lint, and build all code.
# Aborts on first failure (set -e).
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Activate virtualenv if present
if [ -f "$REPO_ROOT/venv/bin/activate" ]; then
    source "$REPO_ROOT/venv/bin/activate"
fi

echo "========================================"
echo "Pre-deploy checks"
echo "========================================"

# ── Python: format ─────────────────────────────────────────
echo ""
echo ">> [Python] Formatting with ruff..."
ruff format "$REPO_ROOT"

# ── Python: lint ───────────────────────────────────────────
echo ""
echo ">> [Python] Linting with ruff..."
ruff check "$REPO_ROOT" --fix

# ── Python: type check (hard gate — blocks deploy on errors) ──
# Per-module overrides in mypy.ini grandfather pre-existing errors; new
# modules are gated strictly by default. Tighten by removing entries from
# mypy.ini, not by re-softening this gate.
echo ""
echo ">> [Python] Type checking with mypy..."
mypy "$REPO_ROOT" --explicit-package-bases

# ── Frontend: lint ─────────────────────────────────────────
echo ""
echo ">> [Frontend] Linting..."
npm run lint --prefix "$REPO_ROOT/frontend"

# ── Frontend: build ────────────────────────────────────────
echo ""
echo ">> [Frontend] Building..."
npm run build --prefix "$REPO_ROOT/frontend"

# ── Done ───────────────────────────────────────────────────
echo ""
echo "========================================"
echo "All pre-deploy checks passed"
echo "========================================"
