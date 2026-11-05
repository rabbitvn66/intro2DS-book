---
title: 3. Các bước trong Pipeline
short_title: 03. Các bước Pipeline
label: m1-03-pipeline-stages
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 3. Các bước trong Pipeline

Quy trình thu thập dữ liệu (crawling pipeline) được xây dựng theo kiến trúc phân tách rõ ràng thành 5 công đoạn liên hoàn: Discovery, Download, Extract, References và Storage. Mỗi công đoạn đảm nhiệm một vai trò chuyên biệt và được đo kiểm nghiêm ngặt.

---

## 3.1. Discovery (Khám phá siêu dữ liệu)

Giai đoạn Khám phá (Discovery) có nhiệm vụ chuyển đổi danh sách các mã định danh arXiv thô (dạng base ID như `2507.01659`) thành siêu dữ liệu đầy đủ của bài báo, đặc biệt là xác định toàn bộ các phiên bản khả dụng ($v1, v2, \dots, vN$) để phục vụ cho các bước tải mã nguồn tiếp theo.

### Phương pháp 1: arXiv API (Cấu hình Baseline B — Hương phụ trách)
arXiv API tại địa chỉ `https://export.arxiv.org/api/query` hỗ trợ truy vấn trực tiếp bằng tham số `id_list`. Khi gửi truy vấn với một base ID (ví dụ: `2507.01659`), API trả về một mục Atom XML chứa siêu dữ liệu của phiên bản **mới nhất** (latest version).

```python
import arxiv

client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)
search = arxiv.Search(id_list=["2507.01659"], max_results=1)
paper = next(client.results(search))
print(f"Title: {paper.title}")
print(f"Latest ID: {paper.get_short_id()}")  # Trả về hậu tố phiên bản, ví dụ: '2507.01659v3'
```

- **Xác định danh sách phiên bản:** Mã định danh arXiv tuân theo quy ước `{base_id}v{version_number}`. Hệ thống tách hậu tố `vN` để xác định số phiên bản mới nhất là $N$, từ đó nội suy danh sách mọi phiên bản cần tải là `versions = [1, 2, ..., N]`.
- **Thu thập ngày sửa đổi (`revised_dates`):**
  - *Chiến lược 1 (Gộp theo lô):* Gộp danh sách các phiên bản trung gian `[f"{id}v{n}" for n in range(2, N)]` vào một yêu cầu API duy nhất để lấy mốc thời gian `entry.updated`.
  - *Chiến lược 2 (Fallback Abs HTML):* arXiv API trả về HTTP 500 khi truy vấn các mã định danh dạng cũ (`hep-th/9901001vN`). Khi đó, hệ thống tự động fallback phân tích khối `Submission history` từ trang web tóm tắt HTML:
    ```python
    _HISTORY_BLOCK = re.compile(r'<div class="submission-history">(.*?)</div>', re.DOTALL)
    _HISTORY_ENTRY = re.compile(
        r"\[v(\d+)\].*?</strong>\s*(\w{3}, \d{1,2} \w{3} \d{4} \d{2}:\d{2}:\d{2}) UTC", re.DOTALL
    )
    ```
- **Điều tốc và Xử lý lỗi:** Đối tượng `Throttle(min_interval=3.0)` ghi nhận mốc thời gian truy cập `time.monotonic()` trước và sau mỗi request để đảm bảo giãn cách tối thiểu 3 giây. Ngoại lệ được chuẩn hoá thành `HTTP_429`, `HTTP_5XX`, `TIMEOUT`, `NOT_FOUND`...

### Phương pháp 2: OAI-PMH (Cấu hình D1 — Linh phụ trách)
*(Endpoint `oaipmh.arxiv.org/oai`, verb `GetRecord`/`ListRecords`, resumption token, bổ sung tra version bằng cách nào, so với arXiv API.)*

### Phương pháp 3: Kaggle Dataset Snapshot (Cấu hình D2 — Châu phụ trách)
*(Dataset Cornell-University/arxiv, cách đọc JSONL/`kagglehub`, lọc theo ID, thiếu thông tin version thì bổ sung thế nào, snapshot cập nhật đến ngày nào.)*

---

## 3.2. Download (Tải mã nguồn và tầng HTTP — Hương phụ trách)

Sau khi xác định danh sách phiên bản, khâu Download tải gói mã nguồn nguyên bản của từng phiên bản về máy cục bộ.

