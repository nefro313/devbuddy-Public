# DevBuddy - Python convenience targets
#
#   make install   Create the venv, install Week 0 deps, scaffold .env
#   make run       Run the Week 0 verification script
#   make rag       Add Week 3 (RAG) dependencies
#   make mcp       Add Week 5 (MCP) dependencies
#   make agent     Add Week 6 (Agent) dependencies
#   make clean     Remove the virtual environment
#
# Requires uv (https://docs.astral.sh/uv/). Run all targets from the python/ directory.

.DEFAULT_GOAL := help
.PHONY: help install run verify rag mcp agent clean

help:
	@echo "make install   - create venv, install Week 0 deps, scaffold .env"
	@echo "make run       - run the Week 0 verification script"
	@echo "make rag|mcp|agent - install later-week dependencies"
	@echo "make clean     - remove the virtual environment"

install:
	@test -d .venv || uv venv
	uv pip install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo ""
	@echo "Setup complete. Next: add your OPENROUTER_API_KEY to python/.env, then run 'make run'."

run:
	uv run python src/verification.py

verify: run

rag:
	uv pip install -e ".[rag]"

mcp:
	uv pip install -e ".[mcp]"

agent:
	uv pip install -e ".[agent]"

clean:
	rm -rf .venv
