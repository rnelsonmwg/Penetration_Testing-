.PHONY: install run cli test clean

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8088

cli:
	python -m app.cli --help

test:
	pytest -q

clean:
	rm -rf .pytest_cache .khepri_data __pycache__ app/**/__pycache__
