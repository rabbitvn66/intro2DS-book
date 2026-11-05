# Hướng dẫn làm Jupyter Book — Nhóm 08 (intro2DS)

Tài liệu này dành cho cả nhóm. Đọc **mục 1–4** trước khi làm bất cứ việc gì. Mục 5–8 là tra cứu khi viết.

- Link sách (nộp cho thầy): `https://<tài-khoản>.github.io/<tên-repo-sách>/`
- Repo code: `https://github.com/qaztyhn/intro2DS`
- Một sách dùng chung cho Milestone 1 và 2. **Link không được đổi**, nội dung được sửa đến hạn nộp Poster.

---

## 1. Cấu trúc repo sách

Repo sách là repo **riêng**, tách khỏi repo code. Cấu trúc tài liệu Milestone 1 được tổ chức thành đúng **7 đề mục lớn (tương ứng với 7 tệp `.md` từ 01 đến 07)** trong thư mục `m1/`:

```
<repo-sách>/
├── myst.yml                       # Cấu hình + MỤC LỤC (toc)
├── index.md                       # Trang chủ dự án
├── bookdata.py                    # Nạp dữ liệu từ data/ (dùng chung, không sửa)
├── requirements.txt               # Thư viện để build
├── README.md                      # Tóm tắt repo
├── data/                          # Chỉ chứa file TÓM TẮT: papers.csv, versions.csv, references.csv, runs.csv, events.jsonl
├── m1/                            # Milestone 1: Đúng 7 đề mục lớn
│   ├── 01_overview.md             # 1. Tổng quan (bối cảnh, dải ID, phân công, sơ đồ mermaid)
│   ├── 02_bounded_pipeline.md     # 2. Bounded pipeline: chiến lược xử lý (Three-lane, Semaphore, Prefetch)
│   ├── 03_pipeline_stages.md      # 3. Các bước trong pipeline (Discovery, Download, Extract, References, Storage)
│   ├── 04_fault_tolerance.md      # 4. Xử lý lỗi và tính nhất quán (CrawlError, atomic write, warm resume, validation)
│   ├── 05_results.md              # 5. Kết quả thu thập (thống kê bài thành công, version, dung lượng trước/sau bỏ ảnh, refs)
│   ├── 06_evaluation.md           # 6. Đánh giá các cấu hình và chiến lược đã triển khai (thời gian, RAM, đĩa, so sánh B/D1/D2/S1)
│   └── 07_conclusion.md           # 7. Kết luận (tổng kết, khó khăn - hạn chế, hướng cải tiến)
├── m2/                            # (tạo sau khi bắt đầu Milestone 2)
└── .github/workflows/deploy.yml   # Tự động build + deploy khi push lên main
```

---

## 2. Phân công nhiệm vụ cụ thể

| Thành viên | MSSV | Vai trò chính | Nội dung & Tệp phụ trách |
|:---|:---:|:---|:---|
| **Nguyễn Lưu Hương** | `24120058` | Baseline (B), Quản trị repo sách | - Quản trị `myst.yml`, `index.md`, duyệt merge PR.<br>- Viết `01_overview.md`, `02_bounded_pipeline.md`, `04_fault_tolerance.md`, `07_conclusion.md`.<br>- Trong `03_pipeline_stages.md`: phụ trách mục 3.1 (arXiv API - B), 3.2 (Download HTTP), 3.5 (Storage & Schema).<br>- Trong `06_evaluation.md`: viết phần nhận xét cấu hình B. |
| **Lê Thị Thùy Linh** | `24120046` | OAI-PMH (D1), Trích xuất mã nguồn | - Trong `03_pipeline_stages.md`: viết mục 3.1 (OAI-PMH - D1) và mục 3.3 (Extract .tex/.bib, loại bỏ hình ảnh, ExtractionLimits).<br>- Trong `06_evaluation.md`: viết phần nhận xét cấu hình D1. |
| **Trần Bảo Châu** | `24120027` | Kaggle (D2), Thu thập Trích dẫn | - Trong `03_pipeline_stages.md`: viết mục 3.1 (Kaggle Dataset Snapshot - D2) và mục 3.4 (Semantic Scholar References, externalIds, Rate Limit).<br>- Trong `06_evaluation.md`: viết phần nhận xét cấu hình D2. |
| **Nguyễn Thị Thu Hiền** | `24120085` | Benchmark, Đo lường & Thống kê | - Cập nhật dữ liệu vào `data/` từ các lần chạy thực nghiệm.<br>- Viết toàn bộ `05_results.md` (code cell sinh đồ thị, bảng thống kê bài, dung lượng, trích dẫn).<br>- Trong `06_evaluation.md`: phụ trách phần 6.1 (đo lường RAM, CPU, đĩa, thời gian) và lập bảng so sánh 6.2. |

