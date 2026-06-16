import pytest

from reddit_pain_search.config import AppConfig, load_config


def test_load_config_from_mapping():
    config = load_config(
        {
            "MOONSHOT_API_KEY": "moonshot",
            "KIMI_MODEL": "kimi for coding",
        }
    )

    assert config.web_access_proxy_url == "http://localhost:3456"
    assert config.kimi_model == "kimi for coding"
    assert config.database_path == "reddit_pain_search.sqlite3"


def test_load_config_rejects_missing_secret():
    with pytest.raises(ValueError, match="MOONSHOT_API_KEY is required"):
        load_config({})


def test_config_repr_does_not_expose_secrets():
    config = AppConfig(
        moonshot_api_key="moonshot-secret",
        kimi_model="kimi for coding",
    )

    rendered = repr(config)
    assert "moonshot-secret" not in rendered
