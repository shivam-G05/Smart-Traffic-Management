from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STMS_")

    app_name: str = "Smart Traffic Management API"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    tick_hz: int = 20
    broadcast_hz: int = 10


settings = Settings()
