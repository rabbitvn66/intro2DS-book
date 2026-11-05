---
title: 1. Tổng quan Milestone 1
short_title: 01. Tổng quan
label: m1-01-overview
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 1. Tổng quan Milestone 1 — Data Crawling

Milestone 1 xây dựng pipeline thu thập dữ liệu từ kho lưu trữ mở arXiv. Với danh sách mã định danh (ID) được phân công, pipeline thực hiện bốn việc: xác định toàn bộ phiên bản (version) của từng bài báo, tải mã nguồn $\LaTeX$ của mọi version, trích xuất riêng các tệp `.tex` và `.bib`, và thu thập danh sách trích dẫn có cấu trúc qua Semantic Scholar API. Kết quả là một corpus được lưu trên đĩa dưới dạng JSON, có nhật ký chạy đầy đủ và được kiểm định tự động.

Corpus này là đầu vào cho Milestone 2 (phân tích cấu trúc LaTeX, trích xuất BibTeX, loại trùng) và Milestone 3 (đối sánh BibTeX với metadata trích dẫn bằng học máy).

## 1.1. Phân công nhiệm vụ và dải ID

Nhóm được giao 20.000 bài báo arXiv (`configs/solo/ids_all.txt`, từ `2505.15666` đến `2508.02871`), chia cho bốn thành viên, mỗi người **5.000 ID**. Bốn dải ID không liền kề nhau. Bảng dưới sắp xếp theo mã số sinh viên.

| Thành viên | MSSV | Dải ID được giao | Nhiệm vụ phụ trách |
|:---|:---:|:---|:---|
| **Trần Bảo Châu** | `24120027` | `2507.21659` – `2508.02871`<br/>(`configs/team/ids_24120027.txt`) | - Chiến lược điều phối Bounded Pipeline.<br/>- Cơ chế xử lý lỗi và đảm bảo tính nhất quán dữ liệu.<br/>- Discovery qua “Kaggle Dataset Snapshot” (phương án tham khảo, không dùng trong cấu hình chính).<br/>- Module thu thập trích dẫn qua Semantic Scholar API. |
| **Lê Thị Thùy Linh** | `24120046` | `2507.11659` – `2507.16658`<br/>(`configs/team/ids_24120046.txt`) | - Discovery qua OAI-PMH.<br/>- Extract: giải nén, chỉ giữ `.tex`/`.bib`, loại bỏ các tệp còn lại (gồm hình ảnh).<br/>- Storage: lưu trữ và kiểm định corpus. |
| **Nguyễn Lưu Hương** | `24120058` | `2507.01659` – `2507.06658`<br/>(`configs/team/ids_24120058.txt`) | - Kiến trúc baseline (cấu hình `B`).<br/>- Discovery qua arXiv API.<br/>- Tải mã nguồn qua HTTP endpoint `export.arxiv.org/src/`.<br/>- Quản trị repo sách, duyệt Pull Request. |
| **Nguyễn Thị Thu Hiền** | `24120085` | `2505.15666` – `2505.20665`<br/>(`configs/team/ids_24120085.txt`) | - Benchmark và Metrics.<br/>- Đo tài nguyên: RAM, CPU, đĩa, thời gian chạy.<br/>- Thu thập log, tổng hợp benchmark.<br/>- Cập nhật dữ liệu thực nghiệm vào báo cáo. |

## 1.2. Công nghệ và cấu hình

Hệ thống viết bằng Python 3.10+. Các thư viện chính được khai báo trong `requirements.txt`:

| Thư viện | Vai trò |
|:---|:---|
| `arxiv` | Truy vấn metadata và danh sách version (discovery của baseline) |
| `requests` | Gửi request HTTP, tải mã nguồn, gọi Semantic Scholar |
| `PyYAML` | Đọc tệp cấu hình chạy (`configs/*.yaml`) |
| `psutil` | Lấy mẫu RAM và đĩa trong lúc chạy |
| `kagglehub` | Đọc Kaggle metadata snapshot (phương án tham khảo) |
| `pytest` | Kiểm thử offline cho các module |

Toàn bộ thiết lập của một lần chạy nằm trong một tệp YAML (`src/config.py` kiểm tra các khóa bắt buộc). Những tham số quan trọng nhất của cấu hình baseline `configs/baseline.yaml`:

