.PHONY: all install run offline shock quick evaluate explain advise test lint format check report clean

PERSONA ?= motorist
PRED ?= 1.0
CONFIDENCE ?= 0.8
REASON ?= Geopolitical shock

all: install run

install:
	uv sync

run:
	uv run fuelcast run

offline:
	uv run fuelcast run --offline

shock:
	uv run fuelcast run --shock "$(REASON)"

quick:
	uv run fuelcast run --offline --skip-eval --skip-stress

evaluate:
	uv run fuelcast evaluate --offline

explain:
	uv run fuelcast explain

advise:
	uv run fuelcast advise --persona $(PERSONA) --pred $(PRED) --confidence $(CONFIDENCE)

test:
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: format lint test

report:
	cat reports/report.md

clean:
	rm -rf data/fuelcast.db data/model_*.pkl data/raw reports .pytest_cache .ruff_cache
