# Smart City Garbage Detection - developer tasks
# Usage: make <target>

PYTHON ?= python3
VENV   ?= .venv
PY      = $(VENV)/bin/python
PIP     = $(VENV)/bin/pip
HOST   ?= 0.0.0.0
PORT   ?= 8000
LLM_MODEL ?= llama3.1:8b

.DEFAULT_GOAL := help
.PHONY: help venv install prepare train-help serve dashboard seed test eval docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

venv: ## Create the Python virtual environment
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip

install: venv ## Install Python dependencies into the venv
	$(PIP) install -r requirements.txt

prepare: ## Prepare dataset (download/convert) - see ml/prepare_data.py
	$(PY) -m ml.prepare_data

train-help: ## Show training command/help (training runs via ml/train.py)
	@echo "Train YOLOv8 on the garbage dataset:"
	@echo "  $(PY) -m ml.train --data ml/dataset.yaml --model yolov8s.pt --epochs 100 --imgsz 640"
	@echo "Weights are written to ml/weights/best.pt (consumed via MODEL_PATH)."
	@echo "Use yolov8m.pt for higher accuracy at the cost of latency."

serve: ## Run the FastAPI API (Swagger at /docs)
	$(VENV)/bin/uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

dashboard: ## Run the Streamlit dashboard
	$(VENV)/bin/streamlit run dashboard/app.py

seed: ## Insert demo incidents so the dashboard looks alive
	$(PY) -m app.seed

test: ## Run the test suite
	$(VENV)/bin/pytest -q

eval: ## Evaluate the trained model (mAP/precision/recall) - see ml/evaluate.py
	$(PY) -m ml.evaluate --data ml/dataset.yaml --weights ml/weights/best.pt

docker-up: ## Build and start ollama + api + dashboard
	docker compose up --build -d

docker-down: ## Stop and remove the docker stack
	docker compose down
