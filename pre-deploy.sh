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

# ── Python: type check (soft gate — warns but does not block) ──
echo ""
echo ">> [Python] Type checking with mypy..."
if ! mypy "$REPO_ROOT" --exclude='(frontend|venv)/' --ignore-missing-imports --explicit-package-bases; then
    echo ""
    echo "   ⚠  mypy found type errors (non-blocking). Fix before tightening this gate."
fi

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
