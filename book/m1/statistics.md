---
title: Thống kê dữ liệu thu thập
short_title: Thống kê
label: m1-stats
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

# Thống kê dữ liệu thu thập

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

## Số bài thành công

Một bài **thành công** khi metadata `ok` và không version nào `failed` (version không có TeX tính là `empty`, không phải lỗi).

```{code-cell} python
:tags: [remove-input]
if bd.need_data():
    p = bd.paper_success()
    v = bd.versions
    n, ok = len(p), int(p["success"].sum())
    display(pd.DataFrame({
        "Chỉ số": ["Số bài", "Bài thành công", "Tỉ lệ thành công", "Tổng số version",
                   "Version có TeX", "Version rỗng (không TeX)", "Version lỗi"],
        "Giá trị": [n, ok, f"{ok/n:.2%}", len(v), int(v["extract_status"].eq("ok").sum()),
                    int(v["extract_status"].eq("empty").sum()),
                    int(v["extract_status"].eq("failed").sum())]}))
```

```{code-cell} python
:tags: [remove-input]
if bd.HAS_DATA:
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    bd.papers["latest_version"].value_counts().sort_index().plot.bar(ax=ax[0], color="#4C78A8")
    ax[0].set(title="Số version mỗi bài", xlabel="Số version", ylabel="Số bài")
    bd.versions["extract_status"].value_counts().plot.bar(ax=ax[1], color="#F58518")
    ax[1].set(title="Trạng thái extract theo version", xlabel="", ylabel="Số version")
    plt.tight_layout(); plt.show()
```

## Kích thước trước và sau khi bỏ hình

```{code-cell} python
:tags: [remove-input]
if bd.HAS_DATA and "unpacked_total_bytes" in bd.versions:
    sz = bd.versions.dropna(subset=["unpacked_total_bytes", "kept_source_bytes"])
    pp = sz.groupby("arxiv_id")[["unpacked_total_bytes", "kept_source_bytes"]].sum()
    display((pp.mean() / 1024).round(1).rename(
        {"unpacked_total_bytes": "Trước khi bỏ hình (KB/bài)",
         "kept_source_bytes": "Sau khi bỏ hình (KB/bài)"}).to_frame("Trung bình"))
```

## References

```{code-cell} python
:tags: [remove-input]
if bd.HAS_DATA and len(bd.refs):
    per = bd.refs.groupby("arxiv_id").size().reindex(bd.papers["arxiv_id"], fill_value=0)
    ok_resp = bd.papers["references_status"].isin(["ok", "empty"]).mean()
    display(pd.DataFrame({
        "Chỉ số": ["Reference trung bình / bài", "Tổng reference có arXiv ID",
                   "Tỉ lệ reference có arXiv ID", "Tỉ lệ bài lấy được metadata reference"],
        "Giá trị": [f"{per.mean():.1f}", int(bd.refs["has_arxiv_id"].sum()),
                    f"{bd.refs['has_arxiv_id'].mean():.2%}", f"{ok_resp:.2%}"]}))
    per.plot.hist(bins=40, figsize=(6, 3.5), color="#54A24B")
    plt.xlabel("Số reference / bài"); plt.ylabel("Số bài"); plt.show()
```
