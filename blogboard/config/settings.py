from typing import Dict, Optional
from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMSettings(BaseModel):
    PROVIDER: str = "groq"  # "groq" or "watsonx"
    API_KEY: str = Field(default="", validation_alias=AliasChoices('API_KEY', 'api_key', 'GROQ_API_KEY', 'groq_api_key'))
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    TEMPERATURE: float = 1.0

class WatsonxSettings(BaseModel):
    API_KEY: str = ""
    PROJECT_ID: str = ""
    URL: str = "https://eu-gb.ml.cloud.ibm.com"
    MODEL_NAME: str = "meta-llama/llama-3-3-70b-instruct"

class TagSettings(BaseModel):
    ml: Dict[str, str] = {"label": "Machine Learning", "shortLabel": "ML"}
    dl: Dict[str, str] = {"label": "Deep Learning", "shortLabel": "DL"}
    statistics: Dict[str, str] = {"label": "Statistics for AI", "shortLabel": "Stats"}
    nlp: Dict[str, str] = {"label": "Natural Language Processing", "shortLabel": "NLP"}
    cv: Dict[str, str] = {"label": "Computer Vision", "shortLabel": "CV"}
    genai: Dict[str, str] = {"label": "Generative AI", "shortLabel": "Gen AI"}
    ainews: Dict[str, str] = {"label": "AI News", "shortLabel": "AI News"}

class R2Settings(BaseModel):
    ACCOUNT_ID: str = "not-used"
    ACCESS_KEY_ID: str = "not-used"
    SECRET_ACCESS_KEY: str = "not-used"
    BUCKET_NAME: str = "not-used"

class ContentAPISettings(BaseModel):
    TAVILY_API_KEY: str = ""
    GUARDIAN_API_KEY: str = ""
    UNSPLASH_API_KEY: str = ""

class Settings(BaseSettings):
    llm: LLMSettings
    watsonx: WatsonxSettings = Field(default_factory=WatsonxSettings)
    tags: TagSettings = Field(default_factory=TagSettings)
    r2: R2Settings = Field(default_factory=R2Settings)
    content: ContentAPISettings = Field(default_factory=ContentAPISettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

app_settings = Settings()