"""Global settings via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class UniversalGearSettings(BaseSettings):
    """Global configuration loaded from env vars / .env / YAML."""

    model_config = {"env_prefix": "UGEAR_"}

    log_level: str = "INFO"
    log_json: bool = False
    fail_fast: bool = True
    validate_transitions: bool = True
