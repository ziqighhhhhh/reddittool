import pytest

from reddit_pain_search.config import AppConfig, load_config


def test_load_config_from_mapping():
    config = load_config(
        {
            "LLM_API_KEY": "dashscope-key",
            "LLM_MODEL": "qwen3.7-plus",
            "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
    )

    assert config.web_access_proxy_url == "http://localhost:3456"
    assert config.llm_model == "qwen3.7-plus"
    assert config.llm_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.database_path == "reddit_pain_search.sqlite3"


def test_load_config_rejects_missing_secret():
    with pytest.raises(ValueError, match="LLM_API_KEY or DASHSCOPE_API_KEY"):
        load_config({})


def test_config_repr_does_not_expose_secrets():
    config = AppConfig(
        llm_api_key="dashscope-secret",
        llm_model="qwen3.7-plus",
    )

    rendered = repr(config)
    assert "dashscope-secret" not in rendered


def test_load_config_prefers_dotenv_over_existing_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "stale-key")
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "LLM_API_KEY=fresh-key",
                "LLM_MODEL=qwen3.7-plus",
                "LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config()

    assert config.llm_api_key.get_secret_value() == "fresh-key"


def test_load_config_accepts_dashscope_api_key_alias():
    config = load_config({"DASHSCOPE_API_KEY": "dashscope-key"})

    assert config.llm_api_key.get_secret_value() == "dashscope-key"
    assert config.llm_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
