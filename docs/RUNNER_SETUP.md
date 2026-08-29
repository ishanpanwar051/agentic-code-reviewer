# Self-Hosted Runner & Local Setup Guide (Windows / 8GB RAM)

This guide walks you through setting up a **GitHub Self-Hosted Runner** on your local Windows machine so PR Sage can review real pull requests using your local Ollama instance with **zero cloud costs** and **100% data privacy**.

---

## 1. Why a Self-Hosted Runner? (Interview Talking Point)

- **Zero API Ingestion Costs**: Cloud LLM API calls on large repositories accumulate costs rapidly. Running locally with `llama3.2:3b` is 100% free.
- **Enterprise Data Privacy**: Proprietary code diffs never leave your local infrastructure or network.
- **Direct Local Ollama Access**: The self-hosted runner executes on the same machine where Ollama is running at `http://localhost:11434`.

---

## 2. Prerequisites

1. **Python 3.11+** installed (`python --version`).
2. **Ollama** installed and running on Windows.
3. Pull the required models:
   ```bash
   ollama pull llama3.2:3b
   ollama pull nomic-embed-text
   ```

---

## 3. GitHub Fine-Grained Personal Access Token (PAT)

1. Navigate to **GitHub** → **Settings** → **Developer Settings** → **Personal Access Tokens** → **Fine-grained tokens**.
2. Click **Generate new token**.
3. Set **Repository Access**: Select *Only select repositories* → Pick your target repository.
4. Under **Permissions**, grant:
   - **Pull requests**: `Read and write` (Required to fetch diffs and post review comments).
   - **Contents**: `Read-only` (Required to inspect commit metadata).
5. Copy the generated token (`github_pat_...`) and store it safely in your local `.env`.

---

## 4. Setting up the GitHub Self-Hosted Runner on Windows

1. On your GitHub repository page:
   - Go to **Settings** → **Actions** → **Runners**.
   - Click **New self-hosted runner**.
   - Select **Runner image**: `Windows`, **Architecture**: `x64`.
2. Open PowerShell as Administrator on your PC and run the commands provided by GitHub:
   ```powershell
   # Create runner folder
   mkdir C:\actions-runner; cd C:\actions-runner

   # Download runner package (adjust version as instructed in GitHub UI)
   Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.317.0/actions-runner-win-x64-2.317.0.zip -OutFile actions-runner-win-x64-2.317.0.zip
   Expand-Archive -Path actions-runner-win-x64-2.317.0.zip -DestinationPath .

   # Configure runner with your repo token
   .\config.cmd --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_REGISTRATION_TOKEN

   # Run as interactive listener or install as background Windows service
   .\run.cmd
   ```
3. Once running, GitHub will show your runner status as **🟢 Idle / Online**.

---

## 5. Local Dry-Run Testing (Without GitHub Actions)

You can run PR Sage locally at any time against any public or private PR:

```powershell
# Activate venv
venv\Scripts\Activate.ps1

# Run in dry-run mode (outputs to review_output.json & review_output.md)
python -m agent --pr-number 1 --owner your-username --repo your-repo --dry-run
```
