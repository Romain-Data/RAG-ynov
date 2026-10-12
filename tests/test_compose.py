"""The preprod compose file must stay a copy of the production one, host folders aside."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROD = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
PREPROD = yaml.safe_load((ROOT / "docker-compose.preprod.yml").read_text())


def _host_folders(compose: dict) -> list[str]:
    return [v.split(":")[0] for v in compose["services"]["api"]["volumes"] if v.startswith("/")]


def _without_api_volumes(compose: dict) -> dict:
    api = {k: v for k, v in compose["services"]["api"].items() if k != "volumes"}
    return {**compose, "services": {**compose["services"], "api": api}}


def test_preprod_matches_production_apart_from_api_volumes() -> None:
    assert _without_api_volumes(PREPROD) == _without_api_volumes(PROD)


def test_preprod_mounts_the_same_targets() -> None:
    def targets(compose: dict) -> list[str]:
        return [v.split(":")[1] for v in compose["services"]["api"]["volumes"]]

    assert targets(PREPROD) == targets(PROD)


def test_preprod_never_mounts_production_folders() -> None:
    prod_folders = set(_host_folders(PROD))
    assert prod_folders
    assert not prod_folders & set(_host_folders(PREPROD))


def test_api_receives_the_deployed_commit() -> None:
    """Coolify sets SOURCE_COMMIT for the compose file (when "Include Source Commit in Build"
    is on), not in the container: /api/health and answer_log.app_version only see it when the
    compose file passes it on. The preprod file follows (test above)."""
    assert "SOURCE_COMMIT=${SOURCE_COMMIT:-}" in PROD["services"]["api"]["environment"]
