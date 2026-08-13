# Contributing to DevBuddy

## Setup

1. Fork the repo: `gh repo fork org/devbuddy --clone`
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add your `OPENROUTER_API_KEY`
5. Run verification: `python src/verification.py`

## Code Style

- Python 3.11+. Type hints required on all public functions.
- Format with `black`. Lint with `mypy`.
- Run tests before pushing: `pytest tests/ -v`

## Pull Requests

- Branch from `main`. Use descriptive branch names: `feat/structured-output`, `fix/llm-timeout`.
- One module per PR. Don't mix `schemas.py` and `rag.py` changes.
- PR description must include: what changed, why, testing done.
- At least one other engineer must approve before merge.

## Project Structure

```
src/
├── llm.py          # OpenRouter client factory
├── schemas.py      # Pydantic models + structured LLM calls
├── rag.py          # RAG pipeline (embed, chunk, store, retrieve)
├── verification.py # Environment verification script
shared/data/        # Test data and document sets
tests/              # pytest test suite
```

## Adding a Document to the RAG Index

Place `.md` or `.txt` files in `shared/data/`. The RAG pipeline automatically indexes all files in that directory. Re-index after adding new documents:

```python
from src.rag import index_documents
index_documents("../shared/data/")
```
