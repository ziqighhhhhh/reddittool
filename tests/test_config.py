import pytest

from reddit_pain_search.config import AppConfig, load_config


def test_load_config_from_mapping():
    config = load_config(
        {
            "REDDIT_CLIENT_ID": "client",
            "REDDIT_CLIENT_SECRET": "secret",
            "REDDIT_USER_AGENT": "agent",
            "MOONSHOT_API_KEY": "moonshot",
            "KIMI_MODEL": "kimi for coding",
        }
    )

    assert config.reddit_client_id == "client"
    assert config.kimi_model == "kimi for coding"
    assert config.database_path == "reddit_pain_search.sqlite3"


def test_load_config_rejects_missing_secret():
    with pytest.raises(ValueError, match="MOONSHOT_API_KEY is required"):
        load_config(
            {
                "REDDIT_CLIENT_ID": "client",
                "REDDIT_CLIENT_SECRET": "secret",
                "REDDIT_USER_AGENT": "agent",
            }
        )


def test_config_repr_does_not_expose_secrets():
    config = AppConfig(
        reddit_client_id="client",
        reddit_client_secret="super-secret",
        reddit_user_agent="agent",
        moonshot_api_key="moonshot-secret",
        kimi_model="kimi for coding",
    )

    rendered = repr(config)
    assert "super-secret" not in rendered
    assert "moonshot-secret" not in rendered
