from pathlib import Path

import pytest
from pydantic import ValidationError

from emporio_agent.application.agent import create_chat_model
from emporio_agent.config import Settings
from emporio_agent.errors import ConfigurationError

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_model_needs_a_provider():
    with pytest.raises(ValidationError):
        Settings(model="claude-sonnet-5-5")


def test_provider_is_read_from_the_model():
    assert Settings(model="openai:some-model").provider == "openai"


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        Settings(model="anthropic:claude-sonnet-5-5", data_dir=DATA_DIR).check_ready_to_chat()


def test_missing_data_folder_is_reported(tmp_path):
    with pytest.raises(ConfigurationError, match="Data folder"):
        Settings(data_dir=tmp_path / "nothing").check_ready_to_chat()


def test_local_providers_do_not_need_a_key():
    Settings(model="ollama:llama3", data_dir=DATA_DIR).check_ready_to_chat()


def test_unknown_provider_is_a_configuration_error():
    with pytest.raises(ConfigurationError):
        create_chat_model("not_a_provider:model")


def test_empty_temperature_means_model_default(monkeypatch):
    monkeypatch.setenv("EMPORIO_TEMPERATURE", "")

    assert Settings().temperature is None


def test_gemini_accepts_either_key_name(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    Settings(model="google_genai:gemini-flash-latest", data_dir=DATA_DIR).check_ready_to_chat()


def test_gemini_without_any_key_names_both(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="GOOGLE_API_KEY or GEMINI_API_KEY"):
        Settings(model="google_genai:gemini-flash-latest", data_dir=DATA_DIR).check_ready_to_chat()


def test_rate_limit_is_attached_to_the_model(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    model = create_chat_model("google_genai:gemini-3.5-flash", requests_per_minute=5)

    assert model.rate_limiter is not None
