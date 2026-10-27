# 実機検証の記録

DCC 本体(Blender・Houdini)でしか確かめられないことを、版ごとに残す。`adapters/` は `hou` / `bpy` が無い環境では動かないため、CI では呼び出しの契約だけを確かめる(`tests/test_adapters_contract.py`)。実機での動作は、ここの記録が根拠になる。

## 記録の一覧

| 対象 | 実施日 | 結果 | 記録 |
| --- | --- | --- | --- |
| Blender 3.5.1 | 2026-10-27 | 5/5 PASS | [blender-3.5.1.md](blender-3.5.1.md) |
| Blender 3.6.0 | 2026-10-27 | 5/5 PASS | [blender-3.6.0.md](blender-3.6.0.md) |
| Blender 4.0.0 | 2026-10-27 | 5/5 PASS | [blender-4.0.0.md](blender-4.0.0.md) |
| Blender 4.5.3 LTS | 2026-10-27 | 5/5 PASS | [blender-4.5.3.md](blender-4.5.3.md) |
| Blender 5.0.0 | 2026-10-27 | 5/5 PASS | [blender-5.0.0.md](blender-5.0.0.md) |
| Houdini 22.0.429 Indie | 2026-09-08 | 全項目 PASS | [houdini-22.0.429.md](houdini-22.0.429.md) |
| Houdini 22.0.466 Indie | 2026-10-27 | 7/7 PASS | [houdini-22.0.466.md](houdini-22.0.466.md) |

## 手順

| 対象 | スクリプト | 実行 |
| --- | --- | --- |
| Blender | `scripts/verify_blender.py` | `blender --background --factory-startup --python scripts/verify_blender.py` |
| Houdini | `scripts/verify_houdini.py` | `hython scripts/verify_houdini.py`(Steam 版は Steam を起動しておく) |

スクリプトは、1 行 1 項目の `CHECK <名前> <PASS|FAIL> <詳細>` を出力する。

## 新しい版を追加するとき

1. 上のスクリプトを実行し、すべて `PASS` であることを確かめる
2. `blender-<版>.md` または `houdini-<版>.md` として、日付・環境・コマンド・出力を記録する
3. この表に 1 行足す
4. `FAIL` があれば、原因を直すか、記録に理由を残す。直したときは契約テストを足して、再発を防ぐ
