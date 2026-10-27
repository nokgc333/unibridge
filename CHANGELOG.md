# Changelog

形式は [Keep a Changelog](https://keepachangelog.com/) に、版の付け方は [Semantic Versioning](https://semver.org/) に従う。

## [0.2.0] - 2026-10-27

### Added

- `integrity-check` コマンド: 既定 Prim・解決できない参照・マテリアルの割り当て・UV・variant の選択・purpose の検査
- ツール間で共通のレポート形式(JSON スキーマ付き)
- Blender 3.5.1 / 3.6.0 / 4.0.0 / 4.5.3 / 5.0.0 の実機検証の記録と、再実行用のスクリプト
- 10 万 Prim までの性能計測
- `unibridge` コマンド(インストール後に使える)

### Changed

- CLI を、コマンドごとのモジュール(`commands/`)に分割
- 既定の命名規則を `core/default_rules.yaml` に移し、パッケージに同梱(インストール後も動く)
- 壊れた USD を渡しても、スタックトレースを出さず、終了コード 10 で終わる
- 変換の書き出しに失敗したとき、終了コード 14 で終わる

### Fixed

- Web UI の静的ファイルを、作業ディレクトリに依らず配信する

## [0.1.0]

- 最初の版: `diff` / `scale-check` / `hierarchy-check` / `batch`、簡易 Web UI、Houdini・Blender のアダプタ
