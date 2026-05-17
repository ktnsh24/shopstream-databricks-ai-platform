from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    databricks_host: str
    databricks_token: str
    agent_endpoint_name: str = "helix-shopstream-agent"
    environment: str = "dev"
    request_timeout_seconds: float = 120.0  # Databricks serving cold-start can take 60-90s

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
