---
title: 6. Đánh giá các Cấu hình và Chiến lược Đã Triển khai
short_title: 06. Đánh giá Cấu hình
label: m1-06-evaluation
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

:::{note} Phụ trách: Hiền (bảng biểu, biểu đồ hiệu năng) — Các thành viên đóng góp nhận xét cho cấu hình của mình
:::

# 6. Đánh giá các Cấu hình và Chiến lược Đã Triển khai

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

## 6.1. Hiệu năng Thực nghiệm (Thời gian, RAM, Ổ đĩa)

Dữ liệu đo đạc tài nguyên thực tế được thu thập qua `ResourceMonitor` (thư viện `psutil`) trong môi trường Colab CPU-only.

### Thời gian chạy theo từng giai đoạn
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
    print("Chưa có dữ liệu events.jsonl.")
```

### Tiêu thụ Bộ nhớ RAM và Dung lượng Đĩa
```{code-cell} python
:tags: [remove-input]
r = bd.runs
if len(r):
    cols = [c for c in ["config", "wall_seconds", "peak_rss_mb", "disk_used_mb"] if c in r.columns]
    display(r[cols])
else:
    print("Chưa có dữ liệu runs.csv.")
```

---

## 6.2. So sánh Tổng hợp Giữa Bốn Cấu hình Thử nghiệm

```{code-cell} python
:tags: [remove-input]
if bd.need_data() and bd.runs["config"].nunique() > 0:
    rows = []
    for cfg in sorted(bd.runs["config"].dropna().unique()):
        p = bd.paper_success(cfg)
        e = bd.events[(bd.events["config"] == cfg) & (bd.events["event"] == "finished")]
        pt = e[e["stage"] == "paper"]["duration_s"]
        rows.append({"Cấu hình": cfg, "Số bài": len(p),
                     "Tỉ lệ thành công": f"{p['success'].mean():.1%}",
                     "TB giây / bài": round(pt.mean(), 1) if len(pt) else None})
    display(pd.DataFrame(rows))
```

### Nhận xét Đánh giá từ các Thành viên:

- **Cấu hình B (Baseline — Hương phụ trách):**
  - *Ưu điểm:* Sử dụng trực tiếp arXiv API qua truy vấn Atom XML và tải stream trực tiếp từ mirror `export.arxiv.org`. Luôn đảm bảo dữ liệu mới nhất, danh sách phiên bản đầy đủ và lấy được chính xác ngày sửa đổi của từng phiên bản qua cơ chế fallback HTML.
  - *Nhược điểm:* Thời gian thu thập bị giới hạn bởi chính sách giãn cách bắt buộc $\ge 3$s giữa hai request của arXiv, khiến tốc độ chạy cho tập lớn 5.000 bài kéo dài từ 14 đến 20 giờ.
  - *Độ tin cậy:* Rất cao nhờ cơ chế ghi tệp nguyên tử và khả năng phục hồi (warm resume) bỏ qua ngay lập tức các bài đã tải thành công.

- **Cấu hình D1 (OAI-PMH — Linh phụ trách):**
  - *(Nhận xét của Linh: Ưu/nhược điểm khi thu thập hàng loạt qua OAI-PMH, vấn đề hết hạn resumption token trong ngày, so sánh với API.)*

- **Cấu hình D2 (Kaggle Snapshot — Châu phụ trách):**
  - *(Nhận xét của Châu: Ưu/nhược điểm khi dùng snapshot tĩnh JSONL, tốc độ nạp cục bộ tức thì nhưng cần cơ chế cập nhật bổ sung các phiên bản mới.)*

- **Cấu hình S1 (arxiv-downloader CLI — Nhóm thử nghiệm):**
  - *(Nhận xét về việc sử dụng công cụ CLI đóng gói sẵn so với tầng HTTP tự phát triển.)*

