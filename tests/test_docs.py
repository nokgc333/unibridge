"""README・ADR・サンプルレポートが、実態と合っていることのテスト。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

README = Path("README.md").read_text(encoding="utf-8")
ADR_DIR = Path("docs/adr")


def test_there_are_at_least_seven_adrs_and_each_is_listed_in_the_readme() -> None:
    adrs = sorted(ADR_DIR.glob("*.md"))

    assert len(adrs) >= 7
    for adr in adrs:
        assert f"docs/adr/{adr.name}" in README, adr.name


def test_every_image_in_the_readme_exists() -> None:
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", README)

    assert len(images) >= 3
    for image in images:
        assert Path(image).is_file(), image


def test_every_relative_link_in_the_readme_points_to_a_file() -> None:
    links = re.findall(r"(?<!!)\[[^\]]*\]\((docs/[^)#]+|[A-Z_]+\.md)", README)

    for link in links:
        assert Path(link).exists(), link


def test_the_sample_integrity_report_follows_the_shared_schema() -> None:
    schema = json.loads(Path("docs/schema/common-report.schema.json").read_text(encoding="utf-8"))
    sample = json.loads(Path("docs/samples/integrity-check.json").read_text(encoding="utf-8"))

    jsonschema.validate(sample, schema)


def test_the_sample_diff_reports_exist_in_all_three_formats() -> None:
    stem = "consistent_scene_vs_changed_structure"

    for ext in ("csv", "json", "html"):
        assert Path(f"docs/samples/{stem}.{ext}").is_file()


def test_the_readme_has_an_english_summary() -> None:
    assert "English summary" in README
