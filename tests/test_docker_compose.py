"""Tests for docker-compose.yml production deployment configuration (AC-15)."""

from pathlib import Path

import yaml


def _load_compose() -> dict:
    """Parse the root docker-compose.yml."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    with compose_path.open() as f:
        return yaml.safe_load(f)


def test_db_service_uses_postgres16() -> None:
    compose = _load_compose()
    assert compose["services"]["db"]["image"] == "postgres:16"


def test_db_name_is_practice() -> None:
    compose = _load_compose()
    env = compose["services"]["db"]["environment"]
    assert env["POSTGRES_DB"] == "practice"


def test_db_volume_is_practice_pgdata() -> None:
    compose = _load_compose()
    volumes_section = compose.get("volumes", {})
    assert "practice_pgdata" in volumes_section

    db_volumes = compose["services"]["db"]["volumes"]
    assert any("practice_pgdata" in v for v in db_volumes)


def test_db_healthcheck_present() -> None:
    compose = _load_compose()
    assert "healthcheck" in compose["services"]["db"]


def test_bot_uses_ghcr_image() -> None:
    compose = _load_compose()
    bot_service = compose["services"]["bot"]
    assert bot_service.get("image") == "ghcr.io/krabbi/tg-practice-companion:latest"
    # Prod bot must NOT build locally — it pulls from the registry
    assert "build" not in bot_service


def test_bot_database_url_uses_env_substitution() -> None:
    compose = _load_compose()
    db_url = compose["services"]["bot"]["environment"]["DATABASE_URL"]
    # Must reference POSTGRES_PASSWORD via variable substitution, not a literal value
    assert "${POSTGRES_PASSWORD}" in db_url
    # Must point to the db service by hostname
    assert "@db/" in db_url


def test_bot_secrets_are_env_based_not_hardcoded() -> None:
    """No real secrets must be baked into the compose file (AC-15)."""
    compose = _load_compose()
    bot_env = compose["services"]["bot"].get("environment", {})

    secret_keys = [
        "TELEGRAM_BOT_TOKEN",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "ALLOWED_USER_IDS",
        "POSTGRES_PASSWORD",
    ]
    for key in secret_keys:
        value = str(bot_env.get(key, ""))
        # Value must be a variable substitution expression, not a plain literal secret
        assert value.startswith("${"), (
            f"{key} appears to be hardcoded in docker-compose.yml: {value!r}"
        )


def test_bot_depends_on_db_healthy() -> None:
    compose = _load_compose()
    depends = compose["services"]["bot"]["depends_on"]
    assert "db" in depends
    assert depends["db"]["condition"] == "service_healthy"


def test_bot_service_has_restart_policy() -> None:
    compose = _load_compose()
    assert compose["services"]["bot"].get("restart") == "unless-stopped"


def test_watchtower_service_present() -> None:
    compose = _load_compose()
    assert "watchtower" in compose["services"]


def test_watchtower_uses_profile() -> None:
    compose = _load_compose()
    watchtower = compose["services"]["watchtower"]
    assert "watchtower" in watchtower.get("profiles", [])
