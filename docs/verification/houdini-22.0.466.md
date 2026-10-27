# Houdini 22.0.466(Indie)の実機検証

> 実施日: 2026-10-27
> 環境: macOS(Apple Silicon)/ Steam 版 Houdini Indie 22.0.466 の `hython`(Steam を起動した状態)
> 対象: `adapters/houdini_adapter.py`

## コマンド

```bash
hython scripts/verify_houdini.py
```

## 結果(全 7 項目 PASS)

```text
list_lop_children PASS count=3
export_usda PASS out.usda
export_usdc PASS out.usdc
export_has_real_prims PASS 
export_has_no_anonymous_sublayer PASS 
missing_node PASS '/stage/none' does not exist
not_a_lop_node PASS '/obj' is not a LOP node
```

## 観察

- 出力が終わっても `hython` が終了しないことがある。結果が出たあとに、手で止めてよい
- 22.0.429 の記録の不具合(匿名 sublayer のみが書き出される)は、再発していない(`export_has_no_anonymous_sublayer`)
