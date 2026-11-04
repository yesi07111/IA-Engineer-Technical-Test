import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from emporio_agent.errors import ConfigurationError

# This is for telling the user which key is missing before the first message fails
PROVIDER_API_KEYS: dict[str, tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


class Settings(BaseSettings):
    """Settings read from environment variables prefixed with EMPORIO_ or from .env."""

    model_config = SettingsConfigDict(
        env_prefix="EMPORIO_", env_file=".env", extra="ignore", env_ignore_empty=True
    )

    model: str = Field("anthropic:claude-sonnet-5-5", description="provider:model")
    temperature: float | None = Field(None, ge=0, le=1, description="None uses the default")
    data_dir: Path = Path("data")
    memory_db: Path = Path(".memory/conversations.sqlite")
    tickets_file: Path = Path(".memory/handoff_tickets.jsonl")
    timezone: str = "America/Campo_Grande"
    max_agent_steps: int = Field(25, ge=5, le=100)
    requests_per_minute: float | None = Field(
        None, gt=0, description="Limit for free tiers, e.g. 5. Empty means no limit"
    )

    @field_validator("model")
    @classmethod
    def check_model_format(cls, value: str) -> str:
        """Validates the "provider:model" format.

        Args:
            value: Raw EMPORIO_MODEL value.

        Returns:
            The value without surrounding spaces.

        Raises:
            ValueError: If there is no provider prefix.
        """
        value = value.strip()
        provider, _, name = value.partition(":")
        if not provider or not name:
            raise ValueError("use the format provider:model, e.g. anthropic:claude-sonnet-5-5")
        return value

    @property
    def provider(self) -> str:
        """Gets the provider part of the model setting.

        Returns:
            The text before ":", e.g. "anthropic".
        """
        return self.model.split(":", 1)[0]

    def check_ready_to_chat(self) -> None:
        """Checks the things that would make the first message fail.

        Raises:
            ConfigurationError: If the data folder is missing or the provider key is not set.
        """
        if not self.data_dir.is_dir():
            raise ConfigurationError(
                f"Data folder not found: {self.data_dir.resolve()}. Run the command from the "
                "project root or set EMPORIO_DATA_DIR."
            )
        key_names = PROVIDER_API_KEYS.get(self.provider, ())
        if key_names and not any(os.environ.get(name) for name in key_names):
            raise ConfigurationError(
                f"{' or '.join(key_names)} is not set. Add it to .env or pick another provider "
                "in EMPORIO_MODEL."
            )
