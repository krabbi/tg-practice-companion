"""Tests for web admin docker-compose profile (AC-19, AC-15)."""

from pathlib import Path

import yaml


def _load_compose() -> dict:
    """Parse the root docker-compose.yml."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    with compose_path.open() as f:
        return yaml.safe_load(f)


def test_web_service_exists_under_web_profile() -> None:
    compose = _load_compose()
    assert "web" in compose["services"]
    web = compose["services"]["web"]
    assert "web" in web.get("profiles", [])


def test_nginx_service_exists_under_web_profile() -> None:
    compose = _load_compose()
    assert "nginx" in compose["services"]
    nginx = compose["services"]["nginx"]
    assert "web" in nginx.get("profiles", [])


def test_nginx_port_uses_nginx_port_variable() -> None:
    compose = _load_compose()
    nginx = compose["services"]["nginx"]
    ports = [str(p) for p in nginx.get("ports", [])]
    assert any("NGINX_PORT" in p for p in ports), (
        f"nginx ports must reference NGINX_PORT variable, got: {ports}"
    )


def test_nginx_maps_to_port_80() -> None:
    compose = _load_compose()
    nginx = compose["services"]["nginx"]
    ports = [str(p) for p in nginx.get("ports", [])]
    assert any(p.endswith(":80") for p in ports), (
        f"nginx must map to container port 80, got: {ports}"
    )


def test_web_jwt_secret_env_driven() -> None:
    compose = _load_compose()
    env = compose["services"]["web"]["environment"]
    value = str(env.get("JWT_SECRET", ""))
    assert value.startswith("${"), f"JWT_SECRET must use env substitution, got: {value!r}"


def test_web_cors_origins_env_driven() -> None:
    compose = _load_compose()
    env = compose["services"]["web"]["environment"]
    value = str(env.get("CORS_ORIGINS", ""))
    assert value.startswith("${"), f"CORS_ORIGINS must use env substitution, got: {value!r}"


def test_web_no_secrets_hardcoded() -> None:
    compose = _load_compose()
    web_env = compose["services"]["web"].get("environment", {})
    # Check all env values that are present — none may be a literal secret.
    # POSTGRES_PASSWORD is intentionally absent as a standalone key (it is
    # embedded in DATABASE_URL via ${POSTGRES_PASSWORD} substitution).
    secret_keys = ["JWT_SECRET", "TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY"]
    for key in secret_keys:
        value = str(web_env.get(key, ""))
        assert value.startswith("${"), (
            f"{key} appears hardcoded in web service environment: {value!r}"
        )


def test_nginx_mounts_frontend_dist() -> None:
    compose = _load_compose()
    nginx = compose["services"]["nginx"]
    volumes = [str(v) for v in nginx.get("volumes", [])]
    assert any("frontend/dist" in v for v in volumes), (
        f"nginx must mount frontend/dist, got volumes: {volumes}"
    )


def test_nginx_mounts_nginx_conf() -> None:
    compose = _load_compose()
    nginx = compose["services"]["nginx"]
    volumes = [str(v) for v in nginx.get("volumes", [])]
    assert any("nginx.conf" in v for v in volumes), (
        f"nginx must mount nginx/nginx.conf, got volumes: {volumes}"
    )


def test_nginx_depends_on_web() -> None:
    compose = _load_compose()
    nginx = compose["services"]["nginx"]
    depends = nginx.get("depends_on", [])
    if isinstance(depends, dict):
        assert "web" in depends
    else:
        assert "web" in depends


def test_web_profile_no_host_port_exposed() -> None:
    """web service is only accessible via nginx — no direct host port mapping."""
    compose = _load_compose()
    web = compose["services"]["web"]
    assert "ports" not in web, "web service must not expose ports directly; nginx proxies to it"
