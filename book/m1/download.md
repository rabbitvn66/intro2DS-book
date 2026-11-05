---
title: Tải mã nguồn và tầng HTTP
short_title: Download / HTTP
label: m1-download
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# Tải mã nguồn và tầng HTTP

Sau khi bước Discovery xác định được danh sách toàn bộ các phiên bản của bài báo, bước Tải mã nguồn (Download) chịu trách nhiệm tải tệp lưu trữ mã nguồn nguyên bản của từng phiên bản về máy cục bộ. Đây là một trong những phần tốn nhiều tài nguyên mạng và thời gian nhất trong toàn bộ quy trình.

## 1. Điểm cuối phục vụ mã nguồn (Source Endpoint)

arXiv cung cấp mã nguồn thông qua máy chủ lưu trữ chuyên dụng `export.arxiv.org`. Thay vì tải file PDF đã biên dịch, pipeline nhắm thẳng vào endpoint:

$$\text{https://export.arxiv.org/src/}\{arxiv\_id\}\text{v}\{version\}$$

Ví dụ: `https://export.arxiv.org/src/2507.01659v1`, `https://export.arxiv.org/src/2507.01659v2`.

*Lưu ý quan trọng:* Tuyệt đối không gửi request tự động đến trang web chính `arxiv.org`, vì hệ thống phát hiện bot tự động của arXiv sẽ lập tức kích hoạt mã chặn HTTP 403. Việc sử dụng máy chủ mirror `export.arxiv.org` kết hợp định danh phiên bản tường minh là phương pháp chính thức và ổn định nhất.

## 2. Kiến trúc Tầng HTTP Chung (`src/utils/http.py`)

Toàn bộ các yêu cầu mạng trong dự án (bao gồm tải file, gọi API arXiv, Semantic Scholar, OAI-PMH) đều bắt buộc đi qua tầng kết nối HTTP dùng chung được xây dựng trên thư viện `requests`. Tầng này đảm bảo các tính năng cốt lõi:

### 2.1. Điều tốc tập trung (Throttling)
Để tuân thủ lịch sự quy tắc của máy chủ (etiquette):
- Máy chủ arXiv yêu cầu khoảng cách tối thiểu giữa hai request liên tiếp là 3.0 giây.
- Semantic Scholar yêu cầu khoảng cách 1.0 giây (nếu có API Key) hoặc 3.0 giây (nếu dùng public pool).
- Lớp `Throttle` sử dụng đồng hồ đơn điệu `time.monotonic()` độc lập với thay đổi đồng hồ hệ thống, tự động tính toán thời gian trễ còn lại và chèn `time.sleep(remaining)` ngay trước mỗi lần thực hiện request.

### 2.2. Chiến lược Tải tệp an toàn (Streaming & Atomic Replacement)
Khi tải tệp lưu trữ mã nguồn lớn qua hàm `download_file()`:
- **Tải theo luồng (Streaming):** Thiết lập `stream=True` và đọc tệp theo từng khối nhỏ `chunk_size=65536` (64 KB). Kỹ thuật này giúp bộ nhớ RAM không bị phình to khi tải các tệp nén dung lượng hàng chục megabyte.
- **Ghi tệp nguyên tử (Atomic replace):** Tệp nén được ghi tạm thời vào một tệp phần `.part` nằm cùng thư mục đích (`NamedTemporaryFile(dir=destination.parent, suffix=".part")`). Chỉ khi quá trình tải kết thúc trọn vẹn và đóng luồng thành công, hàm `os.replace()` mới hoán đổi nguyên tử sang tên tệp chính thức. Nếu có lỗi mạng giữa chừng, tệp `.part` bị xoá bỏ và không để lại tệp hỏng trong hệ thống lưu trữ.

### 2.3. Cơ chế Thử lại và Lùi cấp số nhân (Retry & Exponential Backoff)
Đối với các lỗi có thể tự hồi phục (mã trạng thái 408, 429, 500, 502, 503, 504 hoặc lỗi đường truyền mạng `ConnectionError`, `Timeout`, `ChunkedEncodingError`):
- Hệ thống hỗ trợ thử lại tối đa `max_retries = 3` lần.
- Kiểm tra tiêu đề `Retry-After` trả về từ máy chủ (dưới dạng giây hoặc HTTP-date). Nếu có, hệ thống sẽ chờ đúng khoảng thời gian chỉ định (tối đa chặn ở `MAX_DELAY = 30` giây).
- Nếu không có tiêu đề trên, áp dụng công thức lùi cấp số nhân:
  $$\text{delay} = \min(\text{base\_delay} \times 2^{\text{attempt}}, \text{MAX\_DELAY})$$

```python
# Trích đoạn cơ chế tính delay và retry trong src/utils/http.py
def get_retry_delay(response, attempt, base_delay=1.0):
    if response is not None:
        retry_after = (response.headers.get("Retry-After") or "").strip()
        if retry_after:
            if retry_after.isdecimal():
                return min(float(retry_after), MAX_DELAY)
            try:
                retry_date = parsedate_to_datetime(retry_after)
                if retry_date.tzinfo is not None:
                    now = datetime.now(timezone.utc)
                    delay = (retry_date - now).total_seconds()
                    if math.isfinite(delay):
                        return min(max(0, delay), MAX_DELAY)
            except (TypeError, ValueError, OverflowError):
                pass
    return min(base_delay * 2**attempt, MAX_DELAY)
```

## 3. Nhận dạng định dạng tệp (Magic Bytes Detection)

Sau khi tệp nén nguồn được lưu vào `tmp/<paper_key>/v<N>/source.archive`, hàm `detect_format` sẽ kiểm tra các byte đầu danh nghĩa (magic bytes) để phân loại tệp mà không phụ thuộc vào phần mở rộng của tệp:

| Magic Bytes / Chữ ký | Định dạng nhận diện | Hành vi xử lý tiếp theo |
|:--|:--|:--|
| `\x1f\x8b` (Gzip header) kèm chữ ký tar `ustar` bên trong | `tar.gz` | Gói nén chứa nhiều file mã nguồn TeX/BibTeX |
| `\x1f\x8b` (Gzip header) thông thường | `gz` | Một file đơn lẻ được nén bằng gzip |
| Chữ ký `ustar` tại offset 257 | `tar` | Gói tar không nén |
| Chữ ký `%PDF` tại byte đầu | `pdf` | Phiên bản chỉ có bản PDF, không nộp kèm source TeX |
| Không khớp các chữ ký trên | `unknown` | Định dạng không hỗ trợ, ghi nhận lỗi `UNSUPPORTED_FORMAT` |

## 4. Bảng phân loại mã lỗi và Cách xử lý

Mọi trạng thái lỗi trong quá trình kết nối và tải nguồn đều được chuẩn hoá vào lớp ngoại lệ kế thừa từ `CrawlError`:

| Mã lỗi (`error_code`) | Trạng thái HTTP | Tình huống phát sinh | Biện pháp xử lý của Pipeline |
|:--|:--|:--|:--|
| `TIMEOUT` | 408 / None | Hết thời gian chờ kết nối hoặc tải luồng | Thử lại tối đa 3 lần với backoff; nếu hết lượt ghi nhận thất bại và chuyển sang phiên bản tiếp theo. |
| `HTTP_429` | 429 | Gửi quá số lượng request cho phép | Tôn trọng giá trị `Retry-After` của máy chủ, tạm ngưng tiến trình trước khi thử lại. |
| `HTTP_5XX` | 500, 502, 503, 504 | Máy chủ arXiv quá tải hoặc bảo trì nội bộ | Thử lại theo cấp số nhân; sau 3 lần ghi log `FAILED` vào `events.jsonl`. |
| `NOT_FOUND` | 404 | Phiên bản hoặc bài viết không tồn tại trên kho | Đánh dấu `FAILED`, không thử lại, ghi nhận vào manifest. |
| `NETWORK_ERROR` | None | Đứt kết nối TCP, rớt gói tin hoặc lỗi chunking | Thử lại ngay sau thời gian delay; riêng lỗi SSL handshake sẽ dừng ngay lập tức. |
| `CORRUPT_SOURCE` | 200 | Tệp tải về bị hỏng cấu trúc nén gzip/tar | Báo lỗi trích xuất, giữ nguyên log kiểm tra. |
| `INVALID_RESPONSE`| 200 | Máy chủ phản hồi thân bài viết rỗng (0 bytes) | Xoá file rỗng, ném ngoại lệ và ghi nhận mã lỗi. |

Mã nguồn triển khai hoàn chỉnh tại: [`src/downloader/http.py`](https://github.com/qaztyhn/intro2DS/blob/main/src/downloader/http.py) và [`src/utils/http.py`](https://github.com/qaztyhn/intro2DS/blob/main/src/utils/http.py).
