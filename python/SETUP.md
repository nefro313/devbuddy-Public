# DevBuddy — Setup Guide (Python)

This is the working setup for the Python project in the current repo.

---

## Prerequisites

- Python 3 (any currently supported CPython)
- pip or uv
- Git
- An OpenRouter API key

> For the Week 2 demos, use `openai/gpt-4o-mini` in `.env`. Free models can be used for smoke verification, but not for the main structured-output demos.

---

## 1) Confirm you are in the repo

```bash
cd /path/to/devbuddy
git checkout week-02
git status
```

---

## 2) Install the Python environment

```bash
cd python
# Linux/macOS
python3 install.py

# Windows PowerShell
py -3 install.py
```

This creates the `.venv`, installs dependencies, and scaffolds `.env` if it does not already exist.

---

## 3) Configure the environment

```bash
cd python
nano .env
```

Windows PowerShell:

```powershell
cd python
notepad .env
```

Set these values:

```bash
OPENROUTER_API_KEY=sk-or-your-key
DEVBUDDY_MODEL=openai/gpt-4o-mini
```

If `.env` already exists, just confirm the values instead of overwriting it.

---

## 4) Run verification

```bash
cd python
source .venv/bin/activate
python3 run.py
```

Windows PowerShell:

```powershell
cd python
.\.venv\Scripts\Activate.ps1
py -3 run.py
```

Expected result:

- `VERIFICATION PASSED`
- token count and estimated cost shown
- typed object output, not a plain string

---

## 5) Run the Week 2 demos

Use `python3` on Linux/macOS and `py -3` on Windows PowerShell.

```bash
cd python
source .venv/bin/activate
python3 scripts/week-02/demo-01-prose-vs-structured.py
python3 scripts/week-02/demo-02-raw-vs-pydantic.py
python3 scripts/week-02/demo-03-inference-parameters.py
python3 scripts/week-02/demo-04-sketchpad.py
python3 scripts/week-02/demo-05-agentic-retry.py
python3 scripts/week-02/demo-06-prompt-engineering.py
python3 scripts/week-02/explore-readiness-report.py
```

---

## 6) Run schema-only tests

Use `python3` on Linux/macOS and `py -3` on Windows PowerShell.

```bash
cd python
source .venv/bin/activate
python3 -m pytest tests/test_schemas.py -v -k "not analyze_pr"
```

---

## 7) Promptfoo evaluation

From the repo root:

```bash
cd /path/to/devbuddy
set -a
source nodejs/.env
set +a
npx promptfoo@latest eval --config shared/evals/week-02-prompt-variants.yaml
```

Windows PowerShell:

```powershell
cd C:\path\to\devbuddy
Get-Content .\nodejs\.env | ForEach-Object {
	if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
	$name, $value = $_ -split '=', 2
	Set-Item -Path Env:$name -Value $value
}
npx promptfoo@latest eval --config shared/evals/week-02-prompt-variants.yaml
```

Or if you want the shell environment to use the Python .env file, you can do:

```bash
cd /path/to/devbuddy
set -a
source python/.env
set +a
npx promptfoo@latest eval --config shared/evals/week-02-prompt-variants.yaml
```

---

## Troubleshooting

### `OPENROUTER_API_KEY not set`

- Check `python/.env`
- Re-source the environment if needed
- Use `echo $OPENROUTER_API_KEY` (Linux/macOS) or `echo $env:OPENROUTER_API_KEY` (PowerShell) to confirm

### `Module not found`

```bash
cd python
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Model issues

Recommended for Week 2:

```bash
DEVBUDDY_MODEL=openai/gpt-4o-mini
```

not a free model for the main Week 2 demos.

---

## Verified in this repo

The Python environment is available and active in the current shell, and the repo has been validated against the real project setup in this workspace.
