import json
import re
import math
import os
import logging
from typing import Optional, List

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# ── Prompts ───────────────────────────────────────────────────────────────────

TUTORIAL_TOPIC_PROMPT = """
You are an expert content strategist for a technical blog.
Domain: {cat_label}

Recent History of articles published in this domain:
{history}

Your task is to select an exciting, novel topic that hasn't been covered in the recent history above.
Return the result strictly as JSON:
{{
  "topic": "The title of the new topic",
  "subtopics": "A comma-separated list of 3-4 subtopics to cover"
}}
"""

TUTORIAL_GENERATION_PROMPT = """
You are a highly skilled technical writer.
Domain/Category: {cat_label}
Topic: {topic}
Subtopics to cover: {subtopics}

{validator_feedback}

Your task is to write a comprehensive, highly engaging, and in-depth tutorial blog post in Markdown format.
Use a professional tone, appropriate headers, and bold critical terms. Do not include a markdown codeblock around your entire response.
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

def _read_time(text: str) -> str:
    return f"{math.ceil(len(text.split()) / 200)} min"


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
    name="tutorial_agent",
    description=(
        "Selects a domain and topic, then generates a comprehensive tutorial-style "
        "blog post in Markdown. Returns the updated blog state including the generated "
        "content, domain, topic, subtopics, and estimated read time."
    ),
    permission=ToolPermission.READ_ONLY,
)
def tutorial_agent(
    date: str,
    dry_run: bool = False,
    domain: Optional[str] = None,
    topic: Optional[str] = None,
    subtopics: Optional[str] = None,
    content: Optional[str] = None,
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
    """Generate a tutorial-style blog post.

    Args:
        date: Target date for the article in YYYY-MM-DD format.
        dry_run: If True, skip LLM calls and return placeholder content.
        domain: ML domain slug (e.g. 'ml', 'dl', 'nlp'). Auto-selected if omitted.
        topic: Article topic. Auto-selected if omitted.
        subtopics: Comma-separated subtopics for the article.
        content: Existing content (used during revision loops).
        read_time: Estimated read time string (e.g. '5 min').
        news_data: Raw news research text (passed through from news agent).
        title: Article title (passed through from validator).
        description: Article description (passed through from validator).
        slug: URL slug (passed through from validator).
        tags: Category tags list.
        validator_feedback: Feedback from a previous validator rejection.
        revision_count: Number of revision attempts so far.
        revision_needed: Whether a revision was requested by the validator.
        md_path: Path to the saved markdown file.
        skipped: Whether this pipeline run was skipped.

    Returns:
        Updated blog state dict with domain, topic, subtopics, content, and read_time populated.
    """
    from blogboard.config.settings import app_settings
    from blogboard.services.local_storage import LocalStorageService

    print("  => [TutorialAgent] Running...")

    storage = LocalStorageService()
    _subtopics = subtopics or ""

    # ── Step 1: Topic selection ───────────────────────────────────────────────
    _topic = topic
    _domain = domain

    if not _topic:
        domain_dates = storage.get_all_domains_last_updated()
        valid_domains = {k: v for k, v in domain_dates.items() if k != "ainews"}
        sorted_domains = sorted(valid_domains.items(), key=lambda item: item[1])
        _domain = sorted_domains[0][0]

        tags_config = app_settings.tags.model_dump()
        cat_label = tags_config.get(_domain, {}).get("label", _domain)

        print(f"  [AGENT] Autonomously selected domain: {_domain}")

        recent_history = storage.get_recent_history(_domain, limit=3)
        history_str = "No recent history found."
        if recent_history:
            history_str = "\n---\n".join([
                f"Title: {item['title']}\nTopic: {item['topic']}\nSubtopics: {item['subtopics']}"
                for item in recent_history
            ])

        topic_prompt = _get_prompt(
            "Tutorial_Topic_Prompt",
            TUTORIAL_TOPIC_PROMPT,
            cat_label=cat_label,
            history=history_str,
        )

        llm = _build_llm(temperature=0.8)
        res = llm.invoke(topic_prompt)
        raw = res.content.strip()
        raw = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

        try:
            topic_data = json.loads(raw.strip())
            _topic = topic_data.get("topic", "Advanced Concepts")
            _subtopics = topic_data.get("subtopics", "")
        except json.JSONDecodeError:
            tags_config = app_settings.tags.model_dump()
            cat_label = tags_config.get(_domain, {}).get("label", _domain)
            _topic = "Emerging Trends in " + cat_label
            _subtopics = ""

        print(f"  [AGENT] Picked Topic: {_topic}")
    else:
        tags_config = app_settings.tags.model_dump()
        cat_label = tags_config.get(_domain, {}).get("label", _domain)
        print(f"  [AGENT] Topic already defined: {_topic}")

    # Rebuild state to pass through any existing fields
    state = {
        "date": date,
        "dry_run": dry_run,
        "domain": _domain,
        "topic": _topic,
        "subtopics": _subtopics,
        "revision_count": revision_count,
        "revision_needed": revision_needed,
        "skipped": skipped,
    }
    if content is not None:
        state["content"] = content
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

    # ── Step 2: Content generation ────────────────────────────────────────────
    if dry_run:
        print("  [DRY RUN] Skipping LLM Generation.")
        return {
            **state,
            "content": f"# {_topic}\n\nDry run tutorial text.",
            "read_time": "1 min",
        }

    feedback_str = ""
    if validator_feedback:
        feedback_str = f"CRITICAL FEEDBACK FROM PREVIOUS DRAFT. You must fix these issues:\n{validator_feedback}"

    generation_prompt = _get_prompt(
        "Tutorial_Generation_Prompt",
        TUTORIAL_GENERATION_PROMPT,
        cat_label=cat_label,
        topic=_topic,
        subtopics=_subtopics,
        validator_feedback=feedback_str,
    )

    llm_gen = _build_llm(temperature=0.6)
    res_gen = llm_gen.invoke(generation_prompt)
    generated_content = res_gen.content.strip()
    rt = _read_time(generated_content)

    print(f"  [AGENT] Generated {len(generated_content.split())} words. Read time: {rt}")

    return {
        **state,
        "content": generated_content,
        "read_time": rt,
    }
