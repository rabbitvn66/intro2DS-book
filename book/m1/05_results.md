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

Việc loại bỏ các tệp nhị phân/hình ảnh và chỉ giữ lại `.tex`/`.bib` giúp giảm đáng kể dung lượng lưu trữ. Kích thước giữ lại được tính trực tiếp từ dung lượng `.tex`/`.bib` trong snapshot M1; kích thước trước lọc lấy từ tổng dung lượng nội dung giải nén được ghi trong inventory.

```{code-cell} python
:tags: [remove-input]
if len(bd.m1_size_summary):
    raw_mb = bd.m1_size_summary["raw_bytes"].sum() / (1024 * 1024)
    kept_mb = bd.m1_size_summary["kept_tex_bib_bytes"].sum() / (1024 * 1024)
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
if len(bd.m1_member_summary):
    s = bd.m1_member_summary
    n_papers = s["observed_publications"].sum()
    total_refs = s["references_total"].sum()
    with_arxiv = s["references_with_arxiv_id"].sum()
    with_date = s["references_with_date"].sum()
    print(f"Tổng số references thu thập: {total_refs}")
    print(f"Trung bình references / bài: {total_refs / n_papers:.1f}" if n_papers else "Chưa có bài")
    print(f"Số references có arXiv ID: {with_arxiv} ({with_arxiv / total_refs:.1%})" if total_refs else "Chưa có references")
    print(f"Số references có ngày S2: {with_date} ({with_date / total_refs:.1%})" if total_refs else "Chưa có references")
```

## 5.5. Tổng hợp bốn thành viên

Tổng hợp dưới đây chỉ dùng dữ liệu inventory của M1: số bài quan sát được,
trạng thái metadata và references. Dữ liệu kiểm định validation không được
tính trong trang này. `references_with_date` là số reference có
`ref_submission_date` từ dữ liệu S2, không phải ngày nộp bài trên arXiv.

```{code-cell} python
:tags: [remove-input]
if len(bd.m1_member_summary):
    member_names = {
        "24120027": "Lý Ngọc Châu",
        "24120046": "Nguyễn Hà Minh Hiền",
        "24120058": "Nguyễn Lưu Hương",
        "24120085": "Lê Nguyễn Thùy Linh",
    }
    summary = bd.m1_member_summary.copy()
    summary["member"] = summary["member"].astype(str)
    summary["Thành viên"] = summary["member"].map(member_names).fillna(summary["member"])

    coverage = summary[[
        "Thành viên", "member", "expected_publications",
        "observed_publications", "missing_ids", "metadata_ok", "metadata_unknown",
    ]].rename(columns={
        "member": "MSSV",
        "expected_publications": "ID dự kiến",
        "observed_publications": "ID quan sát",
        "missing_ids": "Thiếu",
        "metadata_ok": "Metadata OK",
        "metadata_unknown": "Metadata chưa rõ",
    })

    references = summary[[
        "Thành viên", "references_ok", "references_empty",
        "references_failed", "references_unknown", "references_total",
        "references_with_date", "references_with_arxiv_id",
    ]].rename(columns={
        "references_ok": "References OK",
        "references_empty": "Không có citation",
        "references_failed": "References lỗi",
        "references_unknown": "References chưa rõ",
        "references_total": "Tổng references",
        "references_with_date": "Có ngày S2",
        "references_with_arxiv_id": "Có arXiv ID",
    })

    display(coverage.style.hide(axis="index").format(
        {"ID dự kiến": "{:,.0f}", "ID quan sát": "{:,.0f}",
         "Thiếu": "{:,.0f}", "Metadata OK": "{:,.0f}",
         "Metadata chưa rõ": "{:,.0f}"}))
    display(references.style.hide(axis="index").format(
        {column: "{:,.0f}" for column in references.columns if column != "Thành viên"}))
```

