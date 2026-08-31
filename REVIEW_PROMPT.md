# 🛡️ Complete Project Review Prompt — PR Sage (Agentic Code Reviewer)

Copy-paste the entire block below into any AI code-review agent (Claude/Codex/etc.) with full read access to this repository. It gives complete context so the reviewer focuses on real engineering substance, not generic advice.

---

## ROLE
You are a **senior staff engineer + AI/ML architect + product strategist** doing a deep, honest engineering review of the PR Sage project. Do NOT write generic advice. Every point must be verified against the actual code with `file:line` references. Be specific, critical, and constructive.

## PROJECT OVERVIEW (verified by reading the code)
- **What it is:** PR Sage = an enterprise, multi-stage "agentic" AI code reviewer for GitHub PRs + local files. Runs a deterministic 4-stage pipeline: Understand → Security → Error Handling → Consolidated Review.
- **Backend core:** `src/agent.py` (PRSageAgent orchestrator, state machine), `src/stages.py` (4 abstract stages + polyglot language detection), `src/diff_parser.py` (unified diff parsing + code-aware sliding-window chunking), `src/guardrails.py` (prompt-injection sanitizer, comment dedup, confidence thresholding, line clamping, caps, patch generation), `src/llm.py` (multi-provider: Groq/OpenAI-compatible + local Ollama with Pydantic structured-output + repair retries), `src/github_client.py` (httpx client w/ rate-limit backoff), `src/config.py` (Pydantic Settings v2 + fail-fast auth validation), `src/models.py` (Pydantic domain contracts), `src/api.py` (FastAPI REST + GitHub webhook w/ HMAC-SHA256), `src/main.py` (CLI).
- **Frontend/UI:** `ui/dashboard.py` (~1590 lines single-file Streamlit cyberpunk console) — preset polyglot vuln scenarios, custom code editor, live GitHub PR diff fetch, multi-model AI hub (Auto-Hybrid AST + Gemini/Claude/OpenAI/Groq/Ollama), health score HUD, inline diff comment thread, 1-click auto-fix + export (patch/md/json), stage trace, precision/recall benchmark. Entrypoints: `app.py`, `streamlit_app.py`, `agent.py`.
- **DevOps:** `Dockerfile` (Streamlit), `render.yaml`, `.github/workflows/review.yml` (PR triggers) + `eval_regression.yml` (pytest + eval harness gate), `docs/RUNNER_SETUP.md` (Windows self-hosted runner + local Ollama for zero-cost private reviews).
- **Eval:** `eval_harness.py` + `eval/data/bug_commits.jsonl` (20 real bug-fix commits) measuring precision/recall/F1 before/after guardrails. `tests/` ~1000+ lines (agent, diff parser, guardrails, github client, llm, stages, api, config, eval).
- **"X-factor" / moat:** (1) deterministic multi-stage pipeline instead of single-shot LLM, (2) strict line-clamping so comments only land on `+` added lines (kills hallucinated GitHub comment placement), (3) noise-control guardrails (confidence ≥0.80, dedup, per-file=5/per-PR=10 caps), (4) offline zero-API-key AST/appsec engine fallback, (5) prompt-injection sanitizer, (6) empirical precision/recall benchmark vs a naive baseline.

## YOUR DELIVERABLES — answer ALL of these, with `file:line` evidence:

### A. Architecture & Backend Review
1. Critique the multi-stage design. Is a sequential stage pipeline actually better than one well-crafted prompt? Where does the "agent" really do intelligent multi-step reasoning vs. just 4 sequential LLM calls? Be honest about whether this is genuine "agentic" behavior.
2. `src/llm.py`: the "multi-model" support is really one OpenAI-compatible client with an Ollama path toggle — is that true? Note limitations (no temperature/model params exposed for some providers, no streaming, hardcoded `keep_alive=0`).
3. `src/agent.py`: review the duplicated guardrail logic (`_apply_file_guardrails`/`_apply_global_guardrails` in agent.py vs `apply_guardrails` in guardrails.py — are they consistent? dead code?). The AST fallback in `review_code` catches ALL exceptions and returns empty findings — is that masking failures?
4. `src/stages.py` Stage 4 "Review Stage" re-provides all prior findings to the LLM — does that actually dedup or just re-emit the same comments (check the merge logic)? Token-cost concerns?
5. `src/api.py`: webhook handler uses FastAPI `BackgroundTasks` (in-process, not durable). Is that production-safe? No auth/rate-limit on `/api/v1/review/*` endpoints (only webhook has HMAC). CORS is `*` with credentials.
6. Thread-safety / singletons: `get_settings()` caches a singleton but `review_code` mutates `settings.MODEL_NAME` — concurrency bug risk under uvicorn?

