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

Sau khi Discovery xác định danh sách phiên bản, khâu Download tải gói mã nguồn nguyên bản của **từng phiên bản** `v1 … vN` về máy cục bộ. Mỗi phiên bản là một request riêng, các request chạy tuần tự và dùng chung một bộ điều tốc.

### Điểm cuối phục vụ mã nguồn

arXiv phục vụ mã nguồn qua máy chủ mirror `export.arxiv.org`. Thay vì tải tệp PDF đã biên dịch, pipeline gọi trực tiếp endpoint có hậu tố phiên bản:

```text
https://export.arxiv.org/src/{arxiv_id}v{version}
```

| Lựa chọn | Lý do |
|:--|:--|
| `export.arxiv.org`, không phải `arxiv.org` | Đề bài yêu cầu trỏ tải tự động vào mirror này. Cào dày đặc trang chính `arxiv.org` sẽ bị nhận diện là robot và bị chặn HTTP 403 |
| Hậu tố `vN` trong URL | Đây là cách duy nhất lấy từng bản sửa đổi riêng lẻ, đúng yêu cầu thu thập mọi phiên bản |
| Tải từng bài, không tải kho S3 | Kho nguồn đầy đủ cỡ nhiều TB và tính phí theo người yêu cầu (requester-pays); nhóm chỉ cần 5.000 bài trong dải được giao |
| `requests` cùng tầng HTTP tự viết | Giãn cách, retry, ghi nguyên tử và đo lường nằm ở một chỗ (`utils/http.py`) và dùng chung cho các module gọi HTTP |

### Quy trình cho mỗi bài (`src/downloader/http.py`)

1. Đọc `metadata.json`. Nếu Discovery chưa `ok` hoặc không có danh sách phiên bản thì bỏ qua bài (ghi event `skipped`).
2. Với mỗi phiên bản trong `versions`: nếu `manifest.json` đã có `download_status = ok` thì bỏ qua (resume).
3. Tải về `tmp/<paper_key>/v<N>/source.archive`. Phản hồi rỗng (0 byte) bị coi là lỗi `INVALID_RESPONSE` và tệp rỗng bị xóa.
4. Nhận diện định dạng, rồi ghi `manifest.json` với `download_status = ok`.
5. Nếu lỗi, `manifest.json` được ghi với `download_status = failed` kèm `error_code`; ngoại lệ ngoài dự kiến cũng để lại manifest (mã `INVALID_RESPONSE`). Một phiên bản lỗi **không** làm dừng các phiên bản còn lại của bài. Hàm trả về số phiên bản `ok / failed / skipped`.

### Tầng HTTP chung (`src/utils/http.py`)

- **Điều tốc tập trung (`Throttle`).** Giãn cách tối thiểu $\ge 3.0$ giây (tham số `arxiv_delay_seconds`) giữa hai request, đo bằng đồng hồ đơn điệu `time.monotonic()`. `Throttle.wait()` được gọi trước **mọi** lần thử, kể cả lần thử lại, nên retry không làm vượt giới hạn của arXiv.
- **Streaming và ghi nguyên tử.** Request dùng `stream=True` và đọc theo khối 64 KB (`chunk_size=65536`). Dữ liệu được ghi vào tệp tạm `.part` trong cùng thư mục (`NamedTemporaryFile`); chỉ khi tải xong mới `os.replace()` sang tên chính thức. Lần thử lỗi sẽ xóa tệp tạm và không đụng tới tệp đích cũ.
- **Thử lại và lùi cấp số nhân.** Các tình huống được thử lại: mã 408, 429, 500, 502, 503, 504, timeout (30 giây mỗi request), mất kết nối và luồng dữ liệu bị cắt. Với `max_retries = 3`, mỗi lần tải có tối đa 4 request, và mỗi lần thử lại tải lại từ đầu. Nếu có tiêu đề `Retry-After` thì chờ theo đó, nếu không thì chờ theo công thức dưới đây; cả hai đều bị chặn trên 30 giây:

$$\text{delay} = \min\left(\text{base\_delay} \times 2^{\text{attempt}},\ 30\right), \quad \text{base\_delay} = 2\ \text{giây (mặc định)}$$

- **Không thử lại.** Lỗi TLS (`SSLError`, báo `NETWORK_ERROR`), HTTP 404 (`NOT_FOUND`) và các mã 4xx khác (`HTTP_4XX`), vì thử lại không thay đổi kết quả. Danh sách mã lỗi đầy đủ ở [](#m1-04-fault-tolerance).
- **Nhận diện bằng header.** Mỗi request mang `User-Agent` mô tả rõ nhóm và email liên hệ, theo yêu cầu của arXiv.
- **Hook đo lường.** Mỗi lần thử gọi hook `on_attempt` ghi mã trạng thái và thời lượng thuần của request (không tính thời gian chờ) phục vụ thống kê ở [](#m1-05-results).

### Nhận diện định dạng và manifest (`src/downloader/http.py`)

Hàm `detect_format` chỉ đọc *magic bytes* (512 byte đầu của tệp):

| Dấu hiệu | `source_format` |
|:--|:--|
| Bắt đầu bằng `\x1f\x8b`; sau khi giải nén gzip, byte 257–261 là `ustar` | `tar.gz` |
| Bắt đầu bằng `\x1f\x8b`, không có `ustar` bên trong | `gz` (một tệp đơn) |
| `ustar` tại offset 257 | `tar` |
| Bắt đầu bằng `%PDF` | `pdf` (bài chỉ có PDF, không có nguồn TeX) |
| Không khớp mẫu nào | `unknown` |

- Gzip không đọc được gây lỗi `CORRUPT_SOURCE` ngay tại bước này, và phiên bản được đánh dấu `failed`.
- Định dạng `pdf` và `unknown` **không** bị coi là lỗi tải: `download_status` vẫn là `ok`. Việc chúng có dùng được hay không (mã `NO_TEX_SOURCE`, `UNSUPPORTED_FORMAT`) do bước Extract quyết định ở mục 3.3.

Mỗi phiên bản có một `versions/vN/manifest.json`. Khâu Download điền các trường sau, còn các trường của Extract giữ trạng thái chờ:

| Nhóm trường | Trường | Giá trị sau Download |
|:--|:--|:--|
| Định danh | `arxiv_id`, `version`, `versioned_id` | Ví dụ `2507.01659`, `2`, `2507.01659v2` |
| Kết quả tải | `download_status`, `error_code`, `source_format`, `archive_path`, `archive_bytes` | `ok` hoặc `failed`; đường dẫn tương đối so với thư mục chạy |
| Dành cho Extract | `extract_status`, `parse_status`, `source_files`, `unpacked_total_bytes`, `kept_source_bytes` | `pending` hoặc rỗng, được điền ở bước sau |

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