| Tham số | Giá trị | Ý nghĩa |
|:---|:---:|:---|
| `arxiv_delay_seconds` | 3 | Khoảng cách tối thiểu giữa hai request tới arXiv |
| `timeout` | 30 | Thời gian chờ mỗi request (giây) |
| `max_retries` | 3 | Số lần thử lại sau lần gọi đầu tiên |
| `s2_max_retries`, `s2_backoff_base_seconds` | 3, 5 | Ngân sách retry riêng cho Semantic Scholar |
| `user_agent` | có email liên hệ | arXiv yêu cầu User-Agent mô tả rõ người chạy |
| `run_id` | `B_{timestamp}` | Chạy mới mỗi lần; đặt giá trị cố định để tiếp tục (resume) một lần chạy dở |

Mã `S2_API_KEY` (nếu có) được đọc từ biến môi trường, không lưu trong repo. Chiến lược chạy được chọn bằng khóa `config_name`; mã nguồn hiện có bốn giá trị: `B` (baseline), `D1` (discovery qua OAI-PMH), `A_BATCH` (discovery theo lô) và `A_PIPELINE` (Bounded Pipeline).

## 1.3. Sơ đồ kiến trúc pipeline

Đơn vị xử lý là **từng bài báo**: mỗi bài đi qua chuỗi stage dưới đây, lỗi của một bài không làm dừng toàn bộ lần chạy. Ở cấu hình baseline `B` (và `D1`), các stage chạy tuần tự theo thứ tự này trong `src/main.py`:

```{mermaid}
flowchart LR
  A[Danh sách ID<br/>ids_file] --> B[Discovery<br/>metadata.json]
  B --> C[Download từng version<br/>export.arxiv.org/src/]
  C --> D[Extract<br/>chỉ giữ .tex / .bib]
  D --> E[References<br/>Semantic Scholar]
  E --> F[Storage và Validation<br/>validation.json]
  M[ResourceMonitor<br/>psutil] -.-> A
  M -.-> F
```

Ở cấu hình `A_PIPELINE`, Extract và References trở thành hai worker độc lập chạy song song với khâu tải của luồng chính, còn Storage và Validation chỉ chạy khi cả hai worker đã xử lý xong bài đó. Chiến lược này được trình bày ở [](02_bounded_pipeline.md). Cả hai kiến trúc dùng chung các module stage và cùng định dạng dữ liệu đầu ra.

## 1.4. Cấu trúc dữ liệu đầu ra

Mỗi lần chạy ghi toàn bộ kết quả vào `experiments/<run_id>/`. Tên thư mục của một bài (`paper_key`) được tạo từ ID gốc bằng cách đổi `.` thành `-` và `/` thành `__`.

```text
experiments/<run_id>/
├── run.json                           # cấu hình, thời điểm chạy, run_status, cache_mode
├── events.jsonl                       # nhật ký từng stage, mỗi bài kết thúc bằng một event "paper"
├── metrics_events.jsonl               # số đo thời gian và tài nguyên
├── tmp/<paper_key>/v<N>/source.archive  # tệp nén tạm của từng version
└── papers/<paper_key>/
    ├── metadata.json                  # kết quả discovery: tiêu đề, tác giả, danh sách version
    ├── references.json                # trích dẫn thu thập từ Semantic Scholar
    ├── validation.json                # báo cáo kiểm định của bài
    └── versions/v<N>/
        ├── manifest.json              # trạng thái tải/trích xuất, dung lượng, danh sách tệp giữ lại
        └── source/                    # chỉ chứa các tệp .tex và .bib
```

Mỗi trạng thái xử lý dùng chung một bộ giá trị: `pending`, `running`, `ok`, `empty`, `failed`, `skipped`. Trạng thái `empty` biểu thị kết quả rỗng hợp lệ, ví dụ bài chỉ có PDF, không có mã nguồn TeX.

## 1.5. Cấu trúc của báo cáo

Báo cáo Milestone 1 gồm bảy mục:

1. [](01_overview.md): mục tiêu, phân công, kiến trúc tổng thể và cấu trúc dữ liệu đầu ra.
2. [](02_bounded_pipeline.md): chiến lược điều phối đa luồng có chặn trên (Three-Lane Bounded Concurrency).
3. [](03_pipeline_stages.md): các bước kỹ thuật gồm Discovery, Download, Extract, References và Storage.
4. [](04_fault_tolerance.md): retry, phân loại mã lỗi, ghi tệp nguyên tử, khả năng chạy lại và kiểm định tính nhất quán.
5. [](05_results.md): thống kê số bài thành công, dung lượng trước và sau khi loại bỏ hình ảnh, phân bố version và trích dẫn.
6. [](06_evaluation.md): đánh giá thời gian chạy, RAM, đĩa và so sánh các cấu hình đã triển khai.
7. [](07_conclusion.md): tổng kết, khó khăn, hạn chế và hướng phát triển.