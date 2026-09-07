# ADR-0004: CLIと簡易Web GUIの両方を提供する設計

## Status
Accepted (2026-09-07)

## Context
UniBridgeの利用者として、パイプラインTDやスクリプトを書ける開発者（CLI操作・CI/CD組み込みを好む層）と、差分レポートを確認したいだけのアーティスト・プロデューサー（ブラウザでの結果閲覧を好む層）の両方を想定している。姉妹プロジェクトPipeBoard miniはNext.js + FastAPIによる本格的なWebアプリケーションだったが、UniBridgeのWeb GUIに同等の技術スタックが必要かどうかを検討した。

## Decision
CLI（`cli.py`, `cli_houdini_entry.py`, `cli_blender_entry.py`）を主要インターフェースとしつつ、FastAPI + 静的HTML/fetchによる最小限の簡易Web GUI（`webui/`）を追加で提供する。PipeBoard miniのようなNext.jsベースのフル機能SPAは採用しない。

## Consequences

良い:
- CLIはCI/CDへの組み込み、スクリプト連携がしやすく、開発者にとって最も高速な導線になる。
- 簡易Web GUIは「USDファイルをアップロードして結果を見る」という単一の情報表示フローに閉じているため、FastAPI + 静的HTML/fetchで要件を十分満たせる。フル機能SPAに必要な複雑な状態管理・クライアントサイドルーティングを持ち込む必要がない。
- 過剰な技術選定を避けたことで、「要件に対して適切な実装規模を選ぶ」というスコープ管理能力自体を面接で説明できる材料になる。

悪い:
- 静的HTML/fetchベースのフロントは、将来的に画面数が増えた場合の拡張性がNext.jsに劣る。
- 2つのインターフェース（CLI/Web GUI）を両方保守するコストが、CLIのみの場合より増える。

## Alternatives Considered
- **CLIのみで簡易Web GUIを持たない**: 実装コストは最も低いが、元企画書で明示された「CLIと簡易GUI(Web)両方に対応」という要件（BR-005）を満たさず、非開発者への見せ方という観点でポートフォリオとしての訴求力が下がるため却下。
- **PipeBoard miniと同様のNext.js + FastAPI構成**: UniBridgeが扱う画面はUSDファイルのアップロードと結果表示のみであり、Next.jsが提供するルーティング・SSR等の恩恵をほとんど活用できない。技術スタックの重複よりも「要件に対する実装規模の適切さ」を優先し、静的HTML/fetch + FastAPIを選定した。
