# ADR-0003: Blender bpy経由での実シーン階層検証を行う設計

## Status
Accepted (2026-09-07)

## Context
USD自体（`.usd`/`.usda`/`.usdc`ファイルとそのコンポジション）は、`usd-core`（`pxr`モジュール）だけで完全に読み書き・検証できる、DCC非依存のデータである。したがって「USDファイル同士の静的な比較」だけであれば、Blenderの`bpy`を経由する必要はなく、`core/`層だけで完結できるはずである。

しかし本プロジェクトが検証したい不整合（座標系・スケール単位の不一致、階層構造の変化）は、静的なUSDファイルの比較だけでは捉えきれない側面を持つ。具体的には、「BlenderのUSD I/Oが実際にどうUSDファイルを解釈し、Blenderの内部シーングラフ（`bpy.data.objects`等）に反映するか」というDCC側の変換挙動そのものが、実務上の事故の原因になりうる（例: BlenderのUSD I/Oがインポート時に独自の座標変換を適用し、結果としてUSDファイル上のupAxisメタデータと、Blender内で実際に見える向きが食い違うケース）。

## Decision
`adapters/blender_adapter.py`にて、`bpy.ops.wm.usd_import()`で実際にBlenderへUSDを読み込み、読込後のBlenderシーン階層（`bpy.data.objects`）を検証対象に含める。読込直後に`bpy.ops.wm.usd_export()`で再エクスポートし、元のUSDファイルとの差分比較（`core/diff_report.py`）にも利用する「往復（round-trip）検証」の設計とする。

## Consequences

良い:
- USDファイル単体の検証では発見できない、DCC側の変換挙動に起因する不整合（Blenderの読込・書出しの往復で失われる/変化する情報）を検出できる。
- 実際のBlenderシーンとして開いた状態を検証することで、「机上のフォーマット比較」ではなく「実務での使われ方」に即した検証ツールとしての説得力が増す。

悪い:
- `blender_adapter.py`自体はBlender実機（`blender --background`）でしかテストできず、`core/`層に比べてCIでの自動検証ができない（手動E2Eに依存、ADR-0002と同じトレードオフ）。
- Blenderのバージョンによって USD I/O の挙動が変わりうるため、動作環境（要件定義書§4.1）を明示的に固定する必要がある。

## Alternatives Considered
- **usd-coreのみでの静的比較に限定し、bpyを一切使わない設計**: 実装がシンプルになり完全にCI自動化できる利点はあるが、「BlenderのUSD I/Oが実際にどう解釈するか」という、実務で最も事故が起きやすいポイントを検証できなくなる。本プロジェクトの目的（DCC間往来での実務的な不整合の検出）に反するため却下。
