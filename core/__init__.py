"""UniBridge core層: DCC(Houdini/Blender)非依存の検証ロジック。

usd-core（pxr）にのみ依存し、hou/bpyを一切importしない
（Ports & Adapters境界、docs/adr/0002-dual-adapter-architecture.md）。
"""
