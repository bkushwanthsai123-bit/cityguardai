#!/usr/bin/env bash
# Smart City Garbage Detection - local bring-up (macOS Apple Silicon / Linux)
# Creates a venv, installs deps, pulls the Ollama model (if Ollama is present),
# seeds demo data, then launches the FastAPI API and the Streamlit dashboard.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV="${VENV:-.venv}"
LLM_MODEL="${LLM_MODEL:-llama3.2:1b}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

echo "==> Project root: $ROOT_DIR"

# 1. Virtual environment
if [ ! -d "$VENV" ]; then
  echo "==> Creating virtual environment ($VENV)"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip

# 2. Dependencies
echo "==> Installing dependencies"
pip install -r requirements.txt

# 3. Env file
if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
fi

# 4. Ollama model (optional - app degrades to deterministic rules if absent)
if command -v ollama >/dev/null 2>&1; then
  echo "==> Pulling Ollama model: $LLM_MODEL"
  ollama pull "$LLM_MODEL" || echo "WARN: ollama pull failed; LLM layer will fall back to rules."
else
  echo "WARN: 'ollama' not found on PATH. Skipping model pull."
  echo "      Install from https://ollama.com - the app still runs using deterministic rules."
fi

# 5. Seed demo incidents
echo "==> Seeding demo incidents"
python -m app.seed || echo "WARN: seed failed (continuing)."

# 6. Launch API (background) + dashboard (foreground)
echo "==> Starting FastAPI on http://${API_HOST}:${API_PORT} (Swagger at /docs)"
uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" &
API_PID=$!

cleanup() {
  echo "==> Shutting down API (pid $API_PID)"
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the API a moment to warm-load the model
sleep 5

echo "==> Starting Streamlit dashboard on http://localhost:8501"
streamlit run dashboard/app.py
