# Houdini 22.0.429(Indie)の実機検証

> 実施日: 2026-09-08(最初の検証)
> 環境: macOS / Steam 版 Houdini Indie 22.0.429 の `hython`
> 対象: `adapters/houdini_adapter.py`

## 結果

| 項目 | 結果 |
| --- | --- |
| `list_lop_children("/stage")` が、作った 3 ノードのパスを返す | PASS |
| `export_stage_from_lop()` で usda・usdc の両方に書き出せる | PASS |
| 書き出したファイルに実際の Prim(`sphere1` `grid1`)がある | PASS |
| 存在しないノード・LOP でないノード(`/obj`)で `LopNodeNotFoundError` | PASS |
| 書き出したファイルを `python cli.py scale-check` が読める | PASS |

## この検証で見つかった不具合(修正済み)

`stage.GetRootLayer().Export()` は、匿名の sublayer への参照だけを書き出し、Prim が空になる。合成済みの Stage を書き出す `stage.Export()` に直した。再発しないことは、契約テスト(`tests/test_adapters_contract.py`)が固定している。

## 再実行

Houdini Indie は、Steam が起動していないとライセンスを取得できず、`hython` が終了コード 3 で止まる。Steam を起動したうえで、次を実行する。

```bash
hython scripts/verify_houdini.py
```

出力の `CHECK` 行を、版ごとの記録としてこのフォルダに追加する。
