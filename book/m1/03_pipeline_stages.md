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

Luồng gọi hàm trong [module Extract][extract-pipeline-code] tách việc duyệt bài, quản lý trạng thái phiên bản và xử lý archive. `extract_paper()` đọc metadata hợp lệ rồi gọi `extract_version()` cho từng version; hàm này chỉ gọi `extract_source()` khi cần trích xuất và Download đã thành công. Sơ đồ thể hiện các nhánh xử lý chính:

```text
extract_paper(): đọc metadata hợp lệ, lặp từng version
    │
    ▼
extract_version(): kiểm tra manifest và nguồn hiện có
    ├─ Manifest sai / nguồn đã hoàn tất không khớp → Báo lỗi
    ├─ Đã hoàn tất, nguồn khớp                    → Tái sử dụng
    ├─ Download chưa ok                          → Chưa trích xuất
    └─ Cần trích xuất, download ok
         │ source.archive từ Download
         ▼
       extract_source(): nhận diện → giải nén khi cần → lọc .tex/.bib
         ├─ Hoàn tất → công bố hoặc dùng lại source/
         │              ├─ Có .tex    → ok
         │              └─ Không .tex → empty + NO_TEX_SOURCE
         └─ Lỗi → không công bố nguồn mới → failed
         │ trả kết quả
         ▼
       extract_version(): cập nhật manifest.json
```

`extract_source()` trả kết quả nhưng không ghi manifest. Các lỗi kiểm tra trước lời gọi này được báo trực tiếp, không đi qua nhánh cập nhật kết quả trích xuất. `extract_paper()` tiếp tục các version còn lại trước khi báo lỗi tổng hợp; cơ chế cô lập lỗi được trình bày tại [mục 4.4](04_fault_tolerance.md).

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

Kết quả `ok`/`empty` chỉ được tái sử dụng sau khi [`_completed_source()`][extract-cache-code] kiểm tra nguồn theo manifest. Khi cần trích xuất, kết quả được chuẩn bị trong thư mục tạm và chỉ được công bố sau xử lý; nguồn cũ khác biệt không bị ghi đè. Điều kiện cache, phục hồi sau gián đoạn và giới hạn của việc kiểm tra kích thước được trình bày tại [mục 4.3 và 4.5](04_fault_tolerance.md).

### Vai trò đối với Milestone 2

Tập `.tex`/`.bib`, đường dẫn tương đối và danh sách tệp theo phiên bản tạo đầu vào có tổ chức cho Parsing. Giữ nguyên byte cho phép bước sau lựa chọn cách giải mã phù hợp, còn `empty` giúp phân biệt không có TeX với lỗi thu thập. Tuy nhiên, trạng thái `ok` chưa chứng minh TeX đúng cú pháp hoặc biên dịch được: Extract chưa chọn tệp chính, phân tích quan hệ phụ thuộc hay loại trùng giữa các version. Việc lọc ảnh, `.sty` và `.cls` phục vụ corpus văn bản/BibTeX; tập tệp giữ lại có thể thiếu tệp phụ thuộc để tái biên dịch tài liệu.

---

## 3.4. References (Thu thập trích dẫn Semantic Scholar — Châu phụ trách)

*(Endpoint Semantic Scholar, các field yêu cầu, lọc `externalIds.ArXiv`, giữ mọi reference cục bộ, rate limit 1 req/s, API key, xử lý lỗi 429. Lưu ý: Semantic Scholar không phân biệt reference theo từng version.)*

---

## 3.5. Storage (Tổ chức lưu trữ và mô hình dữ liệu)

### Vai trò và cấu trúc lưu trữ

Dữ liệu của từng bài báo được tổ chức độc lập theo ba cấp: lần chạy, bài báo và phiên bản. Các công đoạn ghi kết quả trực tiếp vào vị trí chuẩn; [hàm tích hợp `store_paper()`][storage-hook-code] ở cuối pipeline kiểm định dữ liệu đã có và ghi `validation.json`. Module không sao chép corpus sang một hệ lưu trữ thứ hai hoặc tạo cơ sở dữ liệu.

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

`experiments` là `output_root` mặc định; tên tệp trong sơ đồ chỉ minh họa cách tổ chức, không yêu cầu mỗi version có `main.tex` hoặc `.bib`. Hàm [`paper_key()`][common-io-code] đổi `.` thành `-` và `/` thành `__`, chẳng hạn `hep-th/9901001` thành `hep-th__9901001`; ID gốc vẫn nằm trong JSON. `papers/` chứa corpus và bản ghi mô tả, `tmp/` chứa archive trung gian, còn JSONL phục vụ theo dõi thực thi. Extract không tự xóa archive sau xử lý.

### Thiết kế schema và hợp đồng dữ liệu

Pipeline nhiều module cần thống nhất tên trường, kiểu dữ liệu và ý nghĩa trạng thái để một công đoạn có thể đọc kết quả của công đoạn trước. Trong bản triển khai, hợp đồng dữ liệu (*Data Contract*) được thể hiện qua [`schema.py`][schema-code] và [các hàm validation][validation-records-code]: Discovery cung cấp ID và danh sách version; Download khởi tạo manifest; Extract bổ sung danh sách tệp và số đo vào manifest; References tạo các bản ghi cùng ID bài trích dẫn; Storage đối chiếu các thành phần đó. Không phải mọi điểm ghi đều gọi validator trước khi ghi, nên hợp đồng còn được kiểm tra ở bước cuối.

Về mặt kỹ thuật, ba cấp lưu trữ phân tách ba loại ngữ cảnh: `run` lưu cấu hình, đầu vào và môi trường; `paper` giữ metadata cùng references của một bài; `version` giữ archive, nguồn và trạng thái riêng của từng bản nộp. Base ID nhận diện bài xuyên suốt pipeline, còn `versioned_id = <arxiv_id>v<N>` xác định chính xác bản được tải. Cấu trúc này hỗ trợ đối chiếu nhiều phiên bản mà không trộn tệp nguồn của chúng.

| Biểu diễn | Ý nghĩa trong hợp đồng dữ liệu |
|:---|:---|
| `null` | Chưa biết giá trị hoặc chưa có số đo; không thay bằng 0 |
| `[]` | Danh sách không có phần tử; ý nghĩa phụ thuộc trường và trạng thái đi kèm |
| `empty` | Kết quả rỗng đã được công đoạn xác nhận, như nguồn không có TeX |
| `pending` | Công đoạn chưa hoàn tất; chưa thể kết luận kết quả rỗng |
| `failed` | Công đoạn thất bại; mã lỗi và báo cáo kiểm định hỗ trợ truy nguyên |

Các quy ước này cho phép validator phân biệt thiếu dữ liệu với kết quả rỗng, giúp các module quyết định tái sử dụng kết quả, đồng thời hỗ trợ gỡ lỗi qua ID/version. [Ngữ cảnh trong `run.json`][run-record-code] hỗ trợ truy vết điều kiện thực nghiệm; các điều kiện resume cụ thể thuộc [mục 4.5](04_fault_tolerance.md).

Bản triển khai hiện sử dụng JSON cho bản ghi và JSONL cho nhật ký. Xét về kỹ thuật, cách tổ chức này thuận tiện để kiểm tra từng bài và trao đổi dữ liệu mà chưa cần dịch vụ cơ sở dữ liệu; đổi lại, truy vấn tổng hợp cần quét nhiều tệp và chưa có giao dịch chung giữa các bản ghi.

### Schema nội bộ phục vụ Milestone 1

Metadata, manifest và references lưu kết quả thu thập; validation lưu kết quả kiểm tra. `run.json` cùng các nhật ký lưu ngữ cảnh vận hành. Chúng phục vụ pipeline M1, chưa phải bộ bảng bàn giao cuối. Các bảng dưới mô tả field nội bộ; một trường phải hiện diện không đồng nghĩa giá trị luôn khác `null`.

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

**Báo cáo kiểm định — `validation.json`.** Báo cáo gồm `arxiv_id`, `status` và `issues`; mỗi issue có `code`, `path`, `message`, `severity`. Đây là kết quả kiểm tra dữ liệu tại thời điểm thực hiện, không thay thế metadata hoặc manifest. `schema_version` được lưu ở [cấp cấu hình/run][run-record-code]; hiện chưa có cơ chế chuyển đổi giữa các phiên bản schema cho các bản ghi này.

### Luồng dữ liệu và kiểm định

Sơ đồ phân định module tạo dữ liệu và bước Storage đọc, kiểm định dữ liệu. [`download_version()`][download-manifest-code] tạo manifest/archive, Extract cập nhật manifest và source, còn [hàm tích hợp References][references-hook-code] ghi references:

```text
Discovery  ── ghi ──> metadata.json
Download   ── ghi ──> manifest.json + source.archive
                                  │
Extract    <── đọc ────────────────┘
           └── ghi ──> source/ + manifest.json cập nhật
References ── ghi ──> references.json

metadata.json + manifest.json + source/ + references.json
    │
    ▼
store_paper() ── gọi ──> validate_paper() [chỉ đọc]
    ▲                        │
    └──── issues + status ────┘
    │
    └── ghi validation.json + log → báo kết quả cho pipeline
```

