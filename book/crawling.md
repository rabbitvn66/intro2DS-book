---
title: Milestone 1 — Data Crawling
short_title: Milestone 1 — Crawling
label: m1-crawling
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# Milestone 1 — Data Crawling

## 1. Tổng quan

Mục tiêu: với dải ID arXiv được giao, tìm **mọi version** của từng bài, tải mã nguồn LaTeX (chỉ giữ `.tex`, `.bib`), lấy metadata và metadata của các reference qua Semantic Scholar.

*(Viết 1–2 đoạn: dải ID của nhóm, tổng số bài, chia việc giữa các thành viên.)*

## 2. Cách crawl hoạt động

```{mermaid}
flowchart LR
  A[Danh sách ID] --> B[Discovery<br/>arXiv API]
  B --> C[Download<br/>export.arxiv.org/src/ID vN]
  C --> D[Extract<br/>chỉ giữ .tex, .bib]
  B --> E[References<br/>Semantic Scholar]
  D --> F[Storage + Validation]
  E --> F
```

### 2.1 Entry discovery
*(arXiv API `id_list` → metadata và số version từ hậu tố `vN` của bản mới nhất; ngày các bản revise lấy từ trang abs. Nêu lý do chọn arXiv API, và nếu có thử OAI-PMH / Kaggle thì so sánh ngắn.)*

### 2.2 Tải source từng version
*(Endpoint `https://export.arxiv.org/src/{id}v{n}`, delay 3 giây, một kết nối, User-Agent mô tả, retry/backoff, cơ chế resume theo `run_id`.)*

### 2.3 Trích xuất và bỏ hình
*(Chỉ extract `.tex`/`.bib` khỏi archive nên hình không bao giờ vào corpus; giữ nguyên lệnh `figure`, `\includegraphics`. Version chỉ có PDF → bản ghi rỗng `NO_TEX_SOURCE`.)*

### 2.4 Reference qua Semantic Scholar
*(Endpoint, các field, lọc `externalIds.ArXiv`, giữ mọi reference cục bộ, xử lý 429, dùng API key.)*

### 2.5 Công cụ và thư viện
`arxiv` 4.x, `requests`, `PyYAML`, `psutil`, `pytest` … *(bổ sung)*

## 3. Thống kê dữ liệu

```{code-cell} python
:tags: [remove-input]
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt

DATA = Path("data")
def load(name, **kw):
    p = DATA / name
    return pd.read_csv(p, **kw) if p.exists() else pd.DataFrame()

papers = load("papers.csv")
versions = load("versions.csv")
refs = load("references.csv")
runs = load("runs.csv")
events = pd.read_json(DATA / "events.jsonl", lines=True) if (DATA / "events.jsonl").exists() else pd.DataFrame()

HAS_DATA = len(papers) > 0
if not HAS_DATA:
    print("Chưa có dữ liệu trong book/data — chạy export_for_book.py rồi build lại.")
```

### 3.1 Số bài crawl thành công

Một bài được tính **thành công** khi metadata `ok` và mọi version đều đã được xử lý (`ok` hoặc `empty` do không có TeX), không version nào `failed`.

```{code-cell} python
:tags: [remove-input]
if HAS_DATA:
    bad = set(versions.loc[versions["extract_status"].eq("failed") |
                           versions["download_status"].eq("failed"), "arxiv_id"])
    papers["success"] = papers["metadata_status"].eq("ok") & ~papers["arxiv_id"].isin(bad)
    n, ok = len(papers), int(papers["success"].sum())
    summary = pd.DataFrame({
        "Chỉ số": ["Số bài được giao", "Số bài thành công", "Tỉ lệ thành công",
                   "Tổng số version", "Version có TeX (ok)", "Version rỗng (không có TeX)",
                   "Version lỗi"],
        "Giá trị": [n, ok, f"{ok/n:.2%}", len(versions),
                    int(versions["extract_status"].eq("ok").sum()),
                    int(versions["extract_status"].eq("empty").sum()),
                    int(versions["extract_status"].eq("failed").sum())],
    })
    display(summary)
```

```{code-cell} python
:tags: [remove-input]
if HAS_DATA:
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    papers["latest_version"].value_counts().sort_index().plot.bar(ax=ax[0], color="#4C78A8")
    ax[0].set(title="Số version mỗi bài", xlabel="Số version", ylabel="Số bài")
    versions["extract_status"].value_counts().plot.bar(ax=ax[1], color="#F58518")
    ax[1].set(title="Trạng thái extract theo version", xlabel="", ylabel="Số version")
    plt.tight_layout(); plt.show()
```

