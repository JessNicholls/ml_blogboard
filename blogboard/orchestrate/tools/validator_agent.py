import json
import re
import os
import logging
from datetime import datetime
from typing import Optional, List

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# ── Prompt ────────────────────────────────────────────────────────────────────

VALIDATOR_PROMPT = """
You are a strict editorial reviewer and SEO specialist.
Topic: {topic}

Evaluate the following blog post draft:
=== DRAFT START ===
{content}
=== DRAFT END ===

Check for:
1. Is the content substantial, accurate, and professionally written?
2. Does it fully address the core topic?

Respond with STRICTLY JSON:
{{
  "approved": true or false,
  "feedback": "If not approved, explain exactly what is missing or needs to be changed. If approved, leave empty.",
  "title": "If approved, provide a catchy, SEO-optimized title (max 70 chars). Otherwise empty.",
  "description": "If approved, provide a compelling meta description (max 160 chars). Otherwise empty.",
  "slug": "If approved, provide a URL-friendly slug (e.g. 'how-to-train-models'). Otherwise empty."
}}
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


def _build_llm(temperature: float = 1.0):
    from blogboard.config.settings import app_settings
    provider = app_settings.llm.PROVIDER.lower()
    if provider == "watsonx":
        from langchain_ibm import ChatWatsonx
        wx = app_settings.watsonx
        return ChatWatsonx(
            model_id=wx.MODEL_NAME,
            url=wx.URL,
            apikey=wx.API_KEY,
            project_id=wx.PROJECT_ID,
            params={"temperature": temperature, "max_new_tokens": 4096},
        )
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=app_settings.llm.MODEL_NAME,
        temperature=temperature,
        api_key=app_settings.llm.API_KEY,
    )


def _get_prompt(prompt_name: str, fallback: str, **kwargs) -> str:
    try:
        from opik import Opik
        if os.getenv("OPIK_API_KEY"):
            client = Opik()
            return client.get_prompt(name=prompt_name).format(**kwargs)
    except Exception as e:
        logger.warning(f"Opik prompt fetch failed, using fallback: {e}")
    return fallback.format(**kwargs)


# ── Tool ──────────────────────────────────────────────────────────────────────

@tool(
    name="validator_agent",
    description=(
        "Validates a generated blog post draft. If approved, generates metadata "
        "(title, slug, description) and saves the article to local storage. If "
        "rejected, returns feedback so the generator agent can revise. Returns the "
        "updated blog state with revision_needed=True (rejected) or revision_needed=False "
        "plus the saved md_path (approved)."
    ),
    permission=ToolPermission.READ_ONLY,
)
def validator_agent(
    date: str,
    domain: str,
    topic: str,
    content: str,
    dry_run: bool = False,
    subtopics: Optional[str] = None,
    read_time: Optional[str] = None,
    news_data: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    slug: Optional[str] = None,
    tags: Optional[List[str]] = None,
    validator_feedback: Optional[str] = None,
    revision_count: int = 0,
    revision_needed: bool = False,
    md_path: Optional[str] = None,
    skipped: bool = False,
) -> dict:
    """Validate and optionally save a generated blog post draft.

    Args:
        date: Target date for the article in YYYY-MM-DD format.
        domain: ML domain slug (e.g. 'ml', 'dl', 'ainews').
        topic: Article topic string.
        content: The full Markdown content of the draft to validate.
        dry_run: If True, skip LLM calls and simulate approval.
        subtopics: Comma-separated subtopics for the article.
        read_time: Estimated read time string (e.g. '5 min').
        news_data: Raw news research text (passed through).
        title: Article title from a previous run (passed through).
        description: Article description from a previous run (passed through).
        slug: URL slug from a previous run (passed through).
        tags: Category tags list.
        validator_feedback: Feedback from a previous validator rejection.
        revision_count: Number of revision attempts so far.
        revision_needed: Whether a revision was requested by the validator.
        md_path: Path to the saved markdown file from a previous run.
        skipped: Whether this pipeline run was skipped.

    Returns:
        Updated blog state dict. On approval: revision_needed=False, title, slug,
        description, and md_path are set. On rejection: revision_needed=True and
        validator_feedback contains instructions for the generator.
    """
    print("  => [ValidatorAgent] Running...")

    # Rebuild state to pass through any existing fields
    state = {
        "date": date,
        "domain": domain,
        "topic": topic,
        "content": content,
        "dry_run": dry_run,
        "revision_count": revision_count,
        "revision_needed": revision_needed,
        "skipped": skipped,
    }
    if subtopics is not None:
        state["subtopics"] = subtopics
    if read_time is not None:
        state["read_time"] = read_time
    if news_data is not None:
        state["news_data"] = news_data
    if title is not None:
        state["title"] = title
    if description is not None:
        state["description"] = description
    if slug is not None:
        state["slug"] = slug
    if tags is not None:
        state["tags"] = tags
    if validator_feedback is not None:
        state["validator_feedback"] = validator_feedback
    if md_path is not None:
        state["md_path"] = md_path

    if dry_run:
        print("  [DRY RUN] Simulating Approval and Metadata Gen.")
        return {
            **state,
            "revision_needed": False,
            "title": "Dry Run Generated Title",
            "slug": "dry-run-generated",
            "md_path": "r2://dry-run",
            "description": "Dry run generic description.",
        }

    current_revision = revision_count
    _date = date or datetime.now().strftime("%Y-%m-%d")

    prompt = _get_prompt(
        "Validator_Prompt",
        VALIDATOR_PROMPT,
        topic=topic,
        content=content,
    )

    llm = _build_llm(temperature=0.1)
    res = llm.invoke(prompt)

    raw = res.content.strip()
    raw = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    try:
        data = json.loads(raw.strip())
        approved = data.get("approved", True)
        feedback = data.get("feedback", "")
        _title = data.get("title", topic)
        _description = data.get("description", "A blog post about " + topic)
        slug_value = data.get("slug", _title.lower().replace(" ", "-"))
    except json.JSONDecodeError:
        print("  [WARN] Validator failed to return JSON. Forcing approval fallback.")
        approved = True
        feedback = ""
        _title = topic[:70] if topic else "fallback"
        _description = "A blog post about " + _title
        slug_value = _title.lower().replace(" ", "-")

    if not approved and current_revision >= 3:
        print("  [WARN] Max revisions reached. Forcing approval.")
        approved = True

    revision_needed_result = not approved

    if revision_needed_result:
        print(f"  [AGENT] Draft REJECTED. Feedback: {feedback}")
        return {
            **state,
            "revision_needed": True,
            "validator_feedback": feedback,
            "revision_count": current_revision + 1,
        }

    print("  [AGENT] Draft APPROVED! Generating Metadata and Saving locally...")

    from blogboard.services.local_storage import LocalStorageService

    slug_value = re.sub(r"[^\w\s-]", "", slug_value).strip("-")
    md_relative = f"{domain}/{slug_value}.md"
    storage = LocalStorageService()

    storage.put_object(md_relative, content, content_type="text/markdown")
    full_path = storage.base_path / md_relative

    articles = storage.get_articles_json(domain)
    articles = [a for a in articles if a.get("id") != md_relative]
    articles.append({
        "id": md_relative,
        "category": domain,
        "topic": topic,
        "subtopics": subtopics or "",
        "title": _title,
        "description": _description,
        "date": _date,
        "tags": [domain],
        "readTime": read_time or "5 min",
        "file": md_relative,
    })
    articles = sorted(articles, key=lambda x: x["date"], reverse=True)
    storage.save_articles_json(domain, articles)

    return {
        **state,
        "revision_needed": False,
        "title": _title,
        "description": _description,
        "slug": slug_value,
        "md_path": str(full_path),
    }