---

## 3. Thiết lập môi trường (mỗi người làm một lần)

Yêu cầu: **Python 3.10+**, `git`.

```bash
# 1. Clone repo sách
git clone https://github.com/<tài-khoản>/<tên-repo-sách>.git
cd <tên-repo-sách>

# 2. Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1

# 3. Cài đặt thư viện
pip install -r requirements.txt
pip install jupyter-book

# 4. Chạy thử nghiệm sách tại localhost:3000
jupyter book start --execute
```

> [!IMPORTANT]
> Cờ `--execute` là **bắt buộc** để các code cell trong `05_results.md` và `06_evaluation.md` tự động thực thi và vẽ đồ thị khi build. Không có cờ này, sách chỉ hiển thị mã nguồn mà không có hình ảnh/bảng dữ liệu.
> Nếu báo lỗi thiếu kernel: `python3 -m ipykernel install --user --name python3`.

---

## 4. Quy trình làm việc và Đóng góp nội dung

```bash
git checkout main && git pull                    # Luôn cập nhật bản mới nhất
git checkout -b m1/<tên-bạn>-<mục>              # Ví dụ: m1/linh-extract hoặc m1/chau-refs
```

1. Mở file phụ trách (ví dụ: Linh sửa phần 3.3 trong `03_pipeline_stages.md`, Châu sửa 3.4 trong `03_pipeline_stages.md`, Hiền sửa `05_results.md`).
2. Chạy `jupyter book start --execute`, mở `http://localhost:3000`. Khi lưu file, trình duyệt sẽ tự động cập nhật (live reload).
3. Khi nội dung đã chỉn chu, thực hiện commit:
   ```bash
   git add m1/03_pipeline_stages.md
   git commit -m "docs(m1): hoàn thiện mục 3.3 extract và sàng lọc tex/bib"
   git push -u origin m1/linh-extract
   ```
4. Lên GitHub → Tạo **Pull Request** → Gán **Hương** review → Hương kiểm tra và bấm **Merge**.
5. Kiểm tra tab **Actions** của repo, chờ workflow chuyển màu xanh (khoảng 2–3 phút) rồi truy cập link `github.io` để nghiệm thu.

**Quy tắc phối hợp:**
- **Không push trực tiếp vào `main`.** Tất cả thay đổi đều phải qua Pull Request.
- Chỉ `git add` đúng tệp/phần mình phụ trách.
- Không commit thư mục `_build/`, `.venv/` hoặc dữ liệu thô lớn (`.tar.gz`, tệp `.part`).

---

## 5. Quy tắc viết nội dung trong Jupyter Book

### 5.1. Cú pháp và Định dạng
- Tiêu đề cấp 1 dùng duy nhất 1 dấu `#` ở đầu trang: `# 3. Các bước trong Pipeline`.
- Các mục con đánh số rõ ràng: `## 3.1. Discovery`, `### Phương pháp 1: arXiv API`.
- Chèn công thức toán học: `$x^2$` (inline) hoặc `$$ \text{delay} = \min(\text{base\_delay} \times 2^{\text{attempt}}, 30) $$` (khối display).
- Khung ghi chú cảnh báo:
  ```markdown
  :::{note}
  Nội dung thông báo cần lưu ý.
  :::
  ```
  *(Có thể thay `note` bằng `tip`, `warning`, `important`).*

### 5.2. Sơ đồ luồng (Mermaid)
````markdown
```{mermaid}
flowchart LR
  A[Mã ID] --> B[Discovery] --> C[Download]
```
````

### 5.3. Hình vẽ và Bảng biểu sinh từ Code (Dành cho Hiền)
Mọi bảng số liệu và hình ảnh phải được **sinh ra trong quá trình build**, không chụp ảnh màn hình tĩnh dán vào:

````markdown
```{code-cell} python
:tags: [remove-input]
import sys, pathlib
for _p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
    if (_p / "bookdata.py").exists():
        sys.path.insert(0, str(_p)); break
import bookdata as bd
import matplotlib.pyplot as plt

if bd.need_data():
    bd.papers["latest_version"].value_counts().sort_index().plot.bar()
    plt.xlabel("Số version"); plt.ylabel("Số bài"); plt.show()
```
````
- Dòng `:tags: [remove-input]` có tác dụng ẩn khối mã nguồn Python, chỉ hiển thị đồ thị và kết quả bảng biểu cho người đọc.
- Code cell trong sách chỉ đọc dữ liệu từ `data/`, tuyệt đối không gọi request ra ngoài Internet hoặc crawl dữ liệu trong lúc build sách.

---

## 6. Cập nhật dữ liệu từ thực nghiệm vào sách (Hiền)

Sách **chỉ chứa dữ liệu tóm tắt**, không chứa corpus bài báo thô.

Mỗi khi nhóm có kết quả từ các đợt chạy thực nghiệm (ví dụ: `B_huong_01`, `D1_linh_01`, `D2_chau_01`):
```bash
# Tại repo code (intro2DS)
python -m src.tools.export_for_book experiments/B_huong_01 experiments/D1_linh_01 experiments/D2_chau_01 \
       --out ../<repo-sách>/data

# Tại repo sách
cd ../<repo-sách>
git checkout -b data/update-benchmark
git add data/
git commit -m "data: cập nhật số liệu thực nghiệm benchmark 4 cấu hình"
git push -u origin data/update-benchmark
# Tạo Pull Request gửi Hương merge vào main
```

---

## 7. Đối chiếu Yêu cầu Đề bài với 7 Đề mục Báo cáo

| Yêu cầu của Đề bài Milestone 1 | Vị trí thể hiện trong Sách |
|:---|:---|
| Cách crawl, thư viện, công cụ, lý do lựa chọn | `03_pipeline_stages.md` (3.1, 3.2, 3.3, 3.4) |
| Kiến trúc điều phối luồng, kiểm soát bộ nhớ | `02_bounded_pipeline.md` |
| Cơ chế retry, pacing, xử lý mã lỗi, tính nhất quán | `04_fault_tolerance.md` |
| Số bài thành công, tỷ lệ thành công | `05_results.md` (mục 5.1) |
| Kích thước trước/sau khi loại bỏ hình ảnh (chỉ giữ `.tex`/`.bib`) | `05_results.md` (mục 5.3) |
| Số lượng reference trung bình, tỷ lệ metadata | `05_results.md` (mục 5.4) |
| Thời gian chạy: từng bước, trung bình mỗi bài, toàn pipeline | `06_evaluation.md` (mục 6.1) |
| Mức tiêu thụ tài nguyên: RAM tối đa (peak RSS), dung lượng đĩa | `06_evaluation.md` (mục 6.1) |
| So sánh tổng hợp giữa 4 cấu hình B, D1, D2, S1 | `06_evaluation.md` (mục 6.2) |
| Tổng kết, khó khăn - hạn chế và hướng phát triển | `07_conclusion.md` |

---

## 8. Xử lý các sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách khắc phục |
|:---|:---|:---|
| Không thấy trang mới trên web | Chưa khai báo file vào `toc` của `myst.yml` | Mở `myst.yml`, thêm `- file: m1/<tên_file>.md` vào đúng vị trí. |
| Code cell không hiển thị đồ thị | Chạy thiếu tham số thực thi | Luôn dùng lệnh `jupyter book start --execute`. |
| Lỗi `ModuleNotFoundError: bookdata` | Cell thiếu đoạn chèn `sys.path` | Đảm bảo 5 dòng tìm `bookdata.py` nằm ở đầu cell (xem mục 5.3). |
| Trang in dòng "Chưa có dữ liệu" | Thư mục `data/` chưa có tệp CSV | Chạy script `export_for_book.py` để trích xuất dữ liệu từ `experiments/`. |
| Sửa markdown nhưng web không đổi | Trình duyệt hoặc cache của MyST chưa cập nhật | Chạy `jupyter book clean --all` rồi khởi động lại `jupyter book start --execute`. |
| GitHub Pages hiển thị lỗi 404 | Nguồn Pages trong repo chưa chọn Actions | Vào repo GitHub → **Settings** → **Pages** → Build and deployment: chọn **GitHub Actions**. |