### 3.2 Kích thước trước và sau khi bỏ hình

```{code-cell} python
:tags: [remove-input]
if HAS_DATA and "unpacked_total_bytes" in versions:
    sz = versions.dropna(subset=["unpacked_total_bytes", "kept_source_bytes"])
    per_paper = sz.groupby("arxiv_id")[["unpacked_total_bytes", "kept_source_bytes"]].sum()
    display(pd.DataFrame({
        "Trung bình / bài (KB)": (per_paper.mean() / 1024).round(1),
    }).rename(index={"unpacked_total_bytes": "Trước khi bỏ hình",
                     "kept_source_bytes": "Sau khi bỏ hình (.tex + .bib)"}))
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.hist([per_paper["unpacked_total_bytes"] / 1e6, per_paper["kept_source_bytes"] / 1e6],
            bins=40, log=True, label=["Trước", "Sau"])
    ax.set(xlabel="MB / bài", ylabel="Số bài (log)", title="Kích thước source")
    ax.legend(); plt.show()
```

### 3.3 Reference

```{code-cell} python
:tags: [remove-input]
if HAS_DATA and len(refs):
    per_paper_refs = refs.groupby("arxiv_id").size().reindex(papers["arxiv_id"], fill_value=0)
    resp_ok = papers["references_status"].isin(["ok", "empty"]).mean()
    display(pd.DataFrame({
        "Chỉ số": ["Reference trung bình / bài", "Reference có arXiv ID (tổng)",
                   "Tỉ lệ reference có arXiv ID", "Tỉ lệ bài lấy được metadata reference"],
        "Giá trị": [f"{per_paper_refs.mean():.1f}", int(refs["has_arxiv_id"].sum()),
                    f"{refs['has_arxiv_id'].mean():.2%}", f"{resp_ok:.2%}"],
    }))
    ax = per_paper_refs.plot.hist(bins=40, figsize=(6, 3.5), color="#54A24B")
    ax.set(xlabel="Số reference / bài", ylabel="Số bài", title="Phân bố số reference")
    plt.show()
```

## 4. Hiệu năng

### 4.1 Thời gian chạy

```{code-cell} python
:tags: [remove-input]
if len(events):
    fin = events[(events["event"] == "finished") & events["duration_s"].notna()]
    t = (fin.groupby("stage")["duration_s"]
            .agg(["count", "sum", "mean", "max"]).round(2)
            .rename(columns={"count": "Số thao tác", "sum": "Tổng (s)",
                             "mean": "Trung bình (s)", "max": "Lớn nhất (s)"}))
    display(t)
    paper_t = fin[fin["stage"] == "paper"]["duration_s"]
    if len(paper_t):
        print(f"Trung bình xử lý 1 bài: {paper_t.mean():.1f}s")
    ax = (t["Trung bình (s)"].drop(["pipeline"], errors="ignore")
          .plot.barh(figsize=(6, 3), color="#B279A2"))
    ax.set(xlabel="giây", title="Thời gian trung bình theo giai đoạn"); plt.show()
```

### 4.2 Bộ nhớ và đĩa

```{code-cell} python
:tags: [remove-input]
if len(events):
    res = events[events["stage"] == "resources"]
    s = res[res["event"] == "summary"]
    if len(s):
        r = s.iloc[-1]
        display(pd.DataFrame({
            "Chỉ số": ["RAM đỉnh (MB)", "RAM trung bình (MB)", "Đĩa đỉnh (MB)",
                       "Dung lượng đầu ra (MB)"],
            "Giá trị": [round(r["rss_peak_bytes"] / 2**20, 1), round(r["rss_mean_bytes"] / 2**20, 1),
                        round(r["disk_peak_bytes"] / 2**20, 1),
                        round(r["output_storage_bytes"] / 2**20, 1)],
        }))
    smp = res[res["event"] == "sample"]
    if len(smp):
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.plot(smp["elapsed_s"] / 60, smp["rss_bytes"] / 2**20)
        ax.set(xlabel="phút", ylabel="RSS (MB)", title="RAM theo thời gian"); plt.show()
```

*(Ghi rõ môi trường đo: Colab CPU-only hay máy cá nhân; số run; cold/warm cache.)*

## 5. Khó khăn và bài học
*(Rate limit 429 của Semantic Scholar, bài chỉ có PDF, archive lạ (`.gz` đơn lẻ, `.tex` đơn), bài cũ dạng `hep-th/…`, resume sau khi gián đoạn …)*
