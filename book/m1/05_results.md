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

Các bảng dưới đây được tính từ snapshot corpus M1 của bốn thành viên.
Benchmark Colab 5.000 bài được trình bày ở mục 5.5.

## 5.1. Số bài và tỷ lệ thành công

Bài thành công khi metadata `ok`, có đủ phiên bản và mọi phiên bản đều tải `ok`,
trích xuất `ok` hoặc `empty`. Bản không có TeX vẫn giữ bản ghi rỗng theo đề.
Trạng thái `pending` hoặc chưa rõ không tính thành công. References đánh giá riêng.

```{code-cell} python
:tags: [remove-input]
if bd.need_data():
    versions = bd.versions.copy()
    versions["complete"] = (versions["download_status"].eq("ok")
                            & versions["extract_status"].isin(["ok", "empty"]))
    status = versions.groupby(["member", "arxiv_id"]).agg(
        complete=("complete", "all"), observed_versions=("version", "nunique")
    ).reset_index()
    papers = bd.papers.merge(status, on=["member", "arxiv_id"],
                             how="left", validate="one_to_one")
    papers["success"] = (papers["metadata_status"].eq("ok")
                         & papers["complete"].eq(True)
                         & papers["observed_versions"].eq(papers["latest_version"]))
    coverage = papers.groupby("member").agg(
        collected=("arxiv_id", "size"), successful=("success", "sum"))
    coverage.loc["Tổng"] = coverage.sum()
    coverage["Tỷ lệ thành công"] = coverage["successful"] / coverage["collected"]
    display(coverage.rename(columns={"collected": "Số bài", "successful": "Thành công"})
            .rename_axis("MSSV").style.format({"Số bài": "{:,.0f}",
            "Thành công": "{:,.0f}", "Tỷ lệ thành công": "{:.2%}"}))
```

## 5.2. Phân bố số phiên bản

```{code-cell} python
:tags: [remove-input]
if bd.need_data():
    counts = bd.papers["latest_version"].value_counts().sort_index()
    ax = counts.plot.bar(figsize=(7, 3.5), color="#4C72B0")
    ax.set(xlabel="Số phiên bản", ylabel="Số bài", title="Phân bố số phiên bản corpus M1")
    for i, value in enumerate(counts):
        ax.text(i, value, str(value), ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.show()
```

## 5.3. Kích thước trung bình trước và sau lọc

Kích thước mỗi bài cộng tất cả phiên bản rồi chia cho số bài quan sát, kể cả bài
có bản ghi rỗng. Trước lọc là byte giải nén inventory ghi nhận; sau lọc là byte
`.tex`/`.bib` thực giữ lại. Chênh lệch gồm hình ảnh và các loại tệp khác bị loại.

```{code-cell} python
:tags: [remove-input]
if len(bd.m1_size_summary) and len(bd.m1_member_summary):
    sizes = bd.m1_size_summary.merge(
        bd.m1_member_summary[["member", "observed_publications"]],
        on="member", validate="one_to_one").set_index("member")
    sizes.loc["Tổng"] = sizes.sum()
    table = pd.DataFrame({
        "Trước lọc (byte/bài)": sizes["raw_bytes"] / sizes["observed_publications"],
        "Sau lọc (byte/bài)": sizes["kept_tex_bib_bytes"] / sizes["observed_publications"],
        "Giảm dung lượng": 1 - sizes["kept_tex_bib_bytes"] / sizes["raw_bytes"]})
    display(table.rename_axis("MSSV").style.format({
        "Trước lọc (byte/bài)": "{:,.2f}", "Sau lọc (byte/bài)": "{:,.2f}",
        "Giảm dung lượng": "{:.2%}"}))
```

## 5.4. Thu thập metadata references

References trung bình bằng tổng references chia tổng số bài, bao gồm bài không có
references hoặc thu thập lỗi. Tỷ lệ hoàn tất truy vấn metadata theo bài bằng
`(references_ok + references_empty) / số bài`. `empty` nghĩa là truy vấn không trả
về references; lỗi hoặc chưa rõ không tính thành công. Chỉ số này không đo độ đầy
đủ của từng trường metadata.

```{code-cell} python
:tags: [remove-input]
if len(bd.m1_member_summary):
    refs = bd.m1_member_summary.set_index("member")[[
        "observed_publications", "references_total", "references_ok", "references_empty"]].copy()
    refs.loc["Tổng"] = refs.sum()
    table = pd.DataFrame({
        "Tổng references": refs["references_total"],
        "References/bài": refs["references_total"] / refs["observed_publications"],
        "Tỷ lệ lấy metadata": (refs["references_ok"] + refs["references_empty"])
                                / refs["observed_publications"]})
    display(table.rename_axis("MSSV").style.format({"Tổng references": "{:,.0f}",
        "References/bài": "{:.2f}", "Tỷ lệ lấy metadata": "{:.2%}"}))
```

## 5.5. Benchmark thực tế 5.000 bài

Mỗi thành viên chạy cấu hình A_PIPELINE trên Colab với 5.000 bài trong range được phân công.
Số liệu thời gian và RAM từ các report được lưu trong `data/m1_colab_time_ram.json`.

```{code-cell} python
:tags: [remove-input]
import json
benchmark = json.loads((bd.DATA / "m1_colab_time_ram.json").read_text(encoding="utf-8"))
mib = 1024 ** 2
metrics = []
for run in benchmark["runs"]:
    seconds = run["checkpointed_wall_seconds_sum"]
    metrics.append({
        "MSSV": run["member"],
        "Tổng thời gian (giây)": seconds,
        "Tổng thời gian (giờ)": seconds / 3600,
        "Trung bình (giây/bài)": seconds / run["input_count"],
        "RAM RSS cực đại (MiB)": run["rss_peak_bytes"] / mib,
        "RAM RSS TB có trọng số (MiB)": run["rss_mean_bytes_weighted"] / mib,
    })
table = pd.DataFrame(metrics)
display(table.style.hide(axis="index").format({
    column: "{:,.2f}" for column in table.columns if column != "MSSV"
}))
```

Đây là benchmark tổng hợp theo cơ chế streaming/discard: mỗi batch dùng một
`run_id` riêng với cache lạnh; dữ liệu bài chỉ được xóa sau khi metrics và report
của batch đã lưu vào Drive. Tổng thời gian là tổng wall time đã checkpoint,
**không gồm** các lượt bị ngắt chưa commit và thời gian runtime ngừng hoạt động.
Trung bình/bài được tính bằng tổng này chia 5.000, không phải độ trễ đo riêng
của từng bài. RAM là RSS theo các trường peak và trung bình có trọng số trong report.
