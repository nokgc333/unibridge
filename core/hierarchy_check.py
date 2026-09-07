"""Xform/Prim階層の命名規則チェック（仕様書§5.3, §8.4）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pxr import Usd

from core.report_models import DiffCategory, DiffEntry, Severity


@dataclass(frozen=True)
class NamingRule:
    pattern: re.Pattern[str]
    applies_to_prim_type: str
    description: str
    rename_hint: str | None = None


def _applicable_rule(prim_type: str, rules: list[NamingRule]) -> NamingRule | None:
    """Prim種別に対応する規則を1件返す。

    "all"にマッチする規則はフォールバックとして最後に評価する
    （具体的なprim_type一致を優先し、"all"は最後の手段とする）。
    """
    for rule in rules:
        if rule.applies_to_prim_type == prim_type:
            return rule
    for rule in rules:
        if rule.applies_to_prim_type == "all":
            return rule
    return None


def check_naming(
    stage: Usd.Stage, rules: list[NamingRule], exclude_patterns: list[re.Pattern[str]]
) -> list[DiffEntry]:
    """Stage内の全Primを走査し、命名規則に違反するPrimを検出する。

    exclude_patternsに一致するPrimパスは検証対象から除外する（要件定義書§3.3）。
    適用可能な規則が存在しないPrim種別はスキップする（規則を課さない、仕様書§4.4）。
    """
    entries: list[DiffEntry] = []

    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        if any(pattern.search(path) for pattern in exclude_patterns):
            continue

        rule = _applicable_rule(prim.GetTypeName(), rules)
        if rule is None:
            continue

        if rule.pattern.match(path) is None:
            hint = f" (hint: {rule.rename_hint})" if rule.rename_hint else ""
            entries.append(
                DiffEntry(
                    category=DiffCategory.NAMING_VIOLATION,
                    target_path=path,
                    message=(
                        f"prim '{path}' (type={prim.GetTypeName()}) violates naming rule: "
                        f"{rule.description}{hint}"
                    ),
                    severity=Severity.WARNING,
                )
            )

    return entries
