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

Milestone 1 tập trung vào xây dựng pipeline thu thập dữ liệu (crawling) toàn diện từ kho lưu trữ mở arXiv. Mục tiêu chính là giải quyết danh sách mã định danh arXiv được phân công, tải toàn bộ mã nguồn $\LaTeX$ nguyên bản (tất cả các phiên bản của từng bài viết) và thu thập thông tin trích dẫn có cấu trúc thông qua Semantic Scholar API.

Corpus thu thập được trong milestone này là nền tảng phục vụ các bài toán bóc tách cấu trúc (parsing) ở Milestone 2 và mô hình học máy (machine learning / citation matching) ở Milestone 3.

## 1.1. Dải ID và Phân công trong Nhóm

Nhóm được phân công dải gồm 20.000 bài báo arXiv (`configs/solo/ids_all.txt`), được chia đều cho 4 thành viên (mỗi thành viên 5.000 bài):
- **Hương (Baseline B):** Phụ trách kiến trúc baseline, discovery qua arXiv API, tải source qua HTTP endpoint `/src/`, quản trị repo sách và duyệt PR (`configs/team/ids_24120058.txt`: dải `2507.01659` – `2507.06658`).
- **Linh (D1):** Phụ trách cơ chế thu thập siêu dữ liệu qua OAI-PMH, quy trình giải nén trích xuất chỉ giữ `.tex`/`.bib` (loại bỏ hình ảnh) và kiểm định lưu trữ (`configs/team/ids_24120046.txt`: dải `2507.11659` – `2507.16658`).
- **Châu (D2):** Phụ trách cơ chế discovery qua Kaggle Dataset snapshot và module thu thập trích dẫn Semantic Scholar (`configs/team/ids_24120027.txt`: dải `2507.21659` – `2507.26658`).
- **Hiền (Benchmark & Metrics):** Phụ trách đo đạc tài nguyên (RAM, CPU, Disk, thời gian chạy), thu thập log, tổng hợp benchmark và cập nhật dữ liệu báo cáo (`configs/team/ids_24120085.txt`: dải `2505.15666` – `2505.20665`).

## 1.2. Sơ đồ Kiến trúc Pipeline Toàn thể

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

## 1.3. Cấu trúc 7 Chương Mục của Báo cáo

Báo cáo được chuẩn hoá thành 7 tệp tài liệu tương ứng với 7 phần chuyên sâu:

1. **`01_overview.md`**: Tổng quan về mục tiêu, dải phân công, sơ đồ kiến trúc hệ thống.
2. **`02_bounded_pipeline.md`**: Chiến lược điều phối tài nguyên Bounded Pipeline đa luồng (Three-Lane concurrency).
3. **`03_pipeline_stages.md`**: Toàn bộ các bước kỹ thuật trong pipeline: 3.1 Discovery, 3.2 Download, 3.3 Extract, 3.4 References, 3.5 Storage.
4. **`04_fault_tolerance.md`**: Cơ chế xử lý lỗi, phân loại mã lỗi, ghi tệp nguyên tử và kiểm định nhất quán.
5. **`05_results.md`**: Thống kê số lượng bài thành công, dung lượng trước/sau khi loại bỏ hình ảnh, phân bố version và trích dẫn.
6. **`06_evaluation.md`**: Đo lường hiệu năng thực tế (thời gian, RAM, đĩa) và so sánh giữa 4 cấu hình B, D1, D2, S1.
7. **`07_conclusion.md`**: Tổng kết thành quả, các bài học kinh nghiệm, hạn chế và định hướng phát triển cho Milestone 2.

