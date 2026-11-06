---
title: 4. Xử lý lỗi và Tính nhất quán dữ liệu
short_title: 04. Xử lý lỗi & Nhất quán
label: m1-04-fault-tolerance
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 4. Xử lý lỗi và Tính nhất quán dữ liệu

Việc thu thập hàng chục nghìn bài báo phụ thuộc vào các dịch vụ bên ngoài (arXiv, Semantic Scholar) và kéo dài nhiều giờ, nên lỗi mạng, phản hồi bất thường, giới hạn tần suất hoặc việc tiến trình bị ngắt giữa chừng là điều chắc chắn xảy ra. Hệ thống được thiết kế để: (1) phân loại lỗi bằng mã ổn định, (2) thử lại đúng loại lỗi có thể phục hồi, (3) không bao giờ để lại tệp ghi dở, (4) cô lập lỗi theo từng version, stage và bài báo, (5) chạy lại được mà không lặp công việc đã xong, và (6) kiểm định corpus sau khi ghi.

## 4.1. Phân loại lỗi và mã lỗi ổn định

Mọi lỗi nghiệp vụ kế thừa lớp `CrawlError(message, error_code, status_code)` trong `src/utils/errors.py`. Mã lỗi là chuỗi cố định, được ghi vào `events.jsonl`, `manifest.json` và `references.json`, nhờ đó có thể thống kê nguyên nhân thất bại ở [](05_results.md).

| Mã lỗi | Nơi phát sinh | Điều kiện | Thử lại |
|:---|:---|:---|:---:|
| `TIMEOUT` | `utils/http.py` | Quá thời gian chờ, hoặc HTTP 408 | Có |
| `NETWORK_ERROR` | `utils/http.py` | Mất kết nối, luồng dữ liệu bị cắt; lỗi TLS (`SSLError`) | Có (riêng TLS: không) |
| `HTTP_429` | `utils/http.py` | Vượt giới hạn tần suất | Có |
| `HTTP_5XX` | `utils/http.py` | Máy chủ trả lỗi 5xx | Có với 500, 502, 503, 504 |
| `NOT_FOUND` | `utils/http.py`, discovery, extract | HTTP 404, OAI-PMH `idDoesNotExist` hoặc bản ghi đã xóa, hoặc thiếu tệp nén khi giải nén | Không |
| `HTTP_4XX` | `utils/http.py` | Lỗi client khác 404 | Không |
| `REQUEST_ERROR` | `utils/http.py` | Lỗi `requests` không thuộc các nhóm trên | Không |
| `INVALID_RESPONSE` | `utils/http.py`, discovery, downloader, extract | Phản hồi sai cấu trúc hoặc không giải mã được JSON, thiếu trường, thân phản hồi rỗng; thư mục `source/` cũ khác với kết quả giải nén lại | Không |
| `INVALID_ID` | discovery | ID có hậu tố `vN` hoặc sai cú pháp | Không |
| `CORRUPT_SOURCE` | `downloader/http.py`, `extract.py` | gzip/tar hỏng, đường dẫn nguy hiểm, vượt giới hạn giải nén | Không |
| `UNSUPPORTED_FORMAT` | `extract.py` | Định dạng nguồn không nhận diện được | Không |
| `SCHEMA_ERROR` | `stages/storage.py` | Corpus của bài không vượt qua kiểm định | Không |

