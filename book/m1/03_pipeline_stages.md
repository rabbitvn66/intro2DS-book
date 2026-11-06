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

## 3.3. Extract (Trích xuất chọn lọc .tex/.bib)

### Mục tiêu và luồng xử lý

Extract chuyển gói nguồn (archive) đã tải thành tập tệp `.tex` và `.bib` phục vụ Milestone 2 — Parsing. Đầu vào gồm danh sách phiên bản trong `metadata.json`, manifest của từng phiên bản và tệp `source.archive` do Download tạo. Đầu ra là thư mục `versions/v<N>/source/` cùng manifest được bổ sung danh sách tệp, định dạng, dung lượng và trạng thái trích xuất. Extract xử lý tệp cục bộ; việc gửi yêu cầu mạng và thử tải lại thuộc module Download.

Luồng gọi hàm trong [module extract][extract-pipeline-code] được tổ chức theo ba cấp:

1. `extract_paper()` đọc metadata có trạng thái `ok`, duyệt từng version và gọi `extract_version()`. Một version lỗi không ngăn vòng lặp xử lý các version còn lại; sau vòng lặp, hàm báo lỗi tổng hợp cho bộ điều phối nếu cần.
2. `extract_version()` kiểm tra schema và định danh trong manifest, sau đó kiểm tra khả năng tái sử dụng nguồn đã có. Chỉ khi cần trích xuất và `download_status = ok`, hàm mới gọi `extract_source()`.
3. `extract_source()` nhận diện nội dung, trích xuất vào thư mục tạm và công bố `source/` khi hoàn tất. Hàm trả kết quả cho `extract_version()` cập nhật manifest; bản thân `extract_source()` không ghi manifest.

Cách phân tách này giữ thao tác xử lý archive độc lập với quản lý trạng thái theo phiên bản, đồng thời cho phép kiểm thử trích xuất bằng dữ liệu cục bộ.

### Nhận diện định dạng và trích xuất chọn lọc

Bộ trích xuất kiểm tra nội dung thay vì chỉ tin phần mở rộng hoặc kết quả nhận diện sơ bộ của Download. Nếu gặp chữ ký gzip, chương trình giải nén có giới hạn ra tệp tạm rồi tiếp tục nhận diện dữ liệu bên trong. Các nhánh trong [`extract_source()`][extract-source-code] gồm:

| Dạng nguồn | Cách xử lý | Giá trị `source_format` |
|:---|:---|:---|
| Tar, kể cả tar không có chữ ký `ustar` | Thử mở bằng `tarfile`, duyệt các mục | `tar` |
| Gzip chứa tar | Giải lớp gzip rồi xử lý tar | `tar.gz` |
| TeX đơn | Nhận diện lệnh TeX trong 64 KiB đầu, lưu thành `main.tex` | `tex` |
| Gzip chứa TeX đơn | Giải gzip, nhận diện TeX, lưu thành `main.tex` | `gz` |
| Dữ liệu nhận diện là PDF | Không chuyển đổi sang TeX; kết quả không có tệp nguồn TeX | `pdf`, hoặc `gz` nếu có lớp gzip |
| Dữ liệu không nhận diện, như ZIP hoặc HTML | Trả lỗi định dạng không hỗ trợ | `unknown`, hoặc `gz` nếu đã nhận diện lớp gzip |

Nhận diện TeX đơn sử dụng các mẫu lệnh như `\documentclass`, `\begin`, `\input`; loại phần chú thích khi dò mẫu và từ chối phần đầu chứa byte NUL hoặc dấu hiệu HTML. Đây là quy tắc nhận diện dựa trên mẫu lệnh, chưa phải phân tích cú pháp TeX. Với tar, việc chọn tệp dựa trên hậu tố `.tex`/`.bib`, không phân biệt hoa thường. Chương trình đọc từng tệp thường, nhưng chỉ ghi những tệp được chọn vào thư mục đầu ra; ảnh, tệp định dạng và các loại tệp khác vẫn được đọc để kiểm tra kích thước và phát hiện dữ liệu bị cắt. [`_is_tex()` và `_extract_tar()`][extract-tar-code].

Các tệp được sao chép ở chế độ nhị phân, giữ nguyên byte, bảng mã và ký tự xuống dòng. Đường dẫn con được bảo toàn sau chuẩn hóa tiền tố như `./`, chẳng hạn `sections/intro.tex` vẫn nằm trong `source/sections/intro.tex`. Điều này giữ quan hệ đường dẫn cho `\input`, `\include` và tệp tài liệu tham khảo ở bước Parsing. Tệp TeX đơn dùng tên ổn định `main.tex`; quy tắc này không đổi tên các tệp bên trong tar.

### Giới hạn tài nguyên và nguồn không an toàn

[`ExtractionLimits`][extract-tar-code] quy định mặc định: archive tối đa **256 MiB**, tổng byte tệp giải nén **512 MiB**, mỗi tệp **64 MiB** và tối đa **10.000 mục**. Bộ đọc tar còn giới hạn ngân sách đọc header của một mục ở 1 MiB; luồng giải gzip có ngưỡng byte riêng với phần dự phòng cho header/padding. Các giới hạn chính có thể được truyền qua `extraction_limits`. Ngưỡng archive được kiểm tra sau khi tải, nên không phải giới hạn dung lượng nhận qua mạng.

Bộ trích xuất tự sao chép tệp thay vì gọi `extractall`. Các [hàm kiểm tra đường dẫn][schema-code] từ chối đường dẫn tuyệt đối, `..`, đường dẫn Windows không phù hợp và symlink trong đường dẫn dữ liệu. Bộ xử lý tar từ chối liên kết mềm/cứng, tệp thiết bị, FIFO, mục lưu tệp thưa (sparse file) và đường dẫn trùng sau chuẩn hóa, kể cả ở mục không được giữ. Những kiểm tra này giới hạn phạm vi ghi tệp và mức mở rộng dữ liệu; bản triển khai hiện tại chưa đặt thời hạn xử lý hay giới hạn cứng CPU/RAM cho trích xuất. Cơ chế cô lập lỗi và ghi tệp được trình bày tại [](04_fault_tolerance.md).

### Manifest, trạng thái và tái sử dụng kết quả

Sau trích xuất, `extract_version()` cập nhật `extract_status`, `source_format`, `source_files`, ba trường dung lượng và `error_code`, đồng thời giữ các trường khác, bao gồm `parse_status`. Ba số đo có ý nghĩa khác nhau:

| Trường | Phạm vi đo |
|:---|:---|
| `archive_bytes` | Kích thước tệp đầu vào trước giải nén |
| `unpacked_total_bytes` | Tổng byte mọi tệp thường trong tar, kể cả tệp bị lọc, không tính header/padding; với nguồn đơn là kích thước dữ liệu sau giải gzip nếu có |
| `kept_source_bytes` | Tổng byte các tệp `.tex`/`.bib` được giữ |

Hai tổng dung lượng sau giải nén và sau lọc chỉ được ghi khi xử lý hoàn tất; phép đo chưa xác định được biểu diễn bằng `null`. Khi không xác định lại được kích thước archive, giá trị đã biết trong manifest được giữ. Trạng thái được phân biệt như sau:

- `ok`: có ít nhất một tệp `.tex`, `error_code = null`.
- `empty`: dữ liệu nhận diện là PDF hoặc tar xử lý được nhưng không có `.tex`, kèm `NO_TEX_SOURCE`; nếu tar chỉ có `.bib`, các tệp này vẫn được giữ.
- `failed`: nguồn hỏng, không hỗ trợ hoặc không thể xử lý theo các điều kiện kiểm tra; không được diễn giải thành kết quả rỗng hợp lệ.

Với manifest đã `ok`/`empty`, [`_completed_source()`][extract-cache-code] kiểm tra các tệp khai báo, hậu tố, quan hệ trạng thái và tổng kích thước trước khi dùng lại; không cần archive còn tồn tại. Khi source đã được công bố nhưng manifest chưa ghi xong, bộ trích xuất có thể trích xuất lại vào thư mục tạm rồi [so sánh tập tệp và từng byte][extract-compare-code] với nguồn cũ. Nguồn khác biệt không bị ghi đè. Kiểm tra cache đã hoàn tất dựa trên danh sách tệp và kích thước, chưa sử dụng mã băm; chi tiết phục hồi nằm ở mục 4.5 của [](04_fault_tolerance.md).

### Vai trò đối với Milestone 2

Tập `.tex`/`.bib`, đường dẫn tương đối và danh sách tệp theo phiên bản tạo đầu vào có tổ chức cho Parsing. Giữ nguyên byte cho phép bước sau lựa chọn cách giải mã phù hợp, còn `empty` giúp phân biệt không có TeX với lỗi thu thập. Tuy nhiên, trạng thái `ok` chưa chứng minh TeX đúng cú pháp hoặc biên dịch được: Extract chưa chọn tệp chính, phân tích quan hệ phụ thuộc hay loại trùng giữa các version. Việc lọc ảnh, `.sty` và `.cls` phục vụ corpus văn bản/BibTeX; tập tệp giữ lại có thể thiếu tệp phụ thuộc để tái biên dịch tài liệu.

---

## 3.4. References (Thu thập trích dẫn Semantic Scholar — Châu phụ trách)

*(Endpoint Semantic Scholar, các field yêu cầu, lọc `externalIds.ArXiv`, giữ mọi reference cục bộ, rate limit 1 req/s, API key, xử lý lỗi 429. Lưu ý: Semantic Scholar không phân biệt reference theo từng version.)*

---

## 3.5. Storage (Tổ chức lưu trữ và mô hình dữ liệu)

### Vai trò và cấu trúc lưu trữ

Dữ liệu của từng bài báo được tổ chức độc lập theo cấu trúc thư mục phân cấp theo lần chạy, bài báo và phiên bản. Các công đoạn ghi kết quả trực tiếp vào vị trí chuẩn; [hàm tích hợp `store_paper()`][storage-hook-code] ở cuối pipeline kiểm định các kết quả đó và ghi `validation.json`. Storage không sao chép corpus sang một hệ lưu trữ thứ hai hoặc tạo cơ sở dữ liệu.

```text
experiments/<run_id>/
├── run.json                         # Cấu hình, danh sách ID, môi trường và trạng thái lần chạy
├── events.jsonl                     # Nhật ký nghiệp vụ của pipeline
├── metrics_events.jsonl             # Thời gian thao tác/attempt, mẫu RAM và dung lượng đĩa
├── papers/
│   └── <paper_key>/                 # Ví dụ: 2507-01659
│       ├── metadata.json           # Metadata và danh sách version của bài
│       ├── references.json         # References cấp bài, dùng chung các version
│       ├── validation.json         # Báo cáo kiểm định dữ liệu của bài
│       └── versions/
│           ├── v1/
│           │   ├── manifest.json   # Định danh, trạng thái và danh sách tệp của version
│           │   └── source/         # Các tệp .tex/.bib, giữ cấu trúc thư mục con
│           │       ├── main.tex
│           │       └── references.bib
│           └── v2/
│               ├── manifest.json
│               └── source/
└── tmp/<paper_key>/v<N>/
    └── source.archive              # Archive trung gian do Download ghi
```

`experiments` là giá trị `output_root` mặc định; các tên tệp trong sơ đồ minh họa cách tổ chức, không yêu cầu mỗi version phải có `main.tex` hoặc `.bib`. Hàm [`paper_key()`][common-io-code] đổi `.` thành `-` và `/` thành `__`, còn ID gốc được giữ trong JSON. Ví dụ, `hep-th/9901001` được lưu dưới `hep-th__9901001`. Mỗi version dùng thư mục `v<N>` và `versioned_id = <arxiv_id>v<N>`, giúp các phiên bản không ghi chồng lên nhau. `papers/` chứa corpus và các bản ghi mô tả; `tmp/` chứa dữ liệu trung gian; hai JSONL phục vụ theo dõi thực thi. Extract không tự xóa archive sau xử lý.

### Mô hình dữ liệu và các bản ghi JSON

Hai nhóm dữ liệu nội dung là **bài báo** và **references**, được lưu bằng JSON theo từng bài. Các quan hệ ID được kiểm tra bằng mã Python, chưa được triển khai thành khóa chính/khóa ngoại của cơ sở dữ liệu. Schema chung nằm trong [`schema.py`][schema-code] và các [hàm validation][validation-records-code]; việc một trường phải hiện diện không đồng nghĩa giá trị của trường luôn khác `null`.

**Metadata bài báo — `metadata.json`.** Bản ghi có đủ các trường sau:

| Nhóm trường | Kiểu và ý nghĩa |
|:---|:---|
| `arxiv_id` | Chuỗi base ID, không có hậu tố version |
| `title`, `authors` | Tiêu đề và danh sách chuỗi tên tác giả; cho phép `null` khi chưa biết |
| `submission_date`, `revised_dates` | Ngày v1 và danh sách ngày v2…vN theo ISO-8601; dữ liệu thiếu được giữ là `null`, một version không có revision dùng `[]` |
| `venue` | Chuỗi tên nơi công bố hoặc `null` |
| `versions`, `latest_version` | Danh sách số nguyên dương và version lớn nhất; có thể `null` khi discovery chưa xác định được |
| `status`, `error_code` | Trạng thái thu thập và mã lỗi dạng chuỗi hoặc `null` |

Metadata `ok` phải có danh sách version không rỗng, không trùng hoặc bị hở, với `latest_version` khớp version lớn nhất. Một số giá trị metadata thiếu được validator báo cảnh báo thay vì lỗi; Discovery có thể áp dụng điều kiện chặt hơn trước khi tạo bản ghi. Các trường bổ sung của từng nguồn discovery vẫn được giữ.

**Manifest phiên bản — `manifest.json`.** Manifest là bản ghi liên kết archive, source và trạng thái xử lý. Bộ trạng thái chung gồm `pending`, `running`, `ok`, `empty`, `failed` và `skipped`:

| Nhóm trường | Kiểu và ý nghĩa |
|:---|:---|
| `arxiv_id`, `version`, `versioned_id` | ID bài, số nguyên dương của version và định danh có hậu tố tương ứng |
| `download_status`, `extract_status`, `parse_status` | Trạng thái của từng công đoạn; M1 chưa thực hiện Parsing |
| `source_format`, `source_files` | Định dạng nguồn hoặc `null`; danh sách đường dẫn `.tex`/`.bib` tương đối với `source/` |
| `archive_path` | Đường dẫn tương đối với thư mục run hoặc `null` |
| `archive_bytes`, `unpacked_total_bytes`, `kept_source_bytes` | Số nguyên không âm hoặc `null`; định nghĩa tại mục 3.3 |
| `error_code` | Mã lỗi hoặc `null` |

**References — `references.json`.** Bản ghi bao ngoài gồm `arxiv_id`, `status`, `error_code`, `source`, `fetched_at` và danh sách `references`. Các trường `source`, `fetched_at` và `error_code` nhận chuỗi hoặc `null`; thời điểm thu thập khi có giá trị phải theo ISO-8601. Mỗi phần tử trong danh sách có schema:

| Trường | Kiểu và ý nghĩa |
|:---|:---|
| `arxiv_id` | ID bài đang trích dẫn, khớp ID trong bản ghi bao ngoài |
| `ref_arxiv_id` | ID arXiv của bài được trích dẫn, được phép `null` |
| `ref_title` | Tiêu đề bài được trích dẫn hoặc `null` |
| `ref_authors` | Danh sách chuỗi tên tác giả; có thể là `[]` |
| `ref_submission_date` | Ngày nộp bài được trích dẫn theo ISO-8601 hoặc `null` |
| `ref_s2_id` | ID Semantic Scholar của bài được trích dẫn hoặc `null` |

References đã chuẩn hóa không bị loại chỉ vì thiếu arXiv ID. Trong [hàm chuẩn hóa hiện tại][references-normalize-code], `ref_submission_date` luôn là `null` vì request không lấy ngày nộp; mục có `citedPaper = null` bị loại trước khi đến Storage. Storage kiểm tra những bản ghi đã nhận, không bổ sung lại các mục đó.

**Báo cáo kiểm định — `validation.json`.** Báo cáo gồm `arxiv_id`, `status` và `issues`; mỗi issue có `code`, `path`, `message`, `severity`. Đây là kết quả kiểm tra dữ liệu tại thời điểm thực hiện, không thay thế metadata hoặc manifest. Giá trị `null` biểu thị thông tin chưa biết, còn `empty` là trạng thái rỗng được xác nhận theo từng công đoạn. `schema_version` được lưu ở [cấp cấu hình/run][run-record-code]; hiện chưa có cơ chế chuyển đổi giữa các phiên bản schema cho các bản ghi này.

### Luồng ghi, đọc và nhật ký

Trách nhiệm ghi được phân chia theo công đoạn: Discovery ghi metadata; [`download_version()`][download-manifest-code] tạo manifest và archive; Extract cập nhật manifest và source; [hàm tích hợp References trong `main.py`][references-hook-code] ghi references. Storage đọc các bản ghi và tệp nguồn qua `validate_paper()`, sau đó ghi báo cáo kiểm định. Module còn cung cấp các hàm `load_metadata()`, `load_references()`, `load_manifest()` và `load_paper()`; hàm cuối trả các manifest theo khóa version nguyên. [API lưu/đọc Storage][storage-api-code] phân biệt tệp thiếu với JSON hỏng: tệp thiếu trả `None`, JSON hỏng gây ngoại lệ.

Các hàm `save_metadata()`, `save_references()` và `save_manifest()` có kiểm tra schema và bảo vệ bản ghi hoàn tất, nhưng các điểm ghi của pipeline chính nêu trên gọi trực tiếp `write_json_atomic()`. Vì vậy, cơ chế bảo vệ trong API `save_*` chưa phải chính sách ghi chung đã được toàn pipeline sử dụng.

[`write_json_atomic()`][common-io-code] ghi JSON bằng UTF-8, giữ ký tự Unicode với `ensure_ascii=False`, rồi thay thế tệp đích bằng `os.replace()` từ tệp `.tmp` cùng thư mục. Phạm vi nguyên tử là từng tệp; cơ chế này chưa tạo giao dịch giữa JSON và source, không có `fsync` hoặc khóa nhiều tiến trình ghi. Chi tiết xử lý gián đoạn nằm ở mục 4.3 của [](04_fault_tolerance.md).

[`events.jsonl`][business-log-code] ghi trạng thái nghiệp vụ theo `stage`/`status`, còn [`metrics_events.jsonl`][metrics-log-code] ghi sự kiện phép đo theo `stage`/`event`, cùng thời lượng, attempt hoặc mẫu tài nguyên. Cả hai ghi nối tiếp, mỗi dòng là một đối tượng JSON theo UTF-8; chúng không dùng cách thay thế nguyên tử của bản ghi JSON. Hai nhật ký hỗ trợ truy vết và đo đạc, trong khi metadata, manifest, references và validation mô tả dữ liệu đã lưu.

### Kiểm định corpus và tổng hợp trạng thái

Trong [`store_paper()`][storage-hook-code], luồng xử lý là gọi `validate_paper()` → ghi `validation.json` → ghi sự kiện Storage → trả báo cáo nếu `status = ok`; trạng thái khác làm hàm ném `CrawlError` với mã `SCHEMA_ERROR`. [`validate_paper()`][validation-paper-code] chỉ đọc, đối chiếu version được discovery với thư mục thực tế, rồi kiểm tra metadata, từng manifest/source và references. Bộ kiểm định không tự sửa hoặc xóa dữ liệu.

Các tiêu chí bao gồm định danh và kiểu dữ liệu, tính nhất quán danh sách version/trạng thái, đường dẫn an toàn, tệp nguồn thiếu hoặc không khai báo, cùng tổng kích thước so với `kept_source_bytes` khi có số đo. References thiếu metadata tùy chọn hoặc có bản ghi giống hệt được cảnh báo; các bản ghi không bị tự xóa. Chi tiết quy tắc và mã issue được trình bày tại [mục 4.6](04_fault_tolerance.md#m1-04-validation).

Trạng thái báo cáo được tổng hợp theo thứ tự ưu tiên: có vấn đề mức `error` thì `failed`; nếu không, có `IN_PROGRESS` thì `running`; còn vấn đề mức `pending` thì `pending`; các trường hợp còn lại là `ok`. Cảnh báo và thông tin về kết quả rỗng hợp lệ không tự làm báo cáo thất bại. Do đó, một version `empty + NO_TEX_SOURCE` vẫn có thể thuộc corpus hợp lệ, nhưng chưa có nguồn TeX để Parsing. `parse_status = pending` không làm M1 chưa hoàn tất. Trạng thái `pending`/`running` của báo cáo vẫn khiến hàm Storage báo lỗi cho bộ điều phối vì dữ liệu chưa sẵn sàng.

### Liên hệ với các milestone tiếp theo

Manifest chỉ ra tệp nguồn và trạng thái theo version; validation giúp bước sau phân biệt corpus hoàn tất, nguồn rỗng hợp lệ và dữ liệu thiếu hoặc không nhất quán. References cấp bài giữ các trường định danh và giá trị thiếu để phục vụ đối sánh ở Milestone 3. Tuy nhiên, validation hiện kiểm tra cấu trúc, trạng thái và một phần tính toàn vẹn hệ thống tệp: chưa tính mã băm nguồn, xác nhận archive còn tồn tại, phân tích cú pháp TeX/BibTeX hay xác minh tính đầy đủ của trích dẫn. Vì vậy, báo cáo `ok` xác nhận dữ liệu đáp ứng các kiểm tra M1 đã triển khai; khả năng phân tích và chất lượng đối sánh cần được kiểm tra ở các milestone tương ứng.

[extract-pipeline-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L259-L333
[extract-source-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L162-L236
[extract-tar-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L21-L137
[extract-cache-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L239-L256
[extract-compare-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L140-L159
[schema-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/schema.py#L8-L71
[storage-hook-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/storage.py#L178-L213
[storage-api-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/storage.py#L14-L196
[validation-records-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/validation.py#L42-L245
[validation-paper-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/validation.py#L264-L357
[common-io-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/utils/common.py#L33-L86
[references-normalize-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/references.py#L110-L201
[download-manifest-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/downloader/http.py#L56-L108
[references-hook-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/main.py#L66-L109
[business-log-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/utils/common.py#L89-L127
[metrics-log-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/metrics.py#L282-L319
[run-record-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/main.py#L31-L58
