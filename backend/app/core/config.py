from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STMS_")

    app_name: str = "Smart Traffic Management API"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    tick_hz: int = 20
    broadcast_hz: int = 10
    controller_type: str = "fixed"  # "fixed" | "adaptive" | "adaptive_hold" (adaptive + discharge hold)
    # SQLite by default — zero external install. Swap to a
    # postgresql+asyncpg://... DSN later with no code change.
    database_url: str = "sqlite+aiosqlite:///./traffic.db"
    # Shared between the primary and Milestone 9's shadow runner so both
    # see identical vehicle arrivals — the controller is the only variable
    # being compared. Fixed rather than random so a demo is reproducible.
    comparison_seed: int = 42


settings = Settings()
