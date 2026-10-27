# Blender 5.0.0 の実機検証

> 実施日: 2026-10-27
> 環境: macOS(Apple Silicon)/ `/Applications/Blender_v5.0.0.app`(`--background --factory-startup`)
> 対象: `adapters/blender_adapter.py`

## コマンド

```bash
/Applications/Blender_v5.0.0.app/Contents/MacOS/Blender --background --factory-startup --python scripts/verify_blender.py
```

## 結果(全 5 項目 PASS)

```text
import_creates_objects PASS objects=['geo_body', 'root', 'xform_hero']
default_scene_is_cleared PASS 
reexport_writes_file PASS re.usda
reexport_up_axis_is_z PASS upAxis = "Z"
missing_file_is_refused PASS '/Users/naokikaneko/dev/unibridge/sample_scenes/missing.usda
```

## 観察

- `sample_scenes/consistent_scene.usda`(`upAxis = "Y"`)を読み込んで再エクスポートすると、出力の `upAxis` は `Z` になる(Blender の内部座標系に合わせて書き出すため。[ADR-0003](../adr/0003-bpy-for-scene-hierarchy-validation.md))。
