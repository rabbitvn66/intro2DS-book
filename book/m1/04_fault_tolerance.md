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

Khi thu thập và xử lý hàng chục nghìn bài báo với dữ liệu từ các dịch vụ bên ngoài (arXiv, Semantic Scholar), các sự cố mạng ngắt quãng, dữ liệu bất thường hoặc tiến trình bị ngắt đột ngột là điều không thể tránh khỏi. Hệ thống được thiết kế theo các nguyên tắc kỹ thuật chặt chẽ nhằm bảo đảm tính toàn vẹn (integrity) và khả năng phục hồi (fault tolerance).

## 4.1. Phân loại Lỗi và Hệ thống Mã lỗi Ổn định

Mọi ngoại lệ trong pipeline đều được phân loại và chuẩn hoá thông qua lớp cơ sở `CrawlError(message, error_code, status_code)` trong `src/utils/errors.py`:

| Mã lỗi (`error_code`) | Bản chất lỗi | Chiến lược ứng phó |
|:---|:---|:---|
| `TIMEOUT`, `NETWORK_ERROR` | Lỗi mạng tạm thời, ngắt kết nối giữa chừng | Thử lại tối đa 3 lần với cơ chế lùi cấp số nhân (exponential backoff). |
| `HTTP_429` | Bị từ chối do quá giới hạn tần suất (Rate Limit) | Đọc tiêu đề `Retry-After` từ phản hồi của máy chủ, tạm dừng luồng và thử lại. |
| `HTTP_5XX` | Máy chủ đối tác gặp sự cố quá tải tạm thời | Thử lại theo cấp số nhân; sau số lần thử thất bại sẽ ghi log và bỏ qua bài đó. |
| `NOT_FOUND` | Bài báo không tồn tại (HTTP 404) | Ghi nhận lỗi vĩnh viễn, không thử lại, đánh dấu bản ghi thất bại. |
| `NO_TEX_SOURCE` | Bài báo chỉ nộp tệp PDF, không có nguồn TeX | Ghi nhận trạng thái `empty`, coi như một trường hợp hợp lệ theo yêu cầu đề bài. |
| `CORRUPT_SOURCE` | Tệp nén bị lỗi cấu trúc gzip/tar | Huỷ tệp hỏng, ghi nhận mã lỗi vào manifest và không lưu vào corpus. |
| `SCHEMA_ERROR` | Bản ghi không thỏa mãn schema kiểm định | Ghi chi tiết vi phạm vào `validation.json`, đánh dấu thất bại. |

## 4.2. Nguyên tắc Ghi tệp Nguyên tử (Atomic Write)

Để phòng ngừa sự cố mất điện hoặc tiến trình bị ngắt (`SIGINT`, `SIGKILL`) dẫn đến việc tệp JSON hoặc tệp nén bị ghi dở dang gây lỗi cú pháp (corrupted files):
- Mọi thao tác ghi tệp (`metadata.json`, `manifest.json`, `validation.json`, `source.archive`) đều được ghi ra một tệp tạm (`.part` hoặc `.tmp.<pid>`) trong cùng thư mục.
- Sau khi toàn bộ nội dung được ghi xong và xả bộ đệm (flush), lệnh `os.replace()` được sử dụng để hoán đổi nguyên tử (atomic rename). Thao tác này là an toàn tuyệt đối trên cấp độ hệ thống tệp POSIX/NTFS.

```python
# Trích đoạn cơ chế ghi JSON nguyên tử trong src/utils/common.py
def write_json_atomic(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
```

## 4.3. Khả năng Phục hồi và Chạy lại (Idempotency & Warm Resume)

Pipeline được xây dựng trên nguyên tắc **chạy lại không trùng lặp (idempotent)**:
- Mỗi bài báo và từng phiên bản đều có trạng thái hoàn tất được lưu trữ bền vững trên đĩa (`status: ok / empty / failed`).
- Khi khởi động lại một `run_id` cũ:
  - Nếu `metadata.json` của bài đã có trạng thái `ok`, pha Discovery sẽ bỏ qua ngay lập tức (`skipped`).
  - Từng phiên bản đã tải xong và có mã nguồn hợp lệ trong thư mục `source/` sẽ được tái sử dụng mà không cần tải lại qua mạng.
  - Các phần trước đó bị `failed` do mạng sẽ được tự động đưa vào danh sách thử lại.
- Dữ liệu `run.json` ghi nhận cờ `cache_mode = "warm"` và lưu trữ mốc thời gian bắt đầu đầu tiên `first_started_at`, hỗ trợ đo đạc chính xác thời gian tổng thể.

## 4.4. Kiểm định Tính nhất quán (Corpus Validation)

Giai đoạn cuối cùng của mỗi bài báo là kiểm định tự động thông qua module `src/stages/validation.py`:
- Kiểm tra tính đầy đủ của các trường bắt buộc theo đặc tả đồ án.
- So khớp số lượng và dung lượng byte thực tế của các tệp `.tex` và `.bib` trong thư mục `source/` với các giá trị được ghi trong `manifest.json`.
- Kiểm tra tính hợp lệ của mã định danh bài báo (arXiv ID syntax) và các liên kết trích dẫn.
- Báo cáo kết quả kiểm tra được lưu tại `papers/<key>/validation.json`. Nếu phát hiện bất kỳ sai lệch nào, bài viết sẽ bị đánh dấu `failed` và ghi nhận chi tiết vi phạm.