[`validate_paper()`][validation-paper-code] chỉ đọc: kiểm tra định danh/schema, đối chiếu version, manifest, tệp nguồn, kích thước khi có số đo và references. Báo cáo ưu tiên `failed` khi có lỗi; nếu không, còn công đoạn đang chạy thì `running`, còn dữ liệu chưa thu thập thì `pending`, còn lại là `ok`. Cảnh báo và kết quả rỗng hợp lệ không tự làm báo cáo thất bại. [`store_paper()`][storage-hook-code] ghi báo cáo và nhật ký, trả báo cáo khi `ok`, còn trạng thái khác ném `CrawlError` với mã `SCHEMA_ERROR`. Tiêu chí và mã issue chi tiết nằm ở [mục 4.6](04_fault_tolerance.md#m1-04-validation).

[API đọc Storage][storage-api-code] còn cung cấp `load_metadata()`, `load_references()`, `load_manifest()` và `load_paper()` để nạp dữ liệu; hàm cuối trả các manifest theo khóa version nguyên. Các API `save_*` có kiểm tra và bảo vệ riêng, nhưng những điểm ghi của pipeline chính gọi trực tiếp `write_json_atomic()`, chưa dùng chúng làm chính sách ghi chung.

[`write_json_atomic()`][common-io-code] ghi JSON UTF-8 qua tệp tạm rồi `os.replace()` theo từng tệp; đây chưa phải giao dịch nhiều tệp hoặc bảo đảm bền vững tuyệt đối khi mất điện. [Nhật ký nghiệp vụ][business-log-code] dùng `stage`/`status`, còn [nhật ký phép đo][metrics-log-code] dùng `stage`/`event`; cả hai ghi nối tiếp từng đối tượng JSON UTF-8 trên một dòng. Chi tiết ghi nguyên tử, chống ghi đè và phục hồi được dẫn sang [mục 4.3–4.5](04_fault_tolerance.md).

### Phân biệt với schema bàn giao toàn dự án

Theo [yêu cầu chung của đồ án][course-project], dữ liệu được bàn giao cuối ở Milestone 3. Bộ bảng được xác định theo từng milestone:

| Bảng đầu ra | Milestone quy định | Nguồn dữ liệu hoặc vai trò |
|:---|:---|:---|
| `papers` | M1 | Metadata bài báo thu thập được |
| `references` | M1 | Metadata trích dẫn đủ điều kiện xuất |
| `elements` | M2 | Các phần tử nội dung đã phân tích và loại trùng |
| `hierarchy` | M2 | Quan hệ nút–cha theo phiên bản |
| `bibtex` | M2 | Các mục BibTeX đã chuẩn hóa và hợp nhất |
| `predictions` | M3 | Kết quả đối sánh references |

[Yêu cầu M1][course-crawling] cho phép nhóm tự tổ chức corpus và yêu cầu giữ mọi reference đã thu thập cục bộ; bảng `references` bàn giao chỉ chứa bản ghi có `ref_arxiv_id` khác `null`. Vì vậy, nullable trong JSON nội bộ không mâu thuẫn với ràng buộc ID bắt buộc ở bảng cuối. Metadata/references M1 là nguồn để ánh xạ sang hai bảng tương ứng, không phải xuất nguyên bản ghi bao ngoài kèm trạng thái vận hành. Manifest và validation không phải hai bảng đầu ra cuối.

[Yêu cầu M2][course-parsing] quy định đầu ra phân tích cấu trúc; [M3][course-matching] quy định đối sánh và bàn giao dữ liệu dưới dạng Parquet phân mảnh. Pipeline M1 đang khảo sát chưa tạo `elements`, `hierarchy`, `bibtex`, `predictions` hoặc xuất sáu bảng Parquet. Manifest và báo cáo validation hỗ trợ chuẩn bị đầu vào cho các bước đó; `parse_status = pending` không làm M1 chưa hoàn tất, nhưng `ok` ở M1 cũng chưa chứng minh TeX/BibTeX phân tích được hoặc references đầy đủ. Giới hạn kiểm định được trình bày tại [mục 4.6](04_fault_tolerance.md#m1-04-validation).

[extract-pipeline-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L259-L333
[extract-source-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L162-L236
[extract-tar-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L21-L137
[extract-cache-code]: https://github.com/qaztyhn/intro2DS/blob/e5f8700919a00f2031a47e576ca27ea96757d961/src/stages/extract.py#L239-L256
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
[course-project]: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/
[course-crawling]: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/
[course-parsing]: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/parsing/
[course-matching]: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/matching/
