# Hướng dẫn làm Jupyter Book — Nhóm <số nhóm>

Tài liệu này dành cho cả nhóm. Đọc **mục 1–4** trước khi làm bất cứ việc gì. Mục 5–8 là tra cứu khi viết.

- Link sách (nộp cho thầy): `https://<tài-khoản>.github.io/<tên-repo-sách>/`
- Repo code: `https://github.com/<tài-khoản>/intro2DS`
- Một sách dùng chung cho Milestone 1 và 2. **Link không được đổi**, nội dung được sửa đến hạn nộp Poster.

---

## 1. Cấu trúc repo sách

Repo sách là repo **riêng**, tách khỏi repo code.

```
<repo-sách>/
├── myst.yml              # cấu hình + MỤC LỤC (toc)
├── index.md              # trang chủ
├── bookdata.py           # nạp dữ liệu từ data/ (dùng chung, đừng sửa nếu không cần)
├── requirements.txt      # thư viện để build
├── README.md             # file này
├── data/                 # chỉ file TÓM TẮT: papers.csv, versions.csv, references.csv, runs.csv, events.jsonl
├── m1/                   # Milestone 1: mỗi trang một chủ
│   ├── index.md              tổng quan, sơ đồ, bảng 4 cấu hình
│   ├── discovery_arxiv.md    arXiv API (B)          — Hương
│   ├── discovery_oai.md      OAI-PMH (D1)           — Linh
│   ├── discovery_kaggle.md   Kaggle (D2)            — Châu
│   ├── download.md           tải nguồn + HTTP       — Hương
│   ├── extract_storage.md    trích .tex/.bib, lưu   — Hương
│   ├── references.md         Semantic Scholar       — Châu
│   ├── statistics.md         thống kê               — Hiền
│   ├── performance.md        thời gian, RAM, đĩa    — Hiền
│   └── comparison.md         so sánh B/D1/D2/S1     — Hiền
├── m2/                   # (tạo sau khi bắt đầu Milestone 2)
└── .github/workflows/deploy.yml   # tự build + deploy khi push lên main
```

**Nguyên tắc chia file:** mỗi người chỉ sửa trang của mình → gần như không bao giờ xung đột khi merge.

## 2. Phân công

| Người | Vai trò | Trang phụ trách |
|:--|:--|:--|
| **Hương** | Baseline (B), quản trị repo sách | `index.md`, `m1/index.md`, `m1/discovery_arxiv.md`, `m1/download.md`, `m1/extract_storage.md` |
| **Châu** | Kaggle (D2) và references | `m1/discovery_kaggle.md`, `m1/references.md` |
| **Linh** | OAI-PMH (D1) | `m1/discovery_oai.md` |
| **Hiền** | Metric và benchmark | `m1/statistics.md`, `m1/performance.md`, `m1/comparison.md`, và thư mục `data/` |

Chi tiết:

- **Hương** viết phần pipeline baseline: arXiv API, tải `/src/` từng version (throttle, retry, mã lỗi), trích `.tex/.bib`, cấu trúc thư mục lưu trữ, manifest, resume. Ngoài ra Hương tạo repo sách, bật GitHub Pages, **duyệt và merge mọi pull request** vào `main`, kiểm tra trang đã lên.
- **Châu** viết D2 (đọc snapshot Kaggle, lọc theo ID, bổ sung version còn thiếu) và phần references (Semantic Scholar: endpoint, field, lọc ID arXiv, rate limit, xử lý 429, lưu reference thiếu ID).
- **Linh** viết D1 (OAI-PMH: endpoint, verb, resumption token, cách bổ sung version, so với arXiv API).
- **Hiền** chạy `export_for_book.py` để cập nhật `data/` (mục 6), viết thống kê, hiệu năng (thời gian, RAM, đĩa), và bảng so sánh các cấu hình trong `comparison.md`.
- **`m1/comparison.md`**: Hiền làm bảng và hình; mỗi người điền đoạn nhận xét về cấu hình của mình (Hương: B, Linh: D1, Châu: D2).
- **S1 (arxiv-downloader) chưa có người.** Cả nhóm chốt ai nhận; người nhận thêm một mục S1 vào `m1/download.md` và dòng nhận xét trong `comparison.md`.

Mỗi trang có sẵn dàn ý gợi ý trong dấu *(…)*. Viết xong thì **xoá khung "Phụ trách"** ở đầu trang.

Việc của **Milestone 2** sẽ chia lại khi bắt đầu (cùng cấu trúc: mỗi người một trang trong `m2/`).

