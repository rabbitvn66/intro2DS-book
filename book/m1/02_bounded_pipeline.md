---
title: 2. Bounded Pipeline và Chiến lược Xử lý
short_title: 02. Bounded Pipeline
label: m1-02-bounded-pipeline
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 2. Bounded Pipeline: Chiến lược Xử lý

Một trong những thách thức lớn nhất khi thu thập dữ liệu học thuật quy mô lớn (20.000 bài báo với hàng chục nghìn phiên bản) là **sự mất cân bằng giữa tốc độ các khâu** và **nguy cơ cạn kiệt tài nguyên hệ thống (OOM, nghẽn I/O)**. Khâu tải mã nguồn và phân tích trích dẫn bị giới hạn ngặt nghèo bởi chính sách Rate Limit từ máy chủ bên ngoài (arXiv, Semantic Scholar), trong khi các khâu giải nén lại tiêu tốn nhiều CPU và bộ nhớ cục bộ.

Để giải quyết vấn đề này, nhóm triển khai kiến trúc **Bounded Pipeline** đa luồng với cơ chế điều phối tài nguyên có chặn trên (bounded concurrency).

## 2.1. Kiến trúc Three-Lane Bounded Concurrency

Thay vì để các tiến trình con tự do tạo luồng gây quá tải hoặc làm nghẽn hàng đợi mạng, pipeline phân tách các tác vụ thành ba làn độc lập (lanes) và giới hạn số lượng bài báo đang xử lý dở dang (in-flight papers) thông qua `threading.BoundedSemaphore`:

```{mermaid}
flowchart TD
  subgraph MainThread ["Luồng chính (Main Thread): Làn arXiv duy nhất"]
    A[Mã ID đầu vào] --> B[Batch Discovery<br/>arXiv API]
    B --> C[Tuần tự tải source các version<br/>HTTP export.arxiv.org/src/]
  end

  subgraph WorkerLanes ["Các làn công nhân độc lập (Worker Threads)"]
    C -->|Đẩy việc| Q1[Extract Queue<br/>maxsize = 2]
    B -->|Đẩy việc| Q2[References Queue<br/>maxsize = 4]
    Q1 --> W1[Extract Worker<br/>Chỉ lọc .tex/.bib]
    Q2 --> W2[References Worker<br/>Semantic Scholar API]
  end

  subgraph Barrier ["Điểm đồng bộ & Chốt chặn"]
    W1 --> J[Join Barrier<br/>Chờ cả 2 worker hoàn thành]
    W2 --> J
    J --> S[Storage & Schema Validation<br/>Atomic write & Release Slot]
  end
```

### Nguyên tắc vận hành cốt lõi:
1. **Làn arXiv duy nhất (Single arXiv Lane):** Chỉ duy nhất luồng chính được phép gửi yêu cầu tới API arXiv và tải source từ `export.arxiv.org`. Không có luồng nào khác được gọi đồng thời, đảm bảo khoảng cách điều tốc (pacing $\ge 3.0$s) luôn được tuân thủ tuyệt đối mà không bị xung đột tài nguyên mạng.
2. **Hàng đợi công việc giới hạn (Bounded Queues):**
   - `extract_queue` (kích thước tối đa 2): Chứa công việc giải nén cho từng bài báo đã tải xong.
   - `references_queue` (kích thước tối đa 4): Chứa công việc thu thập trích dẫn từ Semantic Scholar cho các bài đã discovery xong.
   - Các công việc trong hàng đợi chỉ là các đối tượng mô tả gọn nhẹ (`PaperJob` descriptor mang ID và bộ đếm trạng thái), hoàn toàn **không lưu trữ nội dung nhị phân (source bytes)** trong RAM. Toàn bộ tệp nén lớn được ghi trực tiếp xuống đĩa.
3. **Semaphore chặn trên toàn cục (`pipeline_max_inflight`):**
   - Thiết lập giới hạn tối đa số lượng bài báo chưa hoàn tất trong toàn hệ thống (mặc định = 4).
   - Ngăn chặn triệt để tình trạng luồng chính tải ồ ạt hàng trăm bài trong khi luồng trích xuất hay tham chiếu chưa kịp hoàn thành, loại trừ rủi ro tràn RAM hoặc tràn ổ đĩa tạm.

## 2.2. Chiến lược Gối đầu Siêu dữ liệu (Interleaved Metadata Prefetch)

Đối với các cấu hình tối ưu, luồng chính không đợi xử lý hết toàn bộ danh sách bài trong nhóm mới thực hiện truy vấn tiếp theo, mà triển khai cơ chế **Prefetch gối đầu**:
- Khi số lượng ID còn lại trong lô hiện tại chạm ngưỡng cảnh báo (`pipeline_prefetch_remaining`, ví dụ $\le 5$ bài), luồng chính sẽ thực hiện một truy vấn API tiếp theo để nạp sẵn siêu dữ liệu của lô kế tiếp.
- Cơ chế này giúp loại bỏ độ trễ rỗi (idle latency) của mạng mà vẫn duy trì tính tuần tự và tôn trọng khoảng trễ rate limit 3 giây của arXiv.

## 2.3. Thông số Cấu hình Tiêu biểu

Cấu hình mẫu cho pipeline có chặn (`configs/a_pipeline_pilot.yaml`):

| Tham số cấu hình | Giá trị mặc định | Ý nghĩa kỹ thuật |
|:---|:---:|:---|
| `discovery_batch_size` | 20 | Số lượng ID gộp trong một đợt truy vấn siêu dữ liệu |
| `pipeline_max_inflight` | 4 | Số bài tối đa được phép tồn tại đồng thời trong pipeline |
| `pipeline_extract_queue` | 2 | Số lượng công việc chờ tối đa trong hàng đợi giải nén |
| `pipeline_references_queue` | 4 | Số lượng công việc chờ tối đa trong hàng đợi trích dẫn |
| `pipeline_prefetch_remaining` | 5 | Ngưỡng số ID còn lại trong batch để kích hoạt prefetch batch tiếp theo |

Kiến trúc này tạo ra sự cân bằng lý tưởng: khai thác tối đa năng lực xử lý I/O đĩa và mạng của máy tính mà không vi phạm quy định rate limit, đồng thời giữ bộ nhớ RAM luôn ổn định dưới ngưỡng 200 MB trong suốt quá trình chạy liên tục.