### Điểm cuối phục vụ mã nguồn
arXiv cung cấp mã nguồn thông qua máy chủ lưu trữ chuyên dụng `export.arxiv.org`. Thay vì tải file PDF đã biên dịch, pipeline nhắm thẳng vào endpoint:
$$\text{https://export.arxiv.org/src/}\{arxiv\_id\}\text{v}\{version\}$$

*Lưu ý:* Tuyệt đối không cào trực tiếp qua `arxiv.org` để tránh bị cơ chế chống bot chặn HTTP 403.

### Tầng HTTP chung (`src/utils/http.py`)
- **Điều tốc tập trung (Throttle):** Duy trì giãn cách $\ge 3.0$s giữa các request bằng đồng hồ đơn điệu `time.monotonic()`.
- **Streaming & Ghi nguyên tử:** Thiết lập `stream=True` và đọc theo khối `chunk_size=65536` (64 KB). Tệp tải về được ghi tạm vào `.part` cùng thư mục (`NamedTemporaryFile`), sau khi tải xong mới gọi `os.replace()` hoán đổi nguyên tử sang tên tệp chính thức, tránh để lại tệp hỏng.
- **Retry & Exponential Backoff:** Đối với các mã lỗi có thể thử lại (408, 429, 500, 502, 503, 504 hoặc đứt cáp mạng), hệ thống thử lại tối đa 3 lần. Nếu có tiêu đề `Retry-After`, hệ thống chờ theo chỉ định; nếu không, áp dụng lùi số nhân $\text{delay} = \min(\text{base\_delay} \times 2^{\text{attempt}}, 30\text{s})$.
- **Nhận diện định dạng tệp:** Kiểm tra magic bytes ở đầu tệp nén để phân loại:
  - `\x1f\x8b` kèm chữ ký `ustar` bên trong: gói `tar.gz`.
  - `\x1f\x8b` thông thường: tệp đơn `gz`.
  - Chữ ký `ustar` tại offset 257: gói `tar`.
  - Chữ ký `%PDF` tại byte đầu: bản `pdf` (không có nguồn TeX).
  - Không khớp: `unknown` (ghi nhận mã lỗi `UNSUPPORTED_FORMAT`).

---

## 3.3. Extract (Trích xuất chọn lọc .tex/.bib — Linh phụ trách)

*(Nhận diện định dạng: tar, tar.gz, gz, tex, pdf; chỉ giữ `.tex`/`.bib`; version không TeX → `empty` + `NO_TEX_SOURCE`; cơ chế sàng lọc trong luồng giải nén; giới hạn tài nguyên an toàn ExtractionLimits chống Zip-bomb.)*

---

## 3.4. References (Thu thập trích dẫn Semantic Scholar — Châu phụ trách)

*(Endpoint Semantic Scholar, các field yêu cầu, lọc `externalIds.ArXiv`, giữ mọi reference cục bộ, rate limit 1 req/s, API key, xử lý lỗi 429. Lưu ý: Semantic Scholar không phân biệt reference theo từng version.)*

---

## 3.5. Storage (Tổ chức lưu trữ và mô hình dữ liệu)

Dữ liệu của từng bài báo được tổ chức độc lập theo cấu trúc thư mục phân cấp rõ ràng:

```
experiments/<run_id>/
├── run.json                                   # Thông tin phiên chạy, cấu hình, môi trường
├── events.jsonl                               # Nhật ký sự kiện chi tiết từng stage
├── metrics_events.jsonl                       # Dữ liệu đo đạc RAM, CPU, thời gian từng attempt
└── papers/
    └── <paper_key>/                           # Ví dụ: 2507-01659
        ├── metadata.json                      # Thông tin discovery: title, authors, versions...
        ├── references.json                    # Dữ liệu trích dẫn từ Semantic Scholar
        └── versions/
            ├── v1/
            │   ├── manifest.json              # Trạng thái tải và trích xuất của v1
            │   └── source/                    # CHỈ chứa file .tex và .bib
            │       ├── main.tex
            │       └── references.bib
            └── v2/
                ├── manifest.json
                └── source/
                    └── ...
```

### Đặc tả 2 Bảng Dữ liệu Chuẩn Đầu ra

1. **Bảng `papers`:**
   - `arxiv_id` (string, khoá chính): Mã định danh gốc của bài báo (vd: `2507.01659`).
   - `title` (string): Tiêu đề bài báo.
   - `authors` (list[string]): Danh sách tác giả.
   - `submission_date` (string, ISO-8601): Mốc thời gian nộp bản đầu tiên $v1$.
   - `revised_dates` (list[string]): Danh sách mốc thời gian của các phiên bản sửa đổi ($v2 \dots vN$).
   - `venue` (string, nullable): Tên tạp chí hoặc hội nghị xuất bản (nếu có).

2. **Bảng `references`:**
   - `arxiv_id` (string, khoá ngoại): Mã định danh bài báo trích dẫn (citing paper).
   - `ref_arxiv_id` (string, bắt buộc): Mã arXiv của bài báo được trích dẫn (cited paper).
   - `ref_title` (string): Tiêu đề của bài báo được trích dẫn.
   - `ref_authors` (list[string]): Danh sách tác giả của bài báo được trích dẫn.
   - `ref_submission_date` (string): Mốc thời gian nộp của bài báo được trích dẫn.
   - `ref_s2_id` (string): Mã định danh Semantic Scholar của bài viết trích dẫn.

