# DevBuddy — Setup Guide (Node.js)

This is the working setup for the current repo state. Use it from the repo root or from the `nodejs/` folder as shown below.

---

## Prerequisites

- Node.js (LTS recommended)
- npm
- Git
- An OpenRouter API key

> For the Week 2 demos, use `openai/gpt-4o-mini` in `.env`. Free OpenRouter models may work for a smoke check, but they often fail strict structured-output demos.

---

## 1) Confirm you are in the repo

```bash
cd /path/to/devbuddy
git checkout week-02
git status
```

---

## 2) Install dependencies

```bash
cd nodejs
npm install
```

---

## 3) Configure the environment

```bash
cd nodejs
cp .env.example .env
```

Windows PowerShell:

```powershell
cd nodejs
Copy-Item .env.example .env
```

Then edit `.env` and make sure it contains:

```bash
OPENROUTER_API_KEY=sk-or-your-key
DEVBUDDY_MODEL=openai/gpt-4o-mini
```

This repo already includes a `.env` in `nodejs/`, so if it exists, just confirm the values are correct instead of replacing it blindly.

---

## 4) Run the verification script

```bash
cd nodejs
npm run verify
```

Expected result:

- `VERIFICATION PASSED`
- token count and cost printed
- typed object output, not a raw string

---

## 5) Run the Week 2 demos

```bash
cd nodejs
node scripts/week-02/demo-01-prose-vs-structured.js
node scripts/week-02/demo-02-raw-vs-zod.js
node scripts/week-02/demo-03-inference-parameters.js
node scripts/week-02/demo-04-sketchpad.js
node scripts/week-02/demo-05-agentic-retry.js
node scripts/week-02/demo-06-prompt-engineering.js
node scripts/week-02/explore-readiness-report.js
```

---

## 6) Run schema-only tests

```bash
cd nodejs
npx vitest run tests/test_schemas.js -t "ServiceReadinessReport|BuildCheck"
```

---

## 7) Promptfoo evaluation

This is the correct way to load the repo env and then run the eval:

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

Do not rely on the CLI alone unless the API key is already exported in the terminal environment.

---

## Troubleshooting

### `OPENROUTER_API_KEY not set`

- Confirm the `.env` file is inside `nodejs/`
- Ensure the variable is exported in the shell
- Linux/macOS:

```bash
cd /path/to/devbuddy
set -a
source nodejs/.env
set +a
```

- PowerShell:

```powershell
cd C:\path\to\devbuddy
Get-Content .\nodejs\.env | ForEach-Object {
	if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
	$name, $value = $_ -split '=', 2
	Set-Item -Path Env:$name -Value $value
}
```

### `ERR_MODULE_NOT_FOUND`

```bash
cd nodejs
npm install
```

### Model issues

Use this model for the Week 2 main demos:

```bash
DEVBUDDY_MODEL=openai/gpt-4o-mini
```

Free models are fine for quick smoke tests only.

### Java / Maven mismatch

This is not a Node issue, but if you are switching between folders and seeing Java errors, check:

```bash
java -version
mvn -version
```

---

## Verified in this repo

We ran:

```bash
cd /home/nabarup_maity/devbuddy/nodejs && npm run verify | head -n 200
```

and it passed with `VERIFICATION PASSED` in the current environment.