Hai mã dưới đây **không phải lỗi** mà là trạng thái rỗng hợp lệ, được kiểm định chặt ở mục [4.6](#m1-04-validation):

- `NO_TEX_SOURCE` (định nghĩa trong `src/schema.py`): version không có tệp `.tex` (ví dụ chỉ nộp PDF); manifest có `extract_status = empty`.
- `NO_REFERENCES_RETURNED`: Semantic Scholar không trả về trích dẫn nào; `references.json` có `status = empty` và danh sách rỗng.

Ngoài ra, nếu người dùng nhấn Ctrl+C, sự kiện `pipeline` được ghi với mã `INTERRUPTED` và `run_status = interrupted`.

## 4.2. Cơ chế thử lại, lùi cấp số nhân và giãn cách request

Toàn bộ request HTTP đi qua `request_with_retry` và `download_file` trong `src/utils/http.py`, nên mọi nguồn dữ liệu dùng chung một chính sách.

```{mermaid}
flowchart TD
  A[Throttle.wait<br/>giãn cách tối thiểu] --> B[Gửi request]
  B --> C{Kết quả}
  C -->|2xx| D[Trả về dữ liệu]
  C -->|Lỗi tạm thời<br/>408 / 429 / 500 / 502 / 503 / 504<br/>timeout, mất kết nối| E{Còn lượt thử?}
  C -->|Lỗi vĩnh viễn<br/>404, 4xx khác, SSLError| F[Raise CrawlError]
  E -->|Có| G[Chờ theo Retry-After<br/>hoặc backoff] --> A
  E -->|Không| F
```

**Số lần thử.** `max_retries` là số lần thử *thêm* sau lần gọi đầu tiên; với `max_retries = 3`, một thao tác có tối đa 4 request. Riêng Semantic Scholar dùng `s2_max_retries` và `s2_backoff_base_seconds` (mặc định cấu hình là 3 và 5 giây).

**Thời gian chờ.** Nếu phản hồi có tiêu đề `Retry-After` hợp lệ (số giây hoặc ngày giờ HTTP), hệ thống chờ đúng khoảng đó; ngược lại dùng lùi cấp số nhân. Cả hai bị chặn trên bởi `MAX_DELAY = 30` giây:

$$
\text{delay} = \min\left(\text{base\_delay} \times 2^{\text{attempt}},\ 30\right)
$$

trong đó `attempt` đếm từ 0 cho lần thử lại đầu tiên và `base_delay` lấy từ `backoff_base_seconds` (mặc định 2 giây). Nếu `Retry-After` là ngày giờ đã qua thì không chờ; nếu giá trị không đọc được thì dùng lùi cấp số nhân.

**Giãn cách (pacing).** Lớp `Throttle` bảo đảm hai lệnh gọi liên tiếp cách nhau ít nhất `min_interval` giây, dùng đồng hồ đơn điệu `time.monotonic()` để không bị ảnh hưởng khi đổi giờ hệ thống. `Throttle.wait()` được gọi trước **mọi** lần thử, kể cả lần thử lại, nên retry không làm vượt giới hạn của arXiv (`arxiv_delay_seconds`, mặc định 3 giây). Semantic Scholar có bộ giãn cách riêng: 1 giây giữa hai request khi có `S2_API_KEY`, 3 giây khi không có.

:::{note}
Lỗi TLS (`SSLError`) không được thử lại vì thử lại không thay đổi kết quả, và lỗi 4xx khác 408/429 là lỗi của yêu cầu nên cũng không thử lại.
:::

Mỗi lần thử gọi hook `on_attempt` để ghi mã trạng thái, mã lỗi và thời lượng thuần của request (không tính thời gian chờ) vào `metrics_events.jsonl`. Lỗi trong hook chỉ được ghi log, không làm gián đoạn request.

## 4.3. Ghi tệp nguyên tử

Một tiến trình bị dừng đột ngột có thể để lại tệp JSON cụt hoặc tệp nén thiếu dữ liệu. Để tránh điều đó, mọi tệp quan trọng đều được ghi ra tệp tạm trong **cùng thư mục** rồi đổi tên bằng `os.replace`. Người đọc chỉ nhìn thấy phiên bản cũ hoặc phiên bản mới hoàn chỉnh, không bao giờ thấy phiên bản ghi dở.

```python
# src/utils/common.py
def write_json_atomic(path: pathlib.Path, data: Any) -> None:
    """Write via a temp file + rename so a crash never leaves a half-written file."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)  # never leave a stale .tmp behind; the old file stays intact
        raise
```

Cơ chế này áp dụng cho từng loại dữ liệu:

| Dữ liệu | Cách ghi |
|:---|:---|
| `metadata.json`, `manifest.json`, `references.json`, `validation.json`, `run.json` | `write_json_atomic` (tệp tạm `*.tmp`) |
| Tệp nén tải về (`source.archive`) | `download_file` ghi tệp tạm `*.part` trong cùng thư mục, sau khi stream xong mới `os.replace`; lần thử thất bại xóa tệp tạm và không đụng tới tệp đích cũ |
| Thư mục `source/` | Giải nén vào thư mục tạm `.extract-*` cùng cấp, rồi `os.replace` sang `source/` |

Nếu `source/` đã có nội dung, hệ thống giải nén lại vào thư mục tạm và so sánh; kết quả khác nhau thì dừng với mã `INVALID_RESPONSE` ("inspect before retrying") thay vì ghi đè. Các lỗi hệ thống tệp, gzip hoặc tar khi giải nén đều quy về `CORRUPT_SOURCE`.

Khi có ngoại lệ, tệp tạm bị xóa và tệp cũ giữ nguyên.

(m1-04-root-cause)=
## 4.4. Cô lập lỗi và xác định nguyên nhân gốc

Lỗi được khoanh vùng ở ba tầng để một sự cố cục bộ không làm hỏng cả lần chạy:

1. **Theo version**: `download_paper` bắt mọi ngoại lệ của từng version, ghi `manifest.json` với `download_status = failed` và mã lỗi, rồi tiếp tục version kế tiếp.
2. **Theo stage**: `run_stage` bọc mỗi stage (extract, references, storage). 2. **Theo stage**: `run_stage` bọc mỗi stage (extract, references, storage). Stage lỗi được ghi event `failed` kèm thông điệp rút gọn (tối đa 300 ký tự), các stage còn lại vẫn chạy. Ở lớp bọc này, trường `error_code` là *tên lớp ngoại lệ* (ví dụ `CrawlError`). Mã lỗi ổn định ở mục 4.1 được ghi bởi chính stage trong `manifest.json`, `metadata.json`, `references.json` và các event do stage tự ghi (ví dụ `SCHEMA_ERROR` của storage).
3. **Theo bài báo**: mỗi bài kết thúc bằng đúng một event `paper` ghi trạng thái `ok` hoặc `failed`, tổng thời gian và số version `ok/failed/skipped`. Bài lỗi không dừng vòng lặp qua các bài khác.

Khi một bài thất bại, hàm `root_error_code` xác định **nguyên nhân gốc** theo thứ tự: discovery, rồi tải/trích xuất của từng version (đọc từ `manifest.json`), rồi references, cuối cùng mới đến lỗi của stage. Thứ tự này tránh việc `SCHEMA_ERROR` của storage (chỉ là hệ quả của dữ liệu thiếu) che mất nguyên nhân thật, chẳng hạn `HTTP_429`.

:::{note}
Nếu không có nguồn nào ở các bước trên mang mã lỗi, `root_error_code` trả về tên lớp ngoại lệ của stage đầu tiên bị lỗi. Do đó ở trường hợp hiếm này, event `paper` có thể chứa tên lớp thay vì mã ổn định. Đây là một hạn chế được nêu ở [](07_conclusion.md).
:::

Ở cấu hình `A_PIPELINE`, nguyên tắc cô lập được giữ nguyên: mỗi worker bọc stage bằng `try/except`, và khối `finally` luôn đẩy tín hiệu dừng, chờ hàng đợi cạn rồi `join` các luồng, nên dù luồng chính gặp ngoại lệ, các bài đang dở vẫn được các worker xử lý xong (xem [](02_bounded_pipeline.md)).

## 4.5. Chạy lại không trùng lặp (idempotency và warm resume)

Trạng thái hoàn tất của từng khâu được lưu bền vững trên đĩa nên một lần chạy dở có thể tiếp tục bằng cách chạy lại với **cùng `run_id`**. Nếu `run_id` chứa `{timestamp}` hoặc là `auto`, mỗi lần chạy sẽ tạo thư mục mới (chạy lạnh, `cache_mode = cold`).

| Stage | Điều kiện bỏ qua | Khi gặp trạng thái khác |
|:---|:---|:---|
| Discovery | `metadata.json` có `status = ok` **và** (`latest_version = 1` hoặc `revised_dates` khác `null`) | `failed`, hoặc bài `ok` nhưng chưa lấy được ngày sửa đổi, được truy vấn lại |
| Download | Mỗi version có `manifest.download_status = ok` | Version `failed` được tải lại |
| Extract | `extract_status` là `ok` hoặc `empty` **và** nguồn đã lưu khớp manifest | Nếu không khớp: báo `CORRUPT_SOURCE`, yêu cầu kiểm tra thay vì tự ghi đè |
| References | `references.json` có `status` là `ok` hoặc `empty` | `failed` được thu thập lại |

Hai chi tiết bảo vệ dữ liệu đã hoàn tất:

- Với Extract, "khớp" nghĩa là mọi tệp khai báo tồn tại, chỉ gồm `.tex`/`.bib`, có `.tex` nếu trạng thái là `ok`, và tổng dung lượng bằng `kept_source_bytes` (hàm `_completed_source`).
- Hàm `_save` trong `storage.py` (dùng bởi `save_metadata`, `save_references`, `save_manifest`) bảo vệ bản ghi đã hoàn tất: nếu bản cũ là `ok` hoặc `empty` thì bản mới không được kém hơn, và với `metadata`/`references` chỉ cho phép *bổ sung* thông tin (`_preserves`); riêng `manifest` đã hoàn tất bị đóng băng hoàn toàn.

`run.json` ghi nhận ngữ cảnh chạy lại:

| Trường | Ý nghĩa |
|:---|:---|
| `cache_mode` | `cold` khi chạy mới, `warm` khi đã có `run.json` trước đó |
| `first_started_at` | Mốc bắt đầu đầu tiên, được giữ nguyên qua các lần resume để tính đúng tổng thời gian |
| `run_status` | `running`, `completed`, `interrupted` (Ctrl+C) hoặc `crashed` (ngoại lệ không bắt được) |

Khối `finally` của `main` luôn ghi `finished_at`, `run_status` và `wall_seconds`, kể cả khi bị ngắt. Lưu ý `run_status = completed` chỉ có nghĩa quy trình điều phối đã kết thúc, không bảo đảm mọi bài đều thành công; số bài thành công phải đọc từ các event `paper`.

(m1-04-validation)=
## 4.6. Kiểm định tính nhất quán của corpus

Stage cuối của mỗi bài là `store_paper` (`src/stages/storage.py`). Stage này gọi `validate_paper` (`src/stages/validation.py`), ghi kết quả vào `papers/<key>/validation.json` và không sao chép hay sửa dữ liệu gốc. Bộ kiểm định chỉ đọc, **không bao giờ xóa hay tự sửa** bản ghi.

Các nhóm kiểm tra chính:

| Đối tượng | Quy tắc | Mã vấn đề |
|:---|:---|:---|
| ID | Đúng cú pháp arXiv và khớp thư mục chứa | `INVALID_ID`, `IDENTITY_MISMATCH` |
| Metadata | `latest_version` bằng version lớn nhất; danh sách version không bị hở; số ngày chỉnh sửa bằng số version trừ 1 | `VERSION_MISMATCH`, `MISSING_VERSION`, `DATE_COUNT_MISMATCH` |
| Manifest | Đủ trường bắt buộc; `kept_source_bytes` không vượt `unpacked_total_bytes` | `MISSING_FIELD`, `INVALID_SIZE` |
| Tệp nguồn | Chỉ `.tex`/`.bib`; không đường dẫn thoát thư mục hay symlink; không thiếu, không thừa so với khai báo; tổng dung lượng khớp manifest | `INVALID_SOURCE_TYPE`, `UNSAFE_PATH`, `MISSING_SOURCE`, `UNDECLARED_SOURCE`, `SIZE_MISMATCH` |
| Trạng thái `ok` | Phải có ít nhất một `.tex` và không có mã lỗi | `INCONSISTENT_STATUS` |
| Trạng thái `empty` | Không có `.tex` và `error_code = NO_TEX_SOURCE` | `INCONSISTENT_STATUS` |
| References | `empty` phải là danh sách rỗng kèm `NO_REFERENCES_RETURNED`; trích dẫn thiếu metadata vẫn được giữ; dòng trùng lặp chỉ cảnh báo | `INCONSISTENT_STATUS`, `MISSING_METADATA`, `DUPLICATE_REFERENCE` |

Mỗi vấn đề có mức độ (`severity`): `error`, `warning`, `info` hoặc `pending`. Trạng thái báo cáo được suy ra như sau:

- `failed` nếu có ít nhất một `error`;
- `running` nếu còn stage đang chạy;
- `pending` nếu có phần chưa thu thập;
- `ok` trong các trường hợp còn lại.

Nếu trạng thái báo cáo khác `ok`, `store_paper` ném `CrawlError` với mã `SCHEMA_ERROR`, khiến stage storage thất bại và bài được đánh dấu `failed`; nguyên nhân gốc vẫn được truy ngược theo mục ßßß[4.4](#m1-04-root-cause).

Ngoài kiểm định từng bài, `validate_run` duyệt toàn bộ ID đầu vào để phát hiện ID bị trùng (`DUPLICATE_PAPER`), thư mục bài lạ không thuộc danh sách đầu vào (`UNEXPECTED_PAPER`) hoặc tên thư mục không khớp ID. Các mã nêu trong bảng chỉ là nhóm chính; bộ kiểm định còn dùng thêm các mã như `DUPLICATE_VERSION`, `INVALID_FORMAT`, `MISSING_ERROR_CODE`, `NOT_COLLECTED` và `IN_PROGRESS` (hai mã cuối có mức `pending`). Phần kiểm thử offline của các cơ chế trong chương này nằm ở `tests/test_http.py`, `tests/test_extract.py`, `tests/test_storage.py`, `tests/test_validation.py` và `tests/test_errors.py`.