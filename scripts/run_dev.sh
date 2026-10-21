#!/usr/bin/env bash
# scripts/run_dev.sh — Start ProcessFoundry AI in development mode (FastAPI + Streamlit)
# Usage: bash scripts/run_dev.sh
# Tested on macOS (zsh/bash) and Linux (bash).

set -euo pipefail

echo -e "\033[36mStarting ProcessFoundry AI Development Environment...\033[0m"

# Verify we are in the project root
if [[ ! -f "app/main.py" ]]; then
    echo "Error: run this script from the project root directory." >&2
    exit 1
fi

# Detect python binary
PYTHON=$(command -v python3 || command -v python || true)
if [[ -z "$PYTHON" ]]; then
    echo "Error: python3 not found. Install Python 3.11+ and try again." >&2
    exit 1
fi
echo "  Using Python: $PYTHON ($($PYTHON --version 2>&1))"

# Source .env if it exists
if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    echo "  Loaded environment from .env"
fi

# Start FastAPI backend in the background
echo -e "\033[32m[1/2] Starting FastAPI backend on http://localhost:8000\033[0m"
"$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "  FastAPI PID: $API_PID"

# Wait up to 6 s for the API to be reachable
echo "  Waiting for API to be ready..."
for i in {1..12}; do
    if curl -sf "http://localhost:8000/api/health" >/dev/null 2>&1; then
        echo -e "  \033[32mAPI health: ok\033[0m"
        break
    fi
    sleep 0.5
done

# Start Streamlit frontend in the foreground
echo -e "\033[32m[2/2] Starting Streamlit frontend on http://localhost:8501\033[0m"
trap "echo 'Shutting down...'; kill $API_PID 2>/dev/null || true" EXIT INT TERM
"$PYTHON" -m streamlit run app/ui/streamlit_app.py --server.port 8501 --server.headless true
