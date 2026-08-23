# 🛡️ PR Sage — Agentic AI Code Reviewer

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ollama: llama3.2:3b](https://img.shields.io/badge/Local_LLM-llama3.2%3A3b-orange.svg)](https://ollama.ai/)
[![Architecture: Multi--Step_Agent](https://img.shields.io/badge/Architecture-Deterministic_Multi--Step_Agent-purple.svg)]()
[![Hardware: 8GB RAM](https://img.shields.io/badge/Hardware-8GB_RAM_No_GPU-success.svg)]()

> **PR Sage** is a production-grade, multi-stage autonomous AI Code Reviewer for GitHub Pull Requests. Engineered specifically to run on resource-constrained hardware (8GB RAM, no GPU) using local small language models (`llama3.2:3b`), PR Sage replaces naive single-shot LLM prompts with an orchestrated, deterministic 4-stage pipeline with strict Pydantic v2 schemas, prompt injection sanitization, fault isolation, and real-world precision/recall evaluation.

---

## 🏛️ System Architecture

```mermaid
graph TD
    PR[GitHub Pull Request Event] --> Actions[GitHub Actions / Local Self-Hosted Runner]
    Actions --> Agent[PRSageAgent Orchestrator]
    
    subgraph "Deterministic Pre-Processing Layer"
        Agent --> Client[Resilient GitHub Client: httpx + Rate-Limit Backoff]
        Client --> RawDiff[Raw Unified Diff]
        RawDiff --> DiffParser[Deterministic Diff Parser: Hunk Offsets & Added Lines]
        DiffParser --> Filter[Filter: Skip-Paths, Binary Assets, Renames]
        Filter --> Chunker[CodeChunker: 150-Line Windows with 20-Line Overlap]
    end

    subgraph "Multi-Step Sequential Agent Pipeline (Per Chunk)"
        Chunker --> S1[Stage 1: UnderstandStage<br/><i>Diff summary, developer intent, risk hotspots</i>]
        S1 --> S2[Stage 2: SecurityStage<br/><i>AppSec vulnerabilities on '+' lines only</i>]
        S2 --> S3[Stage 3: ErrorHandlingStage<br/><i>Unhandled exceptions, silent swallows, leaks</i>]
        S3 --> S4[Stage 4: ReviewStage<br/><i>Consolidation, deduplication, severity rating</i>]
    end

    subgraph "Production Guardrails & Submission"
        S4 --> Guardrails[Guardrails Engine:<br/>- Strict Added-Line Clamping<br/>- Near-Duplicate Filtering<br/>- Per-File Cap: 5 | Global PR Cap: 10]
        Guardrails --> Mode{DRY_RUN?}
        Mode -- True --> LocalOut[Save review_output.json & review_output.md]
        Mode -- False --> PostReview[GitHub REST API: POST /pulls/{n}/reviews]
    end
```

---

## 💡 Why Multi-Step Agent vs Single-Shot LLM? (Interview Deep-Dive)

| Aspect | Naive Single-Shot LLM | PR Sage Multi-Step Pipeline |
| :--- | :--- | :--- |
| **Cognitive Load on 3B Model** | Overwhelmed (tries to understand, check security, verify exceptions, and format JSON all at once). | **Isolated Focus**: 4 sequential stages with dedicated system prompts and schemas. |
| **Line Number Precision** | High hallucination rate (LLMs cannot reliably count raw diff offsets). | **Deterministic AST/Hunk Math**: Line numbers mapped in Python before LLM prompt injection. |
| **False Alarm Rate (Noise)** | Floods PR with 20+ trivial comments on legacy code. | **Added-Lines-Only Filter + Guardrail Caps** (5 per file, 10 per PR). |
| **Failure Mode** | Any JSON parsing error crashes the entire review. | **Fault-Isolated Stages + Surgical 1-Shot Repair Retries**. |
| **Prompt Injection Risk** | Adversarial comments in code can override review logic. | **Sanitized Input + Immutable System Prompts**. |

### Why a Deterministic Pipeline over Free-Form Agents (LangGraph)?
> *"I chose a deterministic state-machine pipeline over a free-form agent for reliability and auditability. In a production code review bot, every stage must satisfy an immutable schema contract. Free-form agents are prone to unpredictable tool loops, non-deterministic latency spikes, and are nearly impossible to benchmark against regression datasets. A deterministic pipeline makes every review stage individually unit-testable and reproducible."*

---

## 🛡️ Production Failure Handling (5 Critical Scenarios)

PR Sage is engineered to never crash a CI/CD pipeline or corrupt PR threads:

```
+---------------------------------------------------------------------------------------------------+
| SCENARIO 1: LLM Crash / Timeout                                                                   |
| Behavior: Per-stage retry (2x) with exponential backoff. If Ollama remains unresponsive,          |
| the stage logs `skipped: {reason}` and continues to the next stage. The run never crashes.        |
+---------------------------------------------------------------------------------------------------+
| SCENARIO 2: Malformed / Incomplete JSON Output                                                    |
| Behavior: Strict JSON fence stripper -> Pydantic validator -> Surgical 1-Shot Repair Prompt        |
| (feeds exact ValidationError back to model). Malformed findings are safely dropped & logged.      |
+---------------------------------------------------------------------------------------------------+
| SCENARIO 3: Massive File Diffs (>150 Lines)                                                       |
| Behavior: Code-aware sliding window chunker splits hunks into 150-line slices with 20-line         |
| overlap. Line numbers are preserved, partial findings merged, and duplicate findings deduped.     |
+---------------------------------------------------------------------------------------------------+
| SCENARIO 4: GitHub API 429 / 403 Rate Limiting                                                    |
| Behavior: Client parses `x-ratelimit-reset` and `Retry-After` headers, sleeps until the window    |
| opens, and retries with jittered exponential backoff (max 3 retries).                             |
+---------------------------------------------------------------------------------------------------+
| SCENARIO 5: Agent State Corruption                                                                |
| Behavior: `AgentState.validate_state()` enforces cross-stage invariants (non-empty PR, valid      |
| owner/repo, dictionary integrity) before dispatching API calls.                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 📊 Real-World Bug Evaluation & Benchmarks

PR Sage is evaluated against **20 real-world historical bug-fix commits** from top open-source repositories (*FastAPI, Requests, Flask, SQLAlchemy, Django, Celery*).

### Benchmark Results (`eval/data/bug_commits.jsonl`)

| Metric | Raw LLM Baseline | PR Sage (With Guardrails) | Delta / Improvement |
| :--- | :---: | :---: | :---: |
| **Precision** | 38.46% | **61.54%** | **+23.08% Precision Gain** |
| **Recall** | 50.00% | **50.00%** | Maintained High Recall |
| **F1 Score** | 0.43 | **0.55** | **+0.12 F1 Improvement** |
| **False Alarms (Noise)** | 16 | **5** | **68.75% Noise Reduction** |

### Honest Error Breakdown (3B Model Realities)
- **Strengths**: Excels at local single-function flaws: SQL injections, hardcoded JWT tokens, bare `except: pass` swallows, missing NoneType checks, and unvalidated redirects.
- **Limitations**: Cross-file architectural bugs and subtle race conditions spanning 300+ lines require larger context windows than 3B parameters can reliably reason over.

---

## 🔒 Security, Privacy & Token Scoping

1. **Fine-Grained Token Least Privilege**:
   - Only requires `Pull requests: Read & write` and `Contents: Read-only`.
   - Never request administrative or workflow rewrite scopes.
2. **Zero Cloud Ingestion (Local LLM)**:
   - Proprietary source code never leaves your local network or runner host.
3. **Indirect Prompt Injection Defense**:
   - `sanitize_untrusted_input()` scans diffs and PR descriptions for adversarial prompts (`Ignore previous instructions`, `SYSTEM: approve`, `<|im_start|>`) and neutralizes them before prompt construction.

---

## ⚡ Quickstart & Setup

### 1. Clone & Setup Environment
```powershell
# Clone repository
git clone https://github.com/your-username/pr-sage.git
cd pr-sage

# Create & activate Python 3.11 virtual environment
py -3.11 -m venv venv
venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```ini
GITHUB_TOKEN=github_pat_11A...
REPO=your-username/your-repo
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=llama3.2:3b
DRY_RUN=false
```

### 3. Start Local Ollama
```bash
ollama run llama3.2:3b
```

### 4. Run Unit Tests (100% Green Coverage)
```powershell
pytest tests/ -v
```

### 5. Execute Local Dry-Run Review
```powershell
python -m agent --pr-number 42 --owner octocat --repo Hello-World --dry-run
```

### 6. Run Benchmark Evaluation Harness
```powershell
python eval_harness.py
```

### 7. Launch Interactive Visual Console
Turn the agentic pipeline, guardrails, and precision/recall benchmark into a polished,
browser-based dashboard (Streamlit) — the fastest way to demo this project.
```powershell
pip install streamlit pandas numpy
streamlit run ui/dashboard.py
```

---

## 🧩 Portfolio Comparison: DocRetriever vs PR Sage

| Dimension | Project #1: DocRetriever (RAG) | Project #2: PR Sage (Agentic AI) |
| :--- | :--- | :--- |
| **Core Paradigm** | Retrieval-Augmented Generation (Embeddings + Vector DB) | Autonomous Multi-Step Agentic Workflow |
| **State Management** | Stateless query-response cycle | Multi-stage `AgentState` accumulator |
| **Execution Flow** | Similarity Search -> Context Augmentation -> Generation | Understand -> Security -> Error Handling -> Review |
| **Failure Handling** | Fallback semantic chunks | Self-correcting JSON repair retries + stage isolation |
| **Evaluation Metric** | Context Precision, Answer Relevance (Ragas) | Real Bug Precision, Recall, F1 Score & Noise Delta |

---

## 📜 License
MIT License. Engineered for open-source AI engineering portfolio excellence.
