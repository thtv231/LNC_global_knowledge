from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_suggest_model: str = "llama-3.1-8b-instant"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = "../../.env"
        extra = "ignore"


settings = Settings()
