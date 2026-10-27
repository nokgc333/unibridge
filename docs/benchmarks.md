# 性能の計測結果

`python tests/benchmark.py` の出力。`usd-core` だけで動き、Houdini・Blender は要らない。生成した Stage(Xform・Mesh・Material の組)に対し、検査ごとの所要時間を測る。

> 計測環境: Python 3.12.3 / macOS arm64(Apple Silicon)
> 計測日: 2026-10-27
> 値は 1 回の実行の実測で、環境により変わる。傾向(Prim 数にほぼ比例)を見るためのもの。

| Prim 数 | open | metadata | naming | integrity | diff |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,999 | 0.006 s | 0.000 s | 0.006 s | 0.042 s | 0.011 s |
| 19,999 | 0.050 s | 0.004 s | 0.067 s | 0.382 s | 0.116 s |
| 100,000 | 0.282 s | 0.019 s | 0.334 s | 1.953 s | 0.588 s |

## 読み方

- 要件(NFR-001): Prim 数 2,000 規模で 15 秒以内。実測は全検査の合計で 0.07 秒前後で、約 200 倍の余裕がある。
- どの検査も Prim 数にほぼ比例して増える(2,000 → 100,000 で約 50 倍の Prim に対し、`integrity` は約 46 倍)。
- 最も重いのは `integrity`(Mesh ごとの primvar・マテリアル割り当ての確認と、親をたどる継承の判定)。10 万 Prim でも 2 秒未満。
- `metadata` は Stage のメタデータと Prim 数を数えるだけなので、規模にほぼ依らない。

## 再現

```bash
python tests/benchmark.py
```
