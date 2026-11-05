---
title: Milestone 1 — Data Crawling
short_title: Tổng quan M1
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

## Tổng quan

Milestone 1 tập trung vào xây dựng pipeline thu thập dữ liệu (crawling) toàn diện từ kho lưu trữ mở arXiv. Mục tiêu chính là giải quyết danh sách mã định danh arXiv được phân công, tải toàn bộ mã nguồn $\LaTeX$ nguyên bản (tất cả các phiên bản của từng bài viết) và thu thập thông tin trích dẫn có cấu trúc thông qua Semantic Scholar API.

Corpus thu thập được trong milestone này là nền tảng phục vụ các bài toán bóc tách cấu trúc (parsing) ở Milestone 2 và mô hình học máy (machine learning / citation matching) ở Milestone 3.

### Dải ID và phân công nhóm
Nhóm được phân công dải gồm 20.000 bài báo arXiv (`configs/solo/ids_all.txt`), được chia đều cho 4 thành viên (mỗi thành viên 5.000 bài):
- **Hương (Baseline B):** Phụ trách kiến trúc baseline, discovery qua arXiv API, tải source qua HTTP endpoint `/src/`, quản trị repo sách và duyệt PR (`configs/team/ids_24120058.txt`: dải `2507.01659` – `2507.06658`).
- **Linh (D1):** Phụ trách cơ chế thu thập siêu dữ liệu qua OAI-PMH, quy trình giải nén trích xuất chỉ giữ `.tex`/`.bib` (loại bỏ hình ảnh) và kiểm định lưu trữ (`configs/team/ids_24120046.txt`: dải `2507.11659` – `2507.16658`).
- **Châu (D2):** Phụ trách cơ chế discovery qua Kaggle Dataset snapshot và module thu thập trích dẫn Semantic Scholar (`configs/team/ids_24120027.txt`: dải `2507.21659` – `2507.26658`).
- **Hiền (Benchmark & Metrics):** Phụ trách đo đạc tài nguyên (RAM, CPU, Disk, thời gian chạy), thu thập log, tổng hợp benchmark và cập nhật dữ liệu báo cáo (`configs/team/ids_24120085.txt`: dải `2505.15666` – `2505.20665`).

### Sơ đồ kiến trúc Pipeline
Toàn bộ hệ thống được thiết kế theo kiến trúc luồng dữ liệu xử lý tuần tự từng bài (per-paper pipeline), đảm bảo tính cô lập lỗi, khả năng phục hồi (fault tolerance) và ghi nhật ký kiểm toán (audit log) chi tiết:

```{mermaid}
flowchart LR
  A[Danh sách ID bài báo] --> B[Discovery<br/>arXiv API / OAI / Kaggle]
  B --> C[Download từng version<br/>HTTP export.arxiv.org/src/]
  C --> D[Extract .tex/.bib<br/>Loại bỏ hình ảnh]
  B --> E[References<br/>Semantic Scholar API]
  D --> F[Storage & Validation<br/>Atomic write & Manifest]
  E --> F
  F --> G[Resource Monitoring<br/>psutil & EventLogger]
```

## Bốn cấu hình thử nghiệm

Để đánh giá hiệu quả và độ tin cậy của các chiến lược thu thập khác nhau, nhóm triển khai và thực nghiệm 4 cấu hình:

| Cấu hình | Phương pháp Discovery | Giao thức Tải nguồn | Đặc điểm chính | Người phụ trách |
|:--|:--|:--|:--|:--|
| **B** (Baseline) | arXiv API (`arxiv.py` + query `id_list`) | HTTP `/src/{id}v{version}` | Chuẩn mực tham chiếu; truy vấn trực tiếp Atom XML API; pacing $\ge 3$s. | Hương |
| **D1** | OAI-PMH (`sickle` endpoint mới) | HTTP `/src/{id}v{version}` (giống B) | Thu thập metadata hàng loạt qua giao thức OAI-PMH; xử lý resumption token hết hạn trong ngày. | Linh |
| **D2** | Kaggle Dataset Snapshot | HTTP `/src/{id}v{version}` (giống B) | Nạp metadata từ snapshot JSONLines địa phương; tốc độ cực nhanh, sau đó bổ sung version mới qua API. | Châu |
| **S1** | arXiv API (giống B) | CLI `arxiv-downloader` | Thử nghiệm công cụ dòng lệnh chuyên dụng để tải mã nguồn thay vì tầng HTTP tự phát triển. | *(Chung nhóm)* |

## Mục lục báo cáo chi tiết

- **Khám phá dữ liệu (Discovery):**
  - [](#m1-discovery-arxiv): Cơ chế truy vấn arXiv API, giải quyết danh sách phiên bản và ngày sửa đổi (revised dates).
  - [](#m1-discovery-oai): Thu hoạch siêu dữ liệu qua OAI-PMH, xử lý tập dữ liệu lớn.
  - [](#m1-discovery-kaggle): Nạp snapshot tĩnh từ Kaggle và chiến lược đồng bộ dữ liệu.
- **Tải và Trích xuất nguồn (Download & Extraction):**
  - [](#m1-download): Tầng kết nối HTTP, cơ chế điều tốc Throttle, Exponential Backoff và phân loại lỗi.
  - [](#m1-extract): Trích xuất cô lập mã nguồn $\LaTeX$ (`.tex`, `.bib`), loại bỏ file rác/ảnh và tổ chức lưu trữ an toàn.
- **Dữ liệu trích dẫn (References):**
  - [](#m1-references): Tích hợp Semantic Scholar API, ánh xạ arXiv ID và xử lý Rate Limit.
- **Thống kê và Đánh giá hiệu năng:**
  - [](#m1-stats): Thống kê số lượng bài, tỷ lệ thành công, kích thước trước/sau khi loại bỏ hình ảnh.
  - [](#m1-perf): Đo lường tài nguyên thực tế (RAM đỉnh, RAM trung bình, dung lượng ổ đĩa, thời gian xử lý).
  - [](#m1-compare): So sánh tổng hợp giữa 4 cấu hình B, D1, D2, S1 và bài học kinh nghiệm.