### B. UI / Frontend Review
7. `ui/dashboard.py` is ONE giant file with inline HTML/CSS strings and logic. List concrete problems: no componentization, `time.time()` runs on every rerun (auto-executes review each rerun?), the AST static analyzer is regex/line-based (false-positive prone) vs the `src/` AST engine as separate code — is it duplicated? The "Auto-Hybrid" calls provider-specific LLMs but silently swallows failures (`except: pass`).
8. Any security leaks in the UI (API keys in `st.text_input` with `type="password"` — is that enough? `unsafe_allow_html=True` with f-strings interpolating findings — XSS risk?).
9. Does the UI actually use the `src/` pipeline (PRSageAgent) or does it re-implement its own engine? This architectural duplication is a big thing to flag. Note `INTERNAL_MODULES_LOADED` fallback.

### C. Database / Persistence — THIS IS A KEY GAP
10. There is **NO database at all** in this project: no SQLite/Postgres, no ORM, no migration tooling, no JSON/Parquet persistence layer. Everything is ephemeral in-memory + a single `review_output.json` overwritten each run. Identify this as the single biggest missing piece and propose a concrete schema (e.g. `reviews`, `comments`, `files`, `telemetry`, `repos/pr_cursor`, `suggestions/applied_fixes`) + what it enables (history, audit trail, dedup across CI runs, dashboards, cost tracking, "applied vs ignored" feedback loop for fine-tuning).
12. List every other missing backend pillar: authn/authz (API keys/JWT, role-based access), multi-tenancy, queueing (Celery/Redis/RQ vs BackgroundTasks), observability (structured logging, metrics/Prometheus, tracing/OpenTelemetry), secret management (keys in env, fine for now but flag Vault/SSM for prod), rate limiting, idempotency for webhooks, caching layer, i18n, error/sentry reporting.

### D. Security Review of the TOOL ITSELF
12. Prompt injection: the sanitizer only regex-replaces a handful of known phrases — is it bypassable (`[REDACTED_UNTRUSTED_DIRECTIVE]` is inserted INTO the prompt — could the model be confused)? Is `sanitize_untrusted_input` applied to the diff/PR body everywhere it should be (check github path vs review_code path)?
13. `verify_github_webhook_signature` — correct HMAC-SHA256 compare? Timing-safe? What if `GITHUB_WEBHOOK_SECRET` is empty (auth silently disabled)?
14. Dependency supply-chain: no pinning/lockfile, no `pip-audit`/`bandit`/`semgrep` in CI. Loose version ranges.

### E. Testing, Eval & CI Review
15. Rate the test suite: good coverage but no tests for the webhook HMAC auth, no integration test against a live/mock GitHub, no test for `eval_harness.py` math beyond what's there, no contract tests. The AST/static analyzer in `ui/dashboard.py` is largely untested.
16. `eval/data/bug_commits.jsonl` only has 20 samples, and the README's claimed numbers (77.78% precision etc.) vs the fallback hardcoded in dashboard (`FALLBACK_EVAL`) differ — investigate this mismatch (dashboard uses a fallback dict with DIFFERENT numbers than README). Flag accuracy of the marketing claims.
17. CI: `review.yml` runs the review on every PR but the secrets may be missing → does the action just fail? No caching of model, no grading/threshold gate that blocks low-precision runs. `eval_regression.yml` runs `--samples 5` only.

### F. "What makes this special / differentiator" — sharpen it
18. Identify the 3–5 genuinely defensible differentiators vs generic AI reviewers (line-clamping, guardrails, offline AST fallback, prompt-injection defense, benchmark evidence) and, equally important, flag where the claims oversell (e.g. "Auto-Hybrid," "100% offline," precision numbers). Recommend how to make the differentiator undeniable (real productized CI action, dataset growth, published benchmark methodology, calibrated confidence).

### G. Missing features & roadmap (prioritize P0/P1/P2)
19. Propose a concrete prioritized roadmap: P0 = DB persistence + durable queue + auth + real CI GitHub Action integration; P1 = unified analysis engine (delete UI/src duplication), provider-agnostic streaming, per-rule suppression/allowlists, code-context embeddings (sometimes vs full-file RAG); P2 = multi-language tree-sitter parsing (drop regex analyzer), feedback-loop fine-tune eval set, plugins, browser extension, GitHub App marketplace.
20. Any correctness bugs you spot while reading (e.g. in `generate_unified_patch`, hunk parsing edge cases, `_extract_json_block`, line-clamping off-by-one, config `SKIP_PATHS` matching) — list concrete ones with line refs.

## OUTPUT FORMAT
Structure your answer as:
1. **Executive Summary** (5 bullet verdict, strengths + critical gaps)
2. **Architecture & Backend** (findings with file:line)
3. **Frontend/UI** (findings)
4. **Database & Persistence** (the P0 gap + proposed schema)
5. **Security of the tool**
6. **Testing / Eval / CI** (incl. numbers mismatch)
7. **What makes it special** (defensible differentiators + what's overstated)
8. **Prioritized Roadmap (P0/P1/P2)**
9. **Top 10 actionable bugs/fixes** (most impactful first)

Be direct and specific. Favor concrete engineering recommendations over praise.
