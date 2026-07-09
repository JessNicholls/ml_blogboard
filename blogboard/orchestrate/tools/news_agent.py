import math
import os
import logging
from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# ── Prompt ────────────────────────────────────────────────────────────────────

NEWS_GENERATION_PROMPT = """
You are a highly-skilled technology journalist.
Domain: {cat_label}
Topic/Headline Focus: {topic}

Extracted Live Search Context:
{news_context}

{validator_feedback}

Your task is to synthesize the extracted context above into a cohesive, highly engaging technical news roundup blog post in Markdown format.
Focus on factual accuracy, properly summarizing the facts from the search context.
Use a professional journalism tone, appropriate headers, and bold critical terms. Do not include a markdown codeblock around your entire response.
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
    name="news_agent",
    description=(
        "Researches live AI news using web-search tools, then synthesises the findings "
        "into a technology news roundup blog post in Markdown. Returns the updated blog "
        "state including the generated content, news research summary, and estimated read time."
    ),
    permission=ToolPermission.READ_ONLY,
)
def news_agent(
    date: str,
    dry_run: bool = False,
    domain: Optional[str] = None,
    topic: Optional[str] = None,
    content: Optional[str] = None,
    read_time: Optional[str] = None,
    news_data: Optional[str] = None,
    validator_feedback: Optional[str] = None,
    revision_count: int = 0,
    revision_needed: bool = False,
    md_path: Optional[str] = None,
    skipped: bool = False,
) -> dict:
    """Generate an AI news roundup blog post.

    Args:
        date: Target date for the article in YYYY-MM-DD format.
        dry_run: If True, skip LLM calls and return placeholder content.
        domain: Domain slug — will be forced to 'ainews' by this agent.
        topic: News topic. Defaults to 'Latest AI News' if omitted.
        content: Existing content (used during revision loops).
        read_time: Estimated read time string (e.g. '5 min').
        news_data: Previously fetched news summary. If present, skips the research step.
        validator_feedback: Feedback from a previous validator rejection.
        revision_count: Number of revision attempts so far.
        revision_needed: Whether a revision was requested by the validator.
        md_path: Path to the saved markdown file.
        skipped: Whether this pipeline run was skipped.

    Returns:
        Updated blog state dict with domain, topic, news_data, content, and read_time populated.
    """
    from blogboard.config.settings import app_settings

    print("  => [NewsAgent] Running...")

    # Domain is always ainews
    _domain = "ainews"
    _topic = topic or "Latest AI News"

    tags_config = app_settings.tags.model_dump()
    cat_label = tags_config.get(_domain, {}).get("label", _domain)

    # Rebuild state to pass through any existing fields
    state = {
        "date": date,
        "dry_run": dry_run,
        "domain": _domain,
        "topic": _topic,
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
    if validator_feedback is not None:
        state["validator_feedback"] = validator_feedback
    if md_path is not None:
        state["md_path"] = md_path

    if dry_run:
        print("  [DRY RUN] Skipping News Research & Generation.")
        return {
            **state,
            "domain": _domain,
            "topic": _topic,
            "news_data": "Dry run news data.",
            "content": f"# {_topic}\n\nDry run AI News text.",
            "read_time": "1 min",
        }

    # ── Step 1: Research ──────────────────────────────────────────────────────
    news_summary = news_data or ""
    if not news_summary:
        print("  [AGENT] Researching the web for live news...")
        from langchain_core.tools import BaseTool
        from langgraph.prebuilt import create_react_agent
        from blogboard.tools import TavilySearchTool, GuardianSearchTool

        llm = _build_llm(temperature=1.0)
        system_prompt = (
            "You are a seasoned AI news researcher. "
            "Use your SearchTools to find the top 3 most important news articles from the past week "
            f"related to the topic: {_topic}. "
            "Summarize the findings clearly, providing URL citations. "
            "Be extremely comprehensive as this will be used to write a blog post."
        )
        research_agent = create_react_agent(
            model=llm,
            tools=[TavilySearchTool(), GuardianSearchTool()],
            prompt=system_prompt,
        )
        response = research_agent.invoke({"messages": [("user", f"Find the latest news for {_topic}")]})
        news_summary = response["messages"][-1].content
        print(f"  [AGENT] Formulated research context ({len(news_summary)} chars).")

    # ── Step 2: Generation ────────────────────────────────────────────────────
    print("  [AGENT] Drafting the news blog...")
    feedback_str = ""
    if validator_feedback:
        feedback_str = f"CRITICAL FEEDBACK FROM PREVIOUS DRAFT. You must fix these issues:\n{validator_feedback}"

    prompt = _get_prompt(
        "News_Generation_Prompt",
        NEWS_GENERATION_PROMPT,
        cat_label=cat_label,
        topic=_topic,
        news_context=news_summary,
        validator_feedback=feedback_str,
    )

    llm_gen = _build_llm(temperature=0.4)
    res = llm_gen.invoke(prompt)
    generated_content = res.content.strip()
    rt = _read_time(generated_content)

    print(f"  [AGENT] Generated {len(generated_content.split())} words. Read time: {rt}")

    return {
        **state,
        "domain": _domain,
        "topic": _topic,
        "news_data": news_summary,
        "content": generated_content,
        "read_time": rt,
    }
