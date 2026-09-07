# ADR-0002: Ports & Adaptersの発展形として2アダプタ構成を採用

## Status
Accepted (2026-09-07)

## Context
姉妹プロジェクトScene Doctorでは、Houdiniの`hou`モジュールへの依存を`adapters/hou_adapter.py`という単一のアダプタに閉じ込め、検証ロジック（`checks/`）を`hou`から完全に分離するPorts & Adaptersパターンを採用した（Scene Doctor ADR-0001）。これにより、Houdiniライセンスなしのローカル/CI環境でも検証ロジックをpytestで検証できるようになった。

UniBridgeはHoudiniとBlenderという2つの異なるDCCを橋渡しするツールであり、Scene Doctorと同じ1アダプタ構成では対応できない。Houdini側の`hou`（HOM）とBlender側の`bpy`という、互いに非互換な2つのDCC APIへの依存を、どのように整理するかを検討した。

## Decision
`adapters/houdini_adapter.py`（`hou`依存、hython専用）と`adapters/blender_adapter.py`（`bpy`依存、`blender --background`専用）という、独立した2つのアダプタを設ける。`core/`層（`scale_check.py` / `hierarchy_check.py` / `diff_report.py`）は、USDそのもの（`usd-core`の`pxr`モジュール）にのみ依存し、`hou`・`bpy`のいずれもimportしない境界を厳格に維持する。両アダプタはいずれも「DCC上のシーンからUSDファイルを入出力する」という共通の契約（USDファイルパスの入出力）のみを`core/`に対して満たせばよく、アダプタ同士が互いを意識する必要はない。

## Consequences

良い:
- `core/`層はHoudini・Blenderいずれの実機もない環境（CI含む）で完全にpytestが完結する（Scene DoctorのADR-0001の恩恵をそのまま継承）。
- 将来的に3つ目のDCC（Unreal Engine, Maya等）への対応が必要になっても、新しいアダプタを追加するだけで済み、`core/`層への変更は不要（要件定義書§16.6 Q3で説明する拡張性）。
- 「複数のDCCが同じ中心的なドメインロジックを共有しながら独立に差し替え可能」という、Ports & Adaptersパターン本来の目的（アダプタの差し替え可能性）を、1アダプタ構成よりも強く体現できる。

悪い:
- アダプタが2つになることで、Scene Doctorに比べ実装・保守すべきコード量が増える。
- 2つのアダプタそれぞれがHoudini実機・Blender実機でしかテストできず、手動E2Eの範囲がScene Doctorより広くなる。

## Alternatives Considered
- **単一アダプタで両DCCを扱う（`adapters/dcc_adapter.py`に`hou`/`bpy`両方をimportし、実行時にどちらか片方だけを使う）**: 実行時に使わない側のimportが必ず失敗する（Houdini実行時に`bpy`は存在せず、Blender実行時に`hou`は存在しない）ため、モジュールレベルのimportエラーを回避する分岐処理が複雑化する。DCCごとに完全に独立したプロセス（hython / blender --background）で実行される以上、ファイルも分離した方が構造として自然だと判断し却下。
- **アダプタを設けず、core/層に直接hou/bpyを条件分岐でimportさせる**: Scene Doctorで確立したPorts & Adaptersの原則（検証ロジックのDCC非依存化）に反し、CIでのテスト可能性を損なうため却下。
