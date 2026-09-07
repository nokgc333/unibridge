"""hou/bpyへの依存をここに閉じ込めるアダプタ層（Ports & Adapters, ADR-0002）。

このパッケージは実Houdini(hython)/実Blender(blender --background)でのみ
importできるモジュールを含む。pyproject.tomlの[tool.mypy] exclude、
[tool.coverage.run] omitにより、CIの型チェック・カバレッジ計測から除外している。
"""