---

## 3. Thiết lập một lần (mỗi người)

Cần: Python 3.10+, git.

```bash
# 1. clone repo sách
git clone https://github.com/<tài-khoản>/<tên-repo-sách>.git
cd <tên-repo-sách>

# 2. tạo môi trường ảo
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1

# 3. cài thư viện
pip install -r requirements.txt
pip install jupyter-book

# 4. chạy thử: sách mở ở http://localhost:3000
jupyter book start --execute
```

`--execute` là **bắt buộc** để các code cell chạy và sinh hình. Không có cờ này, sách chỉ hiện code mà không có kết quả.

Nếu `--execute` báo thiếu kernel: `python -m ipykernel install --user --name python3`.

## 4. Quy trình làm việc mỗi lần viết

```bash
git checkout main && git pull                 # luôn lấy bản mới nhất
git checkout -b m1/<tên-bạn>-<trang>          # ví dụ: m1/linh-oai
```

1. Mở file trang của bạn, viết bằng editor (VS Code đọc Markdown tốt).
2. Chạy `jupyter book start --execute`, mở `localhost:3000`. **Lưu file là trang tự cập nhật.**
3. Hài lòng thì commit:
   ```bash
   git add m1/discovery_oai.md
   git commit -m "M1: viết phần OAI-PMH (D1)"
   git push -u origin m1/linh-oai
   ```
4. Lên GitHub → **Compare & pull request** → gán **Hương** review → Hương bấm **Merge**.
5. Vào tab **Actions** của repo, chờ workflow xanh (khoảng 2–4 phút), rồi mở link github.io kiểm tra.

Quy tắc:
- **Không push thẳng vào `main`.** Mọi thay đổi qua pull request.
- Chỉ `git add` file của bạn. Không `git add .` khi chưa xem `git status`.
- Muốn sửa chung `myst.yml` (mục lục) hoặc `index.md`: báo Hương.
- Không commit `_build/`, `.venv/`, dữ liệu thô (`.tex`, `.bib`, tar.gz).

---

## 5. Cách viết từng loại nội dung

### 5.1 Tạo trang mới (ví dụ Milestone 2)
1. Tạo file, ví dụ `m2/parsing_tree.md`, với phần đầu (frontmatter):
   ```markdown
   ---
   title: Parsing cây phân cấp
   short_title: Parsing
   label: m2-tree
   jupytext:
     text_representation:
       extension: .md
       format_name: myst
   kernelspec:
     name: python3
     display_name: Python 3
   ---
   ```
   Nếu trang **không có code cell** thì bỏ khối `jupytext`/`kernelspec` cũng được.
2. Thêm vào mục lục `myst.yml` (**phải làm**, nếu không trang không hiện):
   ```yaml
   toc:
     - file: index.md
     - title: Milestone 2 — Parsing
       children:
         - file: m2/parsing_tree.md
   ```
3. Chạy `jupyter book start --execute` kiểm tra.

### 5.2 Tiêu đề, danh sách, bảng
```markdown
# Tiêu đề trang (mỗi trang đúng một dòng "# ")
## Mục
### Mục con

- gạch đầu dòng
1. đánh số

| Cột A | Cột B |
|:--|--:|
| 1 | 2 |
```
Công thức: `$x^2$` (trong dòng), `$$ \text{MRR} = \frac{1}{|Q|}\sum \frac{1}{rank_i} $$` (khối).

### 5.3 Khung ghi chú
```markdown
:::{note}
Nội dung ghi chú.
:::
```
Có thể thay `note` bằng `tip`, `warning`, `important`.

### 5.4 Sơ đồ (Mermaid)
````markdown
```{mermaid}
flowchart LR
  A[ID] --> B[Discovery] --> C[Download]
```
````

### 5.5 Tham chiếu chéo giữa các trang
Mỗi trang có `label:` trong frontmatter (ví dụ `m1-download`). Từ trang khác viết:
```markdown
Xem [](#m1-download) để biết cơ chế retry.
```
Link tự lấy tiêu đề trang.

### 5.6 Hình và bảng sinh từ code (quan trọng)
Đề yêu cầu hình/bảng **phải sinh khi build**, không dán ảnh chụp.

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

- `:tags: [remove-input]` ẩn code, chỉ hiện kết quả. Muốn cho người đọc thấy code thì bỏ dòng `:tags:`.
- Dữ liệu có sẵn trong `bookdata.py`: `papers`, `versions`, `refs`, `runs`, `events`; hàm `paper_success(config)`.
- Cột trong `versions`: `download_status`, `extract_status` (`ok`/`empty`/`failed`), `unpacked_total_bytes`, `kept_source_bytes`, `archive_bytes`, `error_code`.

