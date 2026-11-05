---
title: Hiệu năng của scraper
short_title: Hiệu năng
label: m1-perf
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

:::{note} Phụ trách: Hiền
:::

# Hiệu năng của scraper

*(Môi trường đo: Colab CPU-only hay máy nào; số run; cold/warm cache; ngày đo.)*

```{code-cell} python
:tags: [remove-input]
import sys, pathlib
for _p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
    if (_p / "bookdata.py").exists():
        sys.path.insert(0, str(_p)); break
import bookdata as bd
import pandas as pd
import matplotlib.pyplot as plt
```

## Thời gian chạy

```{code-cell} python
:tags: [remove-input]
ev = bd.events
if len(ev):
    fin = ev[(ev["event"] == "finished") & ev["duration_s"].notna()]
    t = (fin.groupby("stage")["duration_s"].agg(["count", "sum", "mean", "max"]).round(2)
         .rename(columns={"count": "Số thao tác", "sum": "Tổng (s)",
                          "mean": "Trung bình (s)", "max": "Lớn nhất (s)"}))
    display(t)
    ax = t["Trung bình (s)"].drop(["pipeline"], errors="ignore").plot.barh(figsize=(6, 3), color="#B279A2")
    ax.set(xlabel="giây", title="Thời gian trung bình theo giai đoạn"); plt.show()
else:
    print("Chưa có events.jsonl.")
```

## Bộ nhớ và đĩa

```{code-cell} python
:tags: [remove-input]
if len(ev):
    res = ev[ev["stage"] == "resources"]
    s = res[res["event"] == "summary"]
    if len(s):
        mb = 2**20
        display(pd.DataFrame({
            "run": s["run_id"], "RAM đỉnh (MB)": (s["rss_peak_bytes"]/mb).round(1),
            "RAM TB (MB)": (s["rss_mean_bytes"]/mb).round(1),
            "Đĩa đỉnh (MB)": (s["disk_peak_bytes"]/mb).round(1),
            "Đầu ra (MB)": (s["output_storage_bytes"]/mb).round(1)}))
    smp = res[res["event"] == "sample"]
    if len(smp):
        fig, ax = plt.subplots(figsize=(7, 3))
        for rid, g in smp.groupby("run_id"):
            ax.plot(g["elapsed_s"]/60, g["rss_bytes"]/2**20, label=rid)
        ax.set(xlabel="phút", ylabel="RSS (MB)", title="RAM theo thời gian"); ax.legend(); plt.show()
```
