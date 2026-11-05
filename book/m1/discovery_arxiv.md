---
title: Discovery bằng arXiv API (baseline B)
short_title: arXiv API
label: m1-discovery-arxiv
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# Discovery bằng arXiv API (baseline B)

Giai đoạn Khám phá (Discovery) có nhiệm vụ chuyển đổi danh sách các mã định danh arXiv thô (dạng base ID như `2507.01659`) thành siêu dữ liệu đầy đủ của bài báo, đặc biệt là xác định toàn bộ các phiên bản khả dụng ($v1, v2, \dots, vN$) để phục vụ cho các bước tải mã nguồn tiếp theo. Trong cấu hình Baseline (B), nhóm sử dụng trực tiếp **arXiv API** thông qua thư viện `arxiv.py`.

## 1. Nguyên lý hoạt động và Truy vấn theo ID

arXiv API tại địa chỉ `https://export.arxiv.org/api/query` hỗ trợ truy vấn trực tiếp bằng tham số `id_list`. Khi gửi truy vấn với một base ID (ví dụ: `2507.01659`), API trả về một mục Atom XML chứa siêu dữ liệu của phiên bản **mới nhất** (latest version).

```python
import arxiv

client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)
search = arxiv.Search(id_list=["2507.01659"], max_results=1)
paper = next(client.results(search))
print(f"Title: {paper.title}")
print(f"Latest ID: {paper.get_short_id()}")  # Trả về hậu tố phiên bản, ví dụ: '2507.01659v3'
```

### Cách xác định danh sách các phiên bản (Version List)
Mã định danh đầy đủ của arXiv tuân theo quy ước `{base_id}v{version_number}`. Khi nhận kết quả từ `paper.get_short_id()`:
1. Hệ thống dùng biểu thức chính quy để tách hậu tố: nếu ID kết thúc bằng `vN` (với $N \ge 1$), phiên bản mới nhất là $N$.
2. Với các bài chỉ nộp một lần không có hậu tố trong ID cũ, phiên bản mặc định là $v1$.
3. Toàn bộ danh sách phiên bản cần tải được nội suy là: `versions = [1, 2, ..., N]`.

## 2. Thu thập ngày sửa đổi các phiên bản (`revised_dates`)

Theo đặc tả của đề bài, bảng dữ liệu `papers` yêu cầu lưu trữ:
- `submission_date`: Thời điểm nộp bản đầu tiên $v1$ (lấy từ thuộc tính `paper.published`).
- `revised_dates`: Danh sách các mốc thời gian cập nhật cho các phiên bản từ $v2$ đến $vN$.

Đối với một bài viết có $N$ phiên bản, việc xác định thời điểm nộp của từng phiên bản trung gian được xử lý qua hai chiến lược:

### Chiến lược 1: Truy vấn API gộp (Batched API Query)
Đối với các bài định dạng mới (new-style IDs dạng `YYMM.NNNNN`), hệ thống gộp danh sách các phiên bản trung gian `[f"{id}v{n}" for n in range(2, N)]` vào một yêu cầu API duy nhất để lấy thuộc tính `entry.updated`. Thời điểm của bản $vN$ được lấy trực tiếp từ thuộc tính `updated` của kết quả truy vấn ban đầu.

### Chiến lược 2: Phân tích trang Abstract (Abs Fallback Parsing)
arXiv API trả về lỗi HTTP 500 khi truy vấn các mã định danh dạng cũ (old-style IDs dạng `hep-th/9901001` có gắn hậu tố `vN`). Hơn nữa, đôi khi API phản hồi thiếu phiên bản trung gian. Khi đó, hệ thống tự động kích hoạt cơ chế fallback: phân tích trực tiếp khối `Submission history` từ trang web tóm tắt:

```python
ABS_URL = "https://export.arxiv.org/abs/{arxiv_id}"
# Regex trích xuất lịch sử nộp bài:
_HISTORY_BLOCK = re.compile(r'<div class="submission-history">(.*?)</div>', re.DOTALL)
_HISTORY_ENTRY = re.compile(
    r"\[v(\d+)\].*?</strong>\s*(\w{3}, \d{1,2} \w{3} \d{4} \d{2}:\d{2}:\d{2}) UTC",
    re.DOTALL
)
```

Nếu cả hai cách đều không lấy được ngày sửa đổi, hệ thống vẫn lưu trữ thông tin phiên bản, gán `revised_dates = None`, đánh dấu bài báo là `ok` và ghi log cảnh báo vào `events.jsonl` để không làm gián đoạn pipeline.

## 3. Điều tốc (Pacing) và Xử lý lỗi

Tuân thủ nghiêm ngặt điều khoản sử dụng của arXiv (arXiv Terms of Use):
- **Cơ chế Throttle:** Đối tượng `Throttle(min_interval=3.0)` ghi nhận mốc thời gian truy cập `time.monotonic()` trước và sau mỗi request. Bất kỳ request nào tới arXiv đều phải chờ ít nhất 3.0 giây kể từ request trước đó.
- **Phân loại ngoại lệ:** Mọi lỗi phát sinh từ thư viện `arxiv` hoặc `requests` đều được chuẩn hoá thành mã lỗi nội bộ:
  - `HTTP_429`: Bị giới hạn tần suất (Rate limit).
  - `HTTP_5XX`: Máy chủ arXiv gặp sự cố tạm thời.
  - `TIMEOUT`: Quá thời gian phản hồi (Connect/Read timeout).
  - `NOT_FOUND`: Bài báo không tồn tại trên hệ thống.
  - `INVALID_RESPONSE`: Lỗi phân tích XML hoặc nội dung phản hồi rỗng.

Đoạn trích triển khai hàm discovery chính trong [`src/discovery/arxiv_api.py`](https://github.com/qaztyhn/intro2DS/blob/main/src/discovery/arxiv_api.py):

```python
def discover_one(
    arxiv_id: str, client: arxiv.Client, opts: Dict[str, Any], throttle: Throttle, record: Dict[str, Any]
) -> Optional[CrawlError]:
    if _HAS_VERSION_SUFFIX.search(arxiv_id):
        raise CrawlError(f"{arxiv_id!r}: give the base id without a vN suffix", INVALID_ID)

    results = _query(client, throttle, [arxiv_id])
    if not results:
        raise CrawlError(f"arXiv returned no entry for {arxiv_id}", NOT_FOUND)
    latest = results[0]
    _, latest_version = split_versioned_id(latest.get_short_id())

    record["title"] = " ".join(latest.title.split())
    record["authors"] = [author.name for author in latest.authors]
    record["submission_date"] = _iso(latest.published)
    record["venue"] = latest.journal_ref or None
    record["latest_version"] = latest_version
    record["versions"] = list(range(1, latest_version + 1))
    record["revised_dates"], warning = _revised_dates(client, opts, throttle, arxiv_id, latest)
    record["status"] = OK
    return warning
```

## 4. Cơ chế Bỏ qua khi chạy lại (Idempotency / Resume)

Để đảm bảo hiệu quả khi chạy khối lượng lớn dữ liệu, trước khi thực hiện truy vấn, hàm `discover_paper` kiểm tra sự tồn tại của file `papers/<paper_key>/metadata.json`. Nếu file đã tồn tại với trạng thái `status == "ok"` và có đầy đủ danh sách phiên bản, tiến trình lập tức trả về trạng thái `skipped` trong vòng vài mili-giây, cho phép phục hồi quá trình cào dữ liệu (warm start) mà không tốn chi phí gọi API.