**Cell chỉ được:** đọc từ `data/`, tính toán, vẽ. **Không được:** gọi mạng, chạy crawl, đọc file ngoài `data/`. Mỗi trang nên build dưới ~30 giây.

### 5.7 Trích mã nguồn
Chỉ dán đoạn ngắn (≤ 25 dòng) có ý nghĩa, kèm link tới file trên repo code:
````markdown
```python
def throttle(self): ...   # đoạn ngắn
```
Mã đầy đủ: [`src/utils/http.py`](https://github.com/<tài-khoản>/intro2DS/blob/main/src/utils/http.py)
````

### 5.8 Ảnh có sẵn (hiếm khi cần)
Đặt vào `figures/` rồi `![mô tả](../figures/x.png)`. Ưu tiên hình sinh bằng code.

---

## 6. Cập nhật dữ liệu cho sách (Hiền)

Sách **không** chứa corpus; chỉ chứa số liệu tóm tắt.

**Quy ước đặt tên thư mục run** (bắt buộc, vì cấu hình được suy ra từ tên): `<cấu-hình>_<tên>_<số>`, ví dụ `B_huong_01`, `D1_linh_01`, `D2_chau_01`.

Mỗi lần có run mới:
```bash
# trong repo code (intro2DS)
cp src/tools/export_for_book.py ...        # lần đầu: script nằm ở src/tools/
python -m src.tools.export_for_book experiments/B_huong_01 experiments/D1_linh_01 experiments/D2_chau_01 \
       --out ../<repo-sách>/data

# trong repo sách
cd ../<repo-sách>
git checkout -b data/update-<ngày>
git add data/
git commit -m "Cập nhật dữ liệu: thêm run ..."
git push -u origin data/update-<ngày>      # rồi tạo PR như mục 4
```
Mỗi lần export phải liệt kê **tất cả** run muốn hiển thị (script ghi đè `data/`). `events.jsonl` lớn hơn ~50 MB thì báo Hương để đổi sang Parquet.

---

## 7. Đối chiếu yêu cầu của đề (M1) với trang

| Yêu cầu của đề | Trang |
|:--|:--|
| Cách crawl, công cụ, lý do chọn | `discovery_*`, `download`, `extract_storage`, `references` |
| Số bài thành công, tỉ lệ | `statistics` |
| Kích thước trước/sau khi bỏ hình | `statistics` |
| Số reference trung bình, tỉ lệ lấy được metadata | `statistics` |
| Thời gian từng bước, trung bình mỗi bài, toàn pipeline | `performance` |
| RAM tối đa, dung lượng đầu ra | `performance` |
| So sánh các phương án | `comparison` |
| Hình/bảng sinh khi build | mọi cell `code-cell` |

---

## 8. Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|:--|:--|
| Trang không hiện trong mục lục | Quên thêm vào `toc` của `myst.yml` |
| Code cell không có kết quả | Chạy thiếu `--execute` |
| `ModuleNotFoundError: bookdata` | Thiếu đoạn `sys.path` ở đầu cell (mục 5.6) |
| In "Chưa có dữ liệu" | `data/` chưa có CSV; nhờ Hiền export |
| Sửa nhưng web không đổi | `jupyter book clean --all` rồi `jupyter book start --execute` |
| github.io báo 404 | Settings → Pages → Source phải là **GitHub Actions**; xem tab Actions có đỏ không |
| Trang lên nhưng mất giao diện | Workflow đặt `BASE_URL` sai; báo Hương |
| Workflow đỏ | Mở log trong tab Actions, copy dòng lỗi cuối gửi nhóm |
| Xung đột ở `myst.yml` khi merge | Giữ cả hai dòng `- file:` của hai người, xoá dấu `<<<<` `====` `>>>>` |

## 9. Chuẩn bị cho Milestone 2

1. Hương tạo thư mục `m2/` với `index.md` (label `m2-parsing`) và các trang con.
2. Thêm khối "Milestone 2 — Parsing" vào `toc` (đã có sẵn dòng comment trong `myst.yml`).
3. Dữ liệu M2 (số element/entry trước–sau dedup, tỉ lệ parse) thêm file CSV mới vào `data/` và một hàm đọc trong `bookdata.py`.
4. **Không đổi tên repo sách, không đổi tên nhánh `main`** — làm vậy sẽ đổi link đã nộp.
