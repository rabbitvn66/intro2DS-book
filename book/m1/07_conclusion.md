---
title: 7. Kết luận và Hướng phát triển
short_title: 07. Kết luận
label: m1-07-conclusion
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 7. Kết luận và Hướng phát triển

## 7.1. Tổng kết Thành quả Milestone 1

Trải qua quá trình nghiên cứu lý thuyết và triển khai kỹ thuật, nhóm đã hoàn thành toàn diện các mục tiêu đặt ra cho Milestone 1:

- **Hạ tầng Pipeline hoàn chỉnh:** Xây dựng thành công quy trình thu thập dữ liệu tự động, khép kín từ khâu giải quyết mã định danh, tải mã nguồn mọi phiên bản, trích xuất chọn lọc tệp $\LaTeX$ đến thu thập trích dẫn học thuật có cấu trúc.
- **Đa dạng hoá Chiến lược Thử nghiệm:** Hiện thực hoá 4 cấu hình cào dữ liệu đại diện (Baseline **B**, OAI-PMH **D1**, Kaggle **D2**, và công cụ CLI **S1**), song song với nghiên cứu mở rộng mô hình **Bounded Pipeline** đa luồng có kiểm soát tài nguyên.
- **Kỷ luật Kỹ thuật và Tính bền vững:** Triển khai cơ chế điều tốc nghiêm ngặt theo chính sách máy chủ, áp dụng kỹ thuật ghi tệp nguyên tử (atomic write), cơ chế tự phục hồi (warm resume) và kiểm định tính toàn vẹn (corpus validation) giúp hệ thống hoạt động ổn định trên tập dữ liệu quy mô lớn mà không gặp sự cố mất mát dữ liệu.
- **Hệ thống Đo đạc và Báo cáo:** Tích hợp bộ công cụ đo tài nguyên (CPU, RAM, Disk, thời gian chạy) và xây dựng báo cáo động trên nền tảng Jupyter Book với dữ liệu được sinh trực tiếp khi biên dịch.

## 7.2. Khó khăn và Hạn chế

Trong quá trình thực nghiệm thực tế, nhóm đã nhận diện một số khó khăn và giới hạn kỹ thuật:

1. **Rào cản Giới hạn Tần suất (Rate Limits):**
   - Kho lưu trữ arXiv áp dụng quy tắc giãn cách tối thiểu 3.0 giây giữa hai yêu cầu liên tiếp. Điều này tạo ra nút thắt cổ chai lớn nhất về thời gian khi phải tải hàng chục nghìn phiên bản bài báo (thời gian chạy đơn luồng cho 5.000 bài có thể kéo dài từ 14 đến 20 giờ).
   - API của Semantic Scholar trên nhóm IP dùng chung (public pool) dễ gặp mã lỗi HTTP 429 khi mạng bận rộn, đòi hỏi phải có cơ chế retry-after và kiểm soát tốc độ chặt chẽ.
2. **Sự biến đổi Định dạng Nguồn của arXiv:**
   - Khoảng 3% các bài nộp trên arXiv chỉ có tệp PDF đã biên dịch sẵn mà không cung cấp mã nguồn $\LaTeX$ nguyên bản, đòi hỏi pipeline phải xử lý linh hoạt trạng thái `empty` (`NO_TEX_SOURCE`) thay vì xem là lỗi thu thập.
   - Các bài viết nộp trước năm 2007 sử dụng quy ước mã định danh cũ (dạng `hep-th/YYMMNNN`), API arXiv không hỗ trợ gắn hậu tố phiên bản trực tiếp và trả về lỗi HTTP 500, buộc nhóm phải xây dựng cơ chế fallback phân tích trang abstract HTML.
3. **Giới hạn Môi trường Điện toán:**
   - Khi chạy thực nghiệm trên các môi trường đám mây miễn phí như Google Colab CPU-only, nguy cơ ngắt phiên (session disconnect) hoặc đầy dung lượng ổ cứng cục bộ khi tải tệp nén lớn đòi hỏi phải dọn dẹp các tệp tạm ngay sau khi trích xuất và lưu checkpoint ra Google Drive.

## 7.3. Hướng Cải tiến và Chuẩn bị cho Milestone 2

Dựa trên kết quả thu được, nhóm đề xuất các hướng tối ưu cho các giai đoạn tiếp theo:

- **Tối ưu hoá Pipeline Crawl:** Tiếp tục chuẩn hoá biến thể Bounded Three-Lane Pipeline vào nhánh chính, thử nghiệm sử dụng tài khoản/API key chính thức của Semantic Scholar và tối ưu hoá kích thước lô truy vấn metadata.
- **Chuẩn bị Dữ liệu cho Milestone 2 (Data Parsing):**
  - Sử dụng toàn bộ kho mã nguồn `.tex` và `.bib` đã được làm sạch và sàng lọc để xây dựng cây phân tích cú pháp phân cấp (hierarchical document tree).
  - Trích xuất cấu trúc các chương mục (`\section`, `\subsection`), bảng biểu (`table`), hình vẽ đồ hoạ (`figure`), và các công thức toán học (`equation`, `math`).
  - Xử lý các lệnh nhúng tệp phức tạp trong $\LaTeX$ như `\input{...}` và `\include{...}` để tái tạo lại văn bản toàn vẹn của bài báo.
- **Chuẩn bị cho Milestone 3 (Machine Learning):**
  - Khai thác tập dữ liệu `references` đã thu thập để làm ground-truth cho bài toán liên kết và đối sánh trích dẫn (citation matching / entity resolution).

