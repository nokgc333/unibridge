# ADR-0006: 標準検査は usdchecker を使わず、usd-core だけで実装する

- 状態: 採用
- 日付: 2026-10-27

## 背景

USD の標準的な準拠検査には `UsdUtils.ComplianceChecker`(usdchecker)がある。この検査を取り込む案があった。

`usd-core`(PyPI の `pxr`)の配布物には、`ComplianceChecker` が含まれていない(26.11 で確認。`pxr.UsdUtils` に属性が無い)。完全な USD のビルドが要る。

## 決定

`usd-core` だけで確かめられる観点を、`core/integrity_check.py` に自前で実装する。

- 既定 Prim の有無
- 解決できない参照(`UsdUtils.ComputeAllDependencies`)
- マテリアルの割り当て(親からの継承、割り当て先の実在)
- UV(primvar `st`)
- variant の選択
- purpose の値

## 理由

- 配布の簡単さ(`pip install` だけで動く)が、このツールの強み。完全な USD のビルドを要求すると失われる
- 検査は読み取り専用で、Stage を変えない([ADR-0005](0005-report-only-no-autofix.md))
- `core/` は `hou` / `bpy` に依存しない([ADR-0002](0002-dual-adapter-architecture.md))

## 結果

- usdchecker の全ルールは網羅しない。型・スキーマの厳密な検査が要る場合は、`usdchecker` を別に実行する
- 将来 `usd-core` に `ComplianceChecker` が入った場合は、この ADR を見直し、同じ `DiffCategory` で取り込む
