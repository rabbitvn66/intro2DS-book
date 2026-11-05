---
title: 5. Kết quả thu thập dữ liệu
short_title: 05. Kết quả
label: m1-05-results
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

:::{note} Phụ trách: Hiền
Dữ liệu và đồ thị trong trang này được tính toán tự động khi biên dịch sách từ các tệp tóm tắt trong `data/`.
:::

# 5. Kết quả thu thập dữ liệu

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

## 5.1. Số bài thành công và Tỉ lệ thành công

Một bài viết được coi là **thành công** khi metadata đạt trạng thái `ok` và không có phiên bản nào bị `failed` (các phiên bản không có TeX được ghi nhận là `empty`, không tính là lỗi).

```{code-cell} python
:tags: [remove-input]
if bd.need_data():
    succ = bd.paper_success()
    total = len(succ)
    ok_count = int(succ["success"].sum())
    rate = ok_count / total if total > 0 else 0
    print(f"Tổng số bài crawl: {total}")
    print(f"Số bài thành công: {ok_count} ({rate:.1%})")
```

## 5.2. Phân bố số phiên bản

Đa số bài báo trên arXiv có 1 đến 2 phiên bản; một số ít bài có số lượng bản cập nhật lớn hơn.

```{code-cell} python
:tags: [remove-input]
if bd.need_data() and len(bd.papers):
    counts = bd.papers["latest_version"].value_counts().sort_index()
    ax = counts.plot.bar(figsize=(7, 3.5), color="#4C72B0")
    ax.set(xlabel="Số phiên bản (latest version)", ylabel="Số lượng bài",
           title="Phân bố số lượng phiên bản của các bài báo")
    for i, v in enumerate(counts):
        ax.text(i, v + 0.5, str(v), ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.show()
```

## 5.3. Kích thước trước và sau khi loại bỏ hình ảnh

Việc loại bỏ các tệp nhị phân/hình ảnh và chỉ giữ lại `.tex`/`.bib` giúp giảm đáng kể dung lượng lưu trữ trên đĩa:

```{code-cell} python
:tags: [remove-input]
if bd.need_data() and len(bd.versions):
    v = bd.versions[bd.versions["extract_status"] == "ok"]
    raw_mb = v["unpacked_total_bytes"].sum() / (1024 * 1024)
    kept_mb = v["kept_source_bytes"].sum() / (1024 * 1024)
    ratio = kept_mb / raw_mb if raw_mb > 0 else 0
    df = pd.DataFrame({
        "Trạng thái": ["Trước khi lọc (tổng giải nén)", "Sau khi lọc (chỉ .tex/.bib)"],
        "Dung lượng (MB)": [round(raw_mb, 2), round(kept_mb, 2)]
    })
    display(df)
    print(f"-> Dung lượng giữ lại chỉ chiếm khoảng {ratio:.1%} so với dung lượng thô ban đầu.")
```

## 5.4. Thống kê Trích dẫn (References)

```{code-cell} python
:tags: [remove-input]
if bd.need_data():
    r = bd.refs
    n_papers = bd.papers["arxiv_id"].nunique()
    total_refs = len(r)
    with_arxiv = r["ref_arxiv_id"].notna().sum()
    print(f"Tổng số references thu thập: {total_refs}")
    print(f"Trung bình references / bài: {total_refs / n_papers:.1f}" if n_papers else "Chưa có bài")
    print(f"Số references có arXiv ID: {with_arxiv} ({with_arxiv / total_refs:.1%})" if total_refs else "Chưa có references")
```

