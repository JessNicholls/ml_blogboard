from typing import Optional, List, Union
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from blogboard.config.settings import app_settings
from blogboard.tools import TavilySearchTool, GuardianSearchTool


def _build_llm(temperature: float) -> BaseChatModel:
    """Instantiate the correct LLM backend based on settings."""
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

    # Default: groq
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=app_settings.llm.MODEL_NAME,
        temperature=temperature,
        api_key=app_settings.llm.API_KEY,
    )


class LLMAgentService:
    """
    A core service class responsible for managing LLM connections and
    orchestrating tool-binding for multi-agent workflows.

    Set llm__provider=groq or llm__provider=watsonx in .env to switch backends.
    """

    def __init__(self, model_name: Optional[str] = None, temperature: Optional[float] = None):
        """
        Args:
            model_name:  Ignored when using watsonx (model is set via watsonx__model_name).
                         Honoured for groq (overrides llm__model_name in settings).
            temperature: Inference temperature. Defaults to llm__temperature in settings.
        """
        self.temperature = temperature if temperature is not None else app_settings.llm.TEMPERATURE
        self.llm: BaseChatModel = _build_llm(self.temperature)

    def get_news_agent(self, system_prompt: Optional[str] = None):
        """
        Constructs a News Research Agent equipped with web-search tools.

        Returns:
            CompiledGraph: A runnable LangGraph ReAct agent with Tavily and Guardian tools.
        """
        news_tools: List[BaseTool] = [
            TavilySearchTool(),
            GuardianSearchTool(),
        ]
        return create_react_agent(
            model=self.llm,
            tools=news_tools,
            prompt=system_prompt,
        )

    def get_custom_agent(self, tools: List[BaseTool], system_prompt: Optional[str] = None):
        """
        A flexible builder to create a custom agent with an arbitrary set of tools.

        Returns:
            CompiledGraph: A runnable LangGraph ReAct agent.
        """
        return create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
        )
