from __future__ import annotations

import logging
import os
import time
from typing import Any
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.agent import PRSageAgent
from src.config import Settings, get_settings
from src.db import DatabaseManager
from src.github_client import GitHubClient
from src.guardrails import verify_github_webhook_signature
from src.llm import LLMClient
from src.models import CodeReviewRequest, PRReviewRequest, ReviewResult


logger = logging.getLogger("pr_sage.api")

app = FastAPI(
    title="PR Sage — Agentic AI Code Reviewer API",
    description="Enterprise REST API & GitHub Webhook Gateway for PR Sage deterministic code reviews.",
    version="2.8.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend / web integrations (credentials disabled for wildcard origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FeedbackRequest(BaseModel):
    """Developer feedback payload."""

    action: str = Field(..., description="'applied', 'dismissed', 'thumbs_up', or 'thumbs_down'")
    comment_id: int | None = Field(default=None, description="Optional target comment ID")
    notes: str = Field(default="", description="Optional feedback notes")


# =====================================================================
# Health & Status Endpoints
# =====================================================================


@app.get("/health", tags=["Monitoring"])
def health_check() -> dict[str, Any]:
    """Returns service health status, runtime uptime, and active configuration."""
    settings = get_settings(DRY_RUN=True)
    db_stats = DatabaseManager.get_instance(settings.DATABASE_PATH).get_statistics()
    return {
        "status": "healthy",
        "service": "pr-sage-agentic-reviewer",
        "version": "2.8.0",
        "model_default": settings.MODEL_NAME,
        "dry_run_default": settings.DRY_RUN,
        "max_comments_per_file": settings.MAX_COMMENTS_PER_FILE,
        "max_comments_per_pr": settings.MAX_COMMENTS_PER_PR,
        "database_stats": db_stats,
    }


# =====================================================================
# Code & PR Review Endpoints
# =====================================================================


@app.post(
    "/api/v1/review/code",
    response_model=ReviewResult,
    tags=["Review"],
    summary="Review raw code or unified diff",
)
def review_code_snippet(payload: CodeReviewRequest) -> ReviewResult:
    """Performs deterministic 4-stage review on a code string or diff snippet.

    Returns structured findings, line mappings, CWE tags, confidence scores, patch, and telemetry.
    """
    custom_model = payload.model or "llama-3.1-8b-instant"
    settings = Settings(DRY_RUN=True, MODEL_NAME=custom_model)

    llm = LLMClient(
        model=custom_model,
        api_key=payload.api_key or settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        timeout=settings.REQUEST_TIMEOUT,
    )
    agent = PRSageAgent(settings=settings, llm=llm)

    try:
        result = agent.review_code(
            code=payload.code,
            filename=payload.filename,
            min_confidence=payload.confidence_threshold,
        )
        return result
    except Exception as exc:
        logger.error(f"Code review failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code review pipeline error: {str(exc)}",
        )


@app.post(
    "/api/v1/review/pr",
    response_model=ReviewResult,
    tags=["Review"],
    summary="Review GitHub Pull Request",
)
def review_github_pr(payload: PRReviewRequest) -> ReviewResult:
    """Fetches diff from GitHub, runs 4-stage pipeline, applies guardrails, and optionally posts comments."""
    custom_model = payload.model or "llama-3.1-8b-instant"
    settings = Settings(DRY_RUN=payload.dry_run, MODEL_NAME=custom_model)
    github = GitHubClient(token=settings.GITHUB_TOKEN)
    llm = LLMClient(
        model=custom_model,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        timeout=settings.REQUEST_TIMEOUT,
    )
    agent = PRSageAgent(settings=settings, github=github, llm=llm)

    try:
        result = agent.run(
            pr_number=payload.pr_number,
            owner=payload.owner,
            repo=payload.repo,
            dry_run=payload.dry_run,
        )
        return result
    except Exception as exc:
        logger.error(f"PR review failed on {payload.owner}/{payload.repo}#{payload.pr_number}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub PR review failed: {str(exc)}",
        )


# =====================================================================
# Review History & Persistence Endpoints
# =====================================================================


@app.get(
    "/api/v1/reviews",
    tags=["History"],
    summary="List recent code review runs",
)
def list_reviews(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    """Retrieves recent review runs and telemetry from the database."""
    settings = get_settings(DRY_RUN=True)
    db = DatabaseManager.get_instance(settings.DATABASE_PATH)
    return db.list_recent_reviews(limit=limit)


@app.get(
    "/api/v1/reviews/{review_id}",
    tags=["History"],
    summary="Get detailed review by ID",
)
def get_review_detail(review_id: int) -> dict[str, Any]:
    """Retrieves a single review record and all associated line comments."""
    settings = get_settings(DRY_RUN=True)
    db = DatabaseManager.get_instance(settings.DATABASE_PATH)
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review #{review_id} not found.")
    return review


@app.post(
    "/api/v1/reviews/{review_id}/feedback",
    tags=["History"],
    summary="Record developer feedback on review",
)
def submit_feedback(review_id: int, payload: FeedbackRequest) -> dict[str, Any]:
    """Records developer acceptance/dismissal feedback for ML fine-tuning and audit."""
    settings = get_settings(DRY_RUN=True)
    db = DatabaseManager.get_instance(settings.DATABASE_PATH)
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review #{review_id} not found.")

    feedback_id = db.record_feedback(
        review_id=review_id,
        comment_id=payload.comment_id,
        action=payload.action,
        notes=payload.notes,
    )
    return {"status": "recorded", "feedback_id": feedback_id}


# =====================================================================
# GitHub Webhook Endpoint
# =====================================================================


def _process_webhook_pr(owner: str, repo: str, pr_number: int) -> None:
    """Background task executing PR Sage on webhook trigger."""
    logger.info(f"Webhook worker processing {owner}/{repo} PR #{pr_number}")
    settings = Settings(DRY_RUN=False)
    github = GitHubClient(token=settings.GITHUB_TOKEN)
    llm = LLMClient(
        model=settings.MODEL_NAME,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
    )
    agent = PRSageAgent(settings=settings, github=github, llm=llm)
    try:
        agent.run(pr_number=pr_number, owner=owner, repo=repo, dry_run=False)
    except Exception as exc:
        logger.error(f"Async webhook review failed for PR #{pr_number}: {exc}")


@app.post(
    "/api/v1/webhooks/github",
    tags=["Webhooks"],
    summary="GitHub Webhook receiver with HMAC authentication",
)
async def github_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
) -> dict[str, str]:
    """Receives and authenticates GitHub pull_request webhooks using HMAC-SHA256."""
    webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    body_bytes = await request.body()

    # Authenticate signature if webhook secret is configured
    if webhook_secret:
        is_valid = verify_github_webhook_signature(
            payload_bytes=body_bytes,
            secret=webhook_secret,
            signature_header=x_hub_signature_256,
        )
        if not is_valid:
            logger.warning("Rejected GitHub webhook: Invalid HMAC-SHA256 signature.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC-SHA256 webhook signature.",
            )
    elif not os.getenv("ALLOW_UNAUTHENTICATED_WEBHOOKS", "false").lower() == "true":
        logger.warning("GITHUB_WEBHOOK_SECRET is not configured on server.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook secret not configured on server.",
        )

    # Ping event response
    if x_github_event == "ping":
        return {"message": "Webhook pong. Authentication valid."}

    # Handle pull_request event
    if x_github_event == "pull_request":
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.")

        action = payload.get("action")
        # Trigger review on PR opened or new commits pushed (synchronize)
        if action in ("opened", "synchronize", "reopened"):
            pr_data = payload.get("pull_request", {})
            pr_number = pr_data.get("number")
            repo_data = payload.get("repository", {})
            full_name = repo_data.get("full_name", "")

            if "/" in full_name and pr_number:
                owner, repo = full_name.split("/", 1)
                background_tasks.add_task(_process_webhook_pr, owner, repo, pr_number)
                return {
                    "status": "enqueued",
                    "action": action,
                    "target": f"{full_name}#{pr_number}",
                }

    return {"status": "ignored", "event": str(x_github_event)}
