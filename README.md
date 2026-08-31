# 🛡️ PR Sage — Enterprise Multi-Stage Agentic AI Code Reviewer

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.39-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Architecture: Multi-Stage Agent](https://img.shields.io/badge/Architecture-Deterministic_State_Machine-purple.svg)]()
[![Guardrails: Zero--Hallucination](https://img.shields.io/badge/Guardrails-Strict_Line_Clamping-success.svg)]()

> **PR Sage** is an enterprise-grade, multi-stage autonomous AI Code Reviewer for GitHub Pull Requests and local repositories. Built with a **deterministic state machine**, **compiler-level Python AST heuristics**, **OWASP AppSec vulnerability scanning**, **strict line-clamping guardrails**, and a **FastAPI Webhook Gateway**, PR Sage replaces naive single-shot LLM prompts with an auditable, noise-controlled engineering tool.

---

## 🏛️ System Architecture

```text
[ GitHub Pull Request / Webhook / REST Client / Streamlit UI ]
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Indirect Prompt Injection Sanitizer     │ (src/guardrails.py)
        └─────────────────────┬────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  Deterministic Unified Diff Parser &     │ (src/diff_parser.py)
        │  Code-Aware Sliding Window Chunking      │
        └─────────────────────┬────────────────────┘
                              │ (150-line chunks, 20-line overlap)
                              ▼
 ┌─────────────────────────────────────────────────────────────┐
 │       4-Stage Deterministic Pipeline (Sequential Execution) │
 │                                                             │
 │   Stage 1: Understand (AST Parse, Intent, Risk Hotspots)    │
 │                             │                               │
 │                             ▼                               │
 │   Stage 2: Security (SQLi, Secrets, RCE, OWASP Top 10)      │
 │                             │                               │
 │                             ▼                               │
 │   Stage 3: Reliability & Error Handling (NoneType, Leaks)   │
 │                             │                               │
 │                             ▼                               │
 │   Stage 4: Review & Consolidation (Deduplication, Summary)  │
 └─────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
 ┌─────────────────────────────────────────────────────────────┐
 │               Production Guardrails & Telemetry             │
 │   • Confidence Thresholding (>= 0.80)                       │
 │   • Strict Line Clamping to verified '+' added lines        │
 │   • Per-File (5) and Per-PR (10) Alert Fatigue Noise Caps   │
 │   • Token, Latency (ms), and USD Cost Measurement           │
 └─────────────────────────────┬───────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [ GitHub REST API / Checks ]          [ 1-Click In-Browser Auto-Fix ]
 (Line comments + PR Summary)          (Clean Refactor + git apply fix.patch)
```

---

## 💡 Why Multi-Stage Pipeline vs Single-Shot LLM?

| Engineering Dimension | Naive Single-Shot LLM | PR Sage Multi-Stage Architecture |
| :--- | :--- | :--- |
| **Cognitive Overload** | Model struggles to audit security, syntax, and logic simultaneously. | **Isolated Stages**: Understand $\to$ Security $\to$ Errors $\to$ Review. |
| **Line Hallucinations** | Comments land on unmodified legacy lines or broken line numbers. | **Deterministic AST & Diff Parser**: Line numbers are pre-computed in Python. |
| **Alert Fatigue & Noise** | Floods PR with 30+ low-value nitpicks. | **Guardrails**: Deduplication, confidence thresholding, and hard noise caps. |
| **Failure Tolerance** | Any JSON parsing error crashes the entire review. | **Fault Isolation & 1-Shot Self-Correction Retries**. |
| **Prompt Injection** | Adversarial comments in code trick model into approving. | **Pre-Inference Sanitizer & Untrusted Role Isolation**. |

---

## ⚡ Multi-Model AI Hub & Fallback Engine

PR Sage supports multi-model routing and zero-network offline fallbacks:

1. **🔥 Auto-Hybrid Pipeline (Default):** Runs static compiler AST checks in $<10$ms and merges LLM semantic business logic.
2. **⚡ Built-in AST Engine:** 100% offline, zero-network, zero-API-key compiler-level static analysis.
3. **✨ Google Gemini:** Powered by `gemini-2.0-flash` / `gemini-1.5-pro`.
4. **🟣 Anthropic Claude:** Powered by `claude-3-5-sonnet` / `claude-3-5-haiku`.
5. **🧠 OpenAI:** Powered by `gpt-4o` / `gpt-4o-mini`.
6. **☁️ Groq Cloud:** High-throughput `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`.
7. **🦙 Local Ollama:** Free private on-premise inference (`llama3.2:3b`).

---

## 🚀 Quickstart & Usage

### 1. Installation
```bash
git clone https://github.com/ishanpanwar051/agentic-code-reviewer.git
cd agentic-code-reviewer
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file from `.env.example`:
```env
GITHUB_TOKEN=your_github_personal_access_token
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
GITHUB_WEBHOOK_SECRET=your_webhook_hmac_secret
```

### 3. Launch Interactive Enterprise Dashboard (Streamlit)
```bash
streamlit run ui/dashboard.py
```

### 4. Start Production REST API & Webhook Server (FastAPI)
```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be available at `http://localhost:8000/docs`.

### 5. CLI Execution
```bash
# Review a local file or demo vulnerability
python -m src.main --file demo/pr_vulnerable.py

# Review a live GitHub Pull Request (Dry-Run mode)
python -m src.main --pr-number 42 --owner pallets --repo flask --dry-run
```

---

## 📊 Empirical Evaluation Benchmark

PR Sage is benchmarked against **20 historical bug-fix commits** from major open-source repositories (*FastAPI, Requests, Flask, SQLAlchemy, Django, Celery*).

### Benchmark Results (`eval/data/bug_commits.jsonl`)

| Metric | Raw Baseline LLM | PR Sage (With Guardrails) | Improvement Delta |
| :--- | :---: | :---: | :---: |
| **Precision** | 12.24% | **77.78%** | **+65.54% Precision Gain** |
| **Recall** | 23.08% | **80.77%** | **+57.69% Recall Gain** |
| **F1 Score** | 0.16 | **0.79** | **+0.63 F1 Improvement** |
| **False Positives (Noise)** | 43 | **6** | **-37 Noise Comments Eliminated** |

Run the automated evaluation harness locally:
```bash
python eval_harness.py
```

---

## 🔌 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check, active model, and configuration telemetry. |
| `POST` | `/api/v1/review/code` | Analyzes code string, returning findings, confidence, telemetry, and patch. |
| `POST` | `/api/v1/review/pr` | Executes 4-stage review on GitHub PR. |
| `POST` | `/api/v1/webhooks/github` | Authenticated webhook listener with HMAC-SHA256 signature verification. |

---

## 🧪 Testing Suite

Run unit and integration tests with pytest:
```bash
pytest -v
```

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for details.
