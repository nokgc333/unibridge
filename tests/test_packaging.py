"""配布に関わる設定のテスト(インストール後も動くこと、メタデータが実態と合うこと)。"""

from __future__ import annotations

import tomllib
from pathlib import Path

from core.rules import DEFAULT_RULES_PATH
from webui.main import STATIC_DIR

PYPROJECT = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
PROJECT = PYPROJECT["project"]


def test_the_default_rules_live_inside_the_package_and_exist() -> None:
    assert DEFAULT_RULES_PATH.is_file()
    assert DEFAULT_RULES_PATH.parent.name == "core"


def test_the_static_files_of_the_web_ui_are_found_next_to_the_module() -> None:
    assert (STATIC_DIR / "index.html").is_file()
    assert STATIC_DIR.parent.name == "webui"


def test_the_data_files_are_declared_as_package_data() -> None:
    package_data = PYPROJECT["tool"]["setuptools"]["package-data"]

    assert "default_rules.yaml" in package_data["core"]
    assert "static/*" in package_data["webui"]


def test_the_cli_module_is_shipped_and_exposed_as_a_command() -> None:
    assert "cli" in PYPROJECT["tool"]["setuptools"]["py-modules"]
    assert PROJECT["scripts"]["unibridge"] == "cli:main"


def test_the_description_says_consistency_checking_not_conversion() -> None:
    assert "整合" in PROJECT["description"]
    assert "相互変換" not in PROJECT["description"]


def test_the_version_matches_the_latest_changelog_entry() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert f"## [{PROJECT['version']}]" in changelog


def test_the_metadata_a_package_index_shows_is_filled_in() -> None:
    assert PROJECT["license"] == "MIT"
    assert PROJECT["classifiers"]
    assert PROJECT["keywords"]
    assert {"Homepage", "Repository", "Changelog"} <= set(PROJECT["urls"])


def test_the_ci_runs_the_tests_on_three_operating_systems_and_three_pythons() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    for name in ("ubuntu-latest", "macos-latest", "windows-latest", '"3.11"', '"3.12"', '"3.13"'):
        assert name in ci


def test_the_release_workflow_publishes_by_trusted_publishing_without_a_token() -> None:
    release = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "id-token: write" in release
    assert "pypa/gh-action-pypi-publish" in release
    assert "password" not in release


def test_automatic_updates_cover_python_packages_and_actions() -> None:
    dependabot = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: pip" in dependabot
    assert "package-ecosystem: github-actions" in dependabot


def test_the_lock_file_and_the_pre_commit_config_exist() -> None:
    assert Path("uv.lock").is_file()
    assert "gitleaks" in Path(".pre-commit-config.yaml").read_text(encoding="utf-8")
