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

Giai đoạn Discovery có nhiệm vụ thu thập thông tin mô tả của các bài báo khoa học từ arXiv, tạo cơ sở cho các công đoạn xử lý tiếp theo. Đầu vào của giai đoạn này là danh sách mã định danh arXiv (arxiv_id) không chứa hậu tố phiên bản, được đọc từ tệp cấu hình ids_file. Thông qua arXiv API, hệ thống xác định các thông tin như tiêu đề, tác giả, ngày nộp, thông tin xuất bản và đặc biệt là số lượng phiên bản của từng bài báo.
Hệ thống gửi yêu cầu tới arXiv API theo từng batch. Danh sách ID đầu vào được chia thành các nhóm có kích thước xác định bởi discovery_batch_size. Quy trình thực hiện gồm các bước:
1. Đọc danh sách arXiv ID và chia thành các batch.
2. Kiểm tra dữ liệu đã tồn tại để bỏ qua những bài báo có metadata hoàn chỉnh.
3. Gửi truy vấn arXiv API cho các ID cần thu thập trong batch.
4. Ánh xạ kết quả trả về với đúng arXiv ID, không phụ thuộc vào thứ tự phản hồi.
5. Xác định phiên bản mới nhất và xây dựng danh sách các phiên bản của từng bài.
6. Thu thập ngày sửa đổi của các phiên bản và lưu metadata vào tệp JSON.


Đối với mỗi bài báo, arXiv API cung cấp thông tin của phiên bản mới nhất. Từ hậu tố phiên bản vN, hệ thống xác định được tổng số phiên bản và xây dựng danh sách từ v1 đến vN. Bên cạnh đó, Discovery thu thập thời điểm nộp phiên bản đầu tiên và thời điểm sửa đổi của các phiên bản tiếp theo.

Đối với các arXiv ID dạng mới, hệ thống có thể gom những phiên bản trung gian vào các truy vấn theo batch để lấy ngày cập nhật. Ngày cập nhật của phiên bản mới nhất được lấy trực tiếp từ kết quả Discovery ban đầu.

Trong trường hợp truy vấn lịch sử phiên bản không thành công hoặc không trả về đầy đủ dữ liệu, hệ thống sử dụng cơ chế dự phòng (fallback), bao gồm truy vấn riêng từng bài báo hoặc phân tích thông tin Submission history trên trang abstract của arXiv. Nếu không thể thu thập đầy đủ ngày sửa đổi nhưng vẫn xác định được danh sách phiên bản, bài báo vẫn có thể được tiếp tục xử lý. Khi đó, revised_dates được để là null và thông tin cảnh báo được ghi vào nhật ký.


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

Giai đoạn References sử dụng Semantic Scholar Academic Graph API để thu thập danh sách các tài liệu khoa học được một bài báo trích dẫn. Đầu vào của giai đoạn này là mã định danh arXiv của bài báo nguồn. Đầu ra là danh sách các tài liệu được bài báo đó trích dẫn, cùng những thông tin mô tả như tiêu đề, tác giả và mã định danh.

Hệ thống gửi yêu cầu đến endpoint của Semantic Scholar Academic Graph API theo cấu trúc:

https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}/references

Trong đó, {arxiv_id} là mã định danh của bài báo cần thu thập tài liệu tham khảo.
Semantic Scholar có thể trả về nhiều tài liệu tham khảo cho một bài báo. Do đó, hệ thống sử dụng cơ chế pagination để thu thập dữ liệu qua nhiều trang. Mỗi request yêu cầu tối đa 1000 references. Sau khi nhận phản hồi, hệ thống kiểm tra trường next. Nếu next chứa offset của trang tiếp theo, hệ thống tiếp tục gửi request với offset tương ứng. Ngược lại, nếu next là null hoặc không tồn tại, quá trình thu thập kết thúc.
Trước khi tiếp tục sang trang mới, hệ thống kiểm tra cấu trúc phản hồi, tính hợp lệ của các trường và việc offset có thực sự tăng hay không. Điều này giúp tránh xử lý dữ liệu sai cấu trúc hoặc lặp vô hạn khi API trả về thông tin phân trang không hợp lệ.

Dữ liệu nhận được từ Semantic Scholar được chuyển đổi về một schema thống nhất để phục vụ lưu trữ và xử lý ở các milestone tiếp theo.
| Trường dữ liệu | Ý nghĩa |
|---|---|
| `arxiv_id` | Mã arXiv của bài báo nguồn đang trích dẫn |
| `ref_arxiv_id` | Mã arXiv của tài liệu được trích dẫn, nếu xác định được |
| `ref_title` | Tiêu đề tài liệu được trích dẫn |
| `ref_authors` | Danh sách tác giả của tài liệu được trích dẫn |
| `ref_submission_date` | Ngày nộp của tài liệu được trích dẫn |
| `ref_s2_id` | Mã Semantic Scholar của tài liệu được trích dẫn |

Trong quá trình chuẩn hóa, hệ thống lấy ref_arxiv_id từ trường externalIds.ArXiv. Nếu Semantic Scholar không cung cấp mã arXiv, giá trị này được lưu là null thay vì loại bỏ toàn bộ reference. Việc giữ lại các references không có arXiv ID giúp hạn chế mất dữ liệu và tạo điều kiện sử dụng các thuộc tính khác, chẳng hạn tiêu đề, tác giả hoặc Semantic Scholar ID, cho các bước đối sánh sau này. Nếu một mục trích dẫn không có đối tượng citedPaper, hệ thống bỏ qua mục đó vì không có đủ đối tượng dữ liệu để chuẩn hóa.

Đối với ref_submission_date, implementation hiện tại chưa thu thập trường này từ API nên giá trị được để là null. Đây là một giới hạn của dữ liệu References tại thời điểm triển khai.

Ngoài ra, Semantic Scholar trả về danh sách tài liệu tham khảo ở mức bài báo; hệ thống hiện chưa phân biệt danh sách references riêng cho từng phiên bản v1, v2, ... của cùng một bài báo arXiv.

Đối với Semantic Scholar API có thể giới hạn tần suất truy cập. Do đó, giữa các yêu cầu gửi được cách nhau tối thiểu 3 giây. Nếu gặp các lỗi HTTP có thể thử lại. Khi phản hồi có header Retry-After, hệ thống ưu tiên thời gian chờ do máy chủ cung cấp. Trong các trường hợp khác, thời gian chờ giữa những lần thử lại được tính theo exponential backoff

Cấu hình pilot sử dụng:

| Tham số | Giá trị | Ý nghĩa |
|---|---:|---|
| `pipeline_references_queue` | 4 | Số công việc tối đa trong hàng đợi References |
| `s2_max_retries` | 3 | Số lần thử lại bổ sung tối đa |
| `s2_backoff_base_seconds` | 5 | Thời gian cơ sở tính exponential backoff |


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

