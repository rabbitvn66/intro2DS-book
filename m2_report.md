---
title: Milestone 2 — Hierarchical Parsing and Standardization
short_title: Milestone 2 — Parsing
label: m2-report
---

# Tổng quan

Milestone 2 biến các nguồn LaTeX đã thu thập ở Milestone 1 thành một kho phần tử có cấu trúc: mỗi version của mỗi publication được phân tích thành cây phân cấp, chuẩn hóa, khử trùng lặp xuyên version, và các tài liệu tham khảo được hợp nhất thành các entry BibTeX. Đầu ra gồm ba bảng công bố (`elements`, `hierarchy`, `bibtex`) cho **5000 publication** được giao (`ids_24120058.txt`).

Toàn bộ số liệu, bảng và hình trong trang này được **sinh lúc biên dịch sách** từ các tệp trong thư mục `m2_report_data/` (xuất từ `state.json` và các bảng Parquet cuối của lần chạy).

```{code-cell} python
:tags: [remove-input]
import json, pathlib
import pandas as pd
import plotly.express as px

D = pathlib.Path("m2_report_data")
df = pd.read_csv(D / "state_metrics.csv", dtype={"arxiv_id": str})
sizes = json.loads((D / "table_sizes.json").read_text())
val = json.loads((D / "validation_summary.json").read_text())
runs = json.loads((D / "run_metrics.json").read_text())

N = len(df)
has_data = df["status"].isin(["success", "partial"])
```

# 1. Thu thập nhiều tệp (Multi-file Gathering)

Một nguồn LaTeX thường trải trên nhiều tệp `.tex`. Bộ gom (`gathering.py`) tái hiện đúng những gì LaTeX sẽ biên dịch, không chạy trình biên dịch:

1. **Tìm gốc (root).** Gốc là tệp chứa **đúng một** khai báo `\documentclass` đang hoạt động. Tên tệp không được viết cứng (không giả định `main.tex`). Khai báo nằm trong chú thích, môi trường nguyên văn (`verbatim`), thân của định nghĩa macro, hoặc nhánh `\iffalse` không phải là gốc. Phần văn bản sau `\end{document}` bị bỏ qua, nên một tài liệu mẫu nối đuôi không tạo gốc thứ hai.
2. **Theo các lệnh bao gồm.** `\input`, `\include`, `\import`/`\subimport` được bung đệ quy; đường dẫn tính theo thư mục của tệp chứa lệnh, thư mục gốc, rồi thư mục nguồn; kiểm tra vòng lặp bằng ngăn xếp đang hoạt động. Lệnh nằm trong chú thích chỉ là văn bản thường. `\includeonly` được hỗ trợ.
3. **Nhiều gốc.** Khi có nhiều tệp khai báo `\documentclass`, bộ gom dựng **đồ thị phụ thuộc** giữa các ứng viên: ứng viên được tệp khác bao gồm không phải gốc cấp cao nhất. Nếu còn đúng một gốc cấp cao nhất thì chọn nó (ghi cảnh báo `ROOT_SELECTED_BY_DEPENDENCY_GRAPH`). Nếu còn nhiều hơn một, version được đánh dấu `failed` với mã `AMBIGUOUS_ROOT`, **không đoán** theo tên tệp.
4. **Tệp không thuộc đường biên dịch bị bỏ qua.** Chỉ các tệp `.tex` có thể đến được từ gốc mới vào văn bản đã gom. Chỉ các `.bib` được `\bibliography{...}` hoặc `\addbibresource{...}` gọi tới trên đường biên dịch mới được nạp.
5. **Biên giới an toàn.** Đọc UTF-8/BOM; UTF-16 và Latin-1 chỉ là phương án dự phòng kèm cảnh báo; tệp chứa byte NUL bị từ chối. Có giới hạn kích thước tệp, tổng byte đọc và độ sâu lồng nhau; vượt giới hạn thì báo lỗi, không cắt âm thầm.
6. **Trạng thái version.** `ok` (gom đầy đủ), `partial` (gom được nhưng có cảnh báo: điều kiện chưa xác định, phụ thuộc động, mã hóa không chắc chắn...), `failed` (không xác định được gốc, hoặc không đọc được nguồn), `no_tex` (M1 ghi nhận version không có TeX, được giữ như bản ghi rỗng theo đặc tả).

## Ba cải tiến phát sinh khi xử lý dữ liệu thật

Khi chạy trên 5000 publication, ba nhóm lỗi gom nguồn có thể sửa bằng quy tắc khách quan (không dùng heuristic theo tên tệp) đã được xử lý:

| Cải tiến | Vấn đề quan sát được | Cách xử lý |
|---|---|---|
| Macro điều kiện có đối số của `etoolbox`/`biblatex` | `\iftoggle{a}{b}{c}`, `\ifbool`, `\iffieldundef`... không có `\fi`, nhưng bị coi là điều kiện mở chưa đóng (`UNTERMINATED_CONDITIONAL`): mọi lệnh phía sau, kể cả `\bibliography` và `\input`, không được xử lý | Bổ sung các macro này kèm số đối số đúng vào bảng macro điều kiện |
| `\subfile` (gói `subfiles`) | Đồ thị phụ thuộc bỏ sót `\subfile`, và nội dung tệp con không được đưa vào | Theo dõi `\subfile` trong đồ thị và bung phần thân giữa `\begin{document}` và `\end{document}` của tệp con |
| Gốc nằm trong điều kiện chưa xác định, và ứng viên không có `\begin{document}` | `\documentclass` trong `\ifx...\else...\fi` bị đếm là 0 gốc (`NO_ROOT`); tệp chỉ có `\documentclass` vẫn là ứng viên gốc | Khi không còn gốc nào khác, đếm gốc trong các nhánh điều kiện; khi có ứng viên chứa `\begin{document}`, loại các ứng viên không có |

Mỗi sửa đổi ghi một cảnh báo kiểm toán (`ROOT_IN_UNRESOLVED_CONDITIONAL`, `ROOT_CANDIDATES_WITHOUT_BEGIN_DOCUMENT`) để mọi lựa chọn tự động đều truy vết được.

```{code-cell} python
:tags: [remove-input]
f = D / "rerun_macro_effect.csv"
if f.exists():
    eff = pd.read_csv(f, dtype={"arxiv_id": str})
    if len(eff):
        eff["elements_gain"] = eff["elements_after"] - eff["elements_before"]
        eff["bibtex_gain"] = eff["bibtex_after"] - eff["bibtex_before"]
        print(f"Chạy lại các publication dùng macro điều kiện của etoolbox/biblatex: {len(eff)} publication thay đổi kết quả")
        print(f"  tổng số dòng elements tăng thêm: {int(eff['elements_gain'].sum()):,}")
        print(f"  tổng số dòng bibtex tăng thêm:   {int(eff['bibtex_gain'].sum()):,}")
        display(eff.sort_values("bibtex_gain", ascending=False).head(10))
```

# 2. Xây dựng phân cấp (Hierarchy Construction)

Văn bản đã gom được đưa vào bộ phân tích phân cấp (`hierarchy.py`), một bộ phân tích **bảo thủ**: cấu trúc không hỗ trợ được giữ nguyên trong văn bản và cấu trúc không cân bằng sinh cảnh báo kèm trạng thái `partial`, thay vì đoán.

- **Gốc cây** là phần tử `document` (mỗi version có một gốc riêng).
- **Cấp trên** là các lệnh phân mục (`\part`, `\chapter`, `\section`, ..., `\paragraph`); cấp được xác định tự động theo cấu trúc thực của từng bài, không giả định thứ tự lồng nhau cố định. `abstract`, phụ lục và lời cảm ơn được giữ (kể cả dạng không đánh số `\section*`).
- **Lá** là câu (`sentence`), công thức khối (`equation`) và hình/bảng (`figure`). Danh sách `itemize`/`enumerate` là thành phần cấp cao, mỗi `\item` là một phần tử cấp kế tiếp.
- **Không cắt câu** bên trong toán học, lệnh, từ viết tắt (như `i.e.`, `et al.`, `Fig. 1`), địa chỉ URL hay số thập phân. Bộ tách câu đã được kiểm tra trên các ca này (ví dụ `We use i.e. this and et al. also. See Fig. 1 for 3.14 and https://a.org/x.y. Next one.` được tách thành đúng ba câu).
- **Mục tài liệu tham khảo không đưa vào cây**; chúng đi vào luồng BibTeX (mục 4).

```{code-cell} python
:tags: [remove-input]
kinds = pd.read_csv(D / "kind_counts.csv")
fig = px.bar(kinds.sort_values("count"), x="count", y="kind", orientation="h", log_x=True,
             title="Số phần tử theo loại (thang log)", labels={"count": "số phần tử (sau khử trùng lặp)", "kind": ""})
fig.update_layout(height=460)
fig
```

# 3. Chuẩn hóa

Chuẩn hóa tác động lên **nội dung** từng phần tử đã phân tích, theo nguyên tắc **không phá hủy**: macro và môi trường không hỗ trợ được giữ nguyên chứ không bị xóa.

- **Dọn dẹp LaTeX:** bỏ chú thích (giữ `\%`), bỏ các lệnh bố cục không mang nghĩa như `\centering` và `\midrule`/`\toprule`/`\bottomrule`, bỏ lệnh định dạng chữ nhưng giữ nội dung (`\textbf{x}` thành `x`); chuẩn hóa khoảng trắng. Các lệnh không thuộc danh sách (ví dụ `\label`, `\vspace`) được **giữ nguyên** theo nguyên tắc không phá hủy. Nội dung nguyên văn (`verbatim`, `lstlisting`, `minted`) được bảo vệ khỏi mọi bước. Mức tồn dư thực tế của tùy chọn đặt vị trí `[htpb]` và các lệnh trên trong dữ liệu cuối được đo ở mục 5.5.
- **Chuẩn hóa toán học:** toán nội dòng (`\(...\)`, `\begin{math}`) đưa về dạng thống nhất `$...$`; toán khối viết bằng `\[...\]` hoặc `$$...$$` đưa về `\begin{equation*}...\end{equation*}`; các môi trường có tên như `align` được giữ nguyên.
- **Chuẩn hóa trích dẫn:** các lệnh `\cite` được viết lại theo khóa đã chọn sau khi hợp nhất entry (mục 4).

# 4. Trích xuất và khử trùng lặp

## 4.1. Tài liệu tham khảo → BibTeX

Entry BibTeX đến từ hai nguồn: các tệp `.bib` được gọi trên đường biên dịch và các mục `\bibitem` trong môi trường `thebibliography`. Sau đó hợp nhất ở mức publication, **xuyên mọi version**:

- Các entry khác khóa nhưng cùng nội dung tham khảo được gộp về **một khóa duy nhất**; mọi `\cite{...}` trỏ tới khóa bị bỏ được **đổi tên** thành khóa được chọn.
- Các trường được **hợp nhất (union)**: trường có ở bất kỳ bản sao nào đều được giữ, không chọn một bản và bỏ phần còn lại.

## 4.2. Khử trùng lặp phần tử

Các phần tử có `(kind, nội dung chuẩn hóa)` **khớp chính xác** trong cùng một publication dùng chung một `element_id`, bất kể version, vị trí hay phần tử cha. Việc khớp **sau chuẩn hóa** nên khác biệt vô nghĩa về định dạng hay khoảng trắng không làm hai nội dung giống nhau bị coi là khác nhau. Không khớp mờ, không khớp giữa các publication. Bảng `hierarchy` chỉ chứa các cạnh nút-cha của từng version, nên một phần tử của version cũ có thể là nút trong cạnh của version mới, gắn với cha chỉ tồn tại ở version mới.

Với phần tử cấu trúc (tiêu đề, danh sách) lặp lại nhiều lần với cùng nội dung trong một version, mỗi lần xuất hiện dùng một đại diện khác nhau trong một nhóm đại diện, để không gộp nhầm các nhánh con khác nhau; các nhóm đại diện này được ghi nhận bằng cảnh báo. Trước khi tái dùng một `element_id`, hệ thống kiểm tra việc đó không tạo vòng lặp trong đồ thị của version hiện tại.

# 5. Kết quả

## 5.1. Tỉ lệ thành công

Tỉ lệ được báo cáo kèm tử số, mẫu số và **định nghĩa**:

- **`success`**: mọi version parse được hoặc không có TeX (`no_tex`).
- **`partial`** (mức publication): còn ít nhất một version parse được nhưng có ít nhất một version lỗi; dữ liệu của các version tốt vẫn được giữ.
- **`failed`**: không version nào parse được; không có dữ liệu.

```{code-cell} python
:tags: [remove-input]
vc = df["status"].value_counts()
summary = pd.DataFrame({
    "số publication": vc,
    "tỉ lệ (trên %d)" % N: (vc / N).map("{:.2%}".format),
}).rename_axis("trạng thái")
display(summary)
ok_rate = has_data.mean()
print(f"Có dữ liệu trong bảng (success + partial): {has_data.sum()}/{N} = {ok_rate:.2%}")
print(f"Chỉ success (mọi version đều không lỗi):  {(df['status'] == 'success').sum()}/{N} = {(df['status'] == 'success').mean():.2%}")
```

## 5.2. Nguyên nhân thất bại

Mã lỗi được ghi theo dạng `giai đoạn/lý do` ở mức version.

```{code-cell} python
:tags: [remove-input]
bad = df[df["bad_codes"].fillna("") != ""].assign(code=lambda x: x["bad_codes"].str.split(";")).explode("code")
tab = (bad.groupby(["code", "status"]).size().unstack(fill_value=0)
          .assign(tổng=lambda x: x.sum(axis=1)).sort_values("tổng", ascending=False))
display(tab)
fig = px.bar(tab.reset_index().melt(id_vars="code", value_vars=[c for c in tab.columns if c != "tổng"],
                                    var_name="trạng thái publication", value_name="số publication"),
             x="code", y="số publication", color="trạng thái publication", title="Mã lỗi mức version, theo trạng thái publication")
fig.update_layout(xaxis_title="")
fig
```

- `AMBIGUOUS_ROOT`: nhiều tệp cùng khai báo `\documentclass` mà đồ thị phụ thuộc không phân xử được (ví dụ một bài báo cùng tài liệu hướng dẫn độc lập). Hệ thống **cố ý không đoán** theo tên tệp hay độ dài; chỉ chọn qua lựa chọn gốc đã được rà soát.
- `SOURCE_NOT_DOWNLOADED`: M1 không tải được nguồn của version đó; không sửa được ở M2.
- Các mã còn lại (`NO_ROOT`, `NUL_BYTES`, `ROOT_SCAN_INCOMPLETE`, `MULTIPLE_ROOT_DECLARATIONS`) chiếm số lượng nhỏ.

## 5.3. Độ phủ version

```{code-cell} python
:tags: [remove-input]
m = df.dropna(subset=["n_versions"])
tv = int(m["n_versions"].sum())
cov = pd.DataFrame({
    "số version": [int(m["versions_parsed"].sum()), int(m["versions_no_tex"].sum()), int(m["versions_bad"].sum())],
}, index=["parse được (ok/partial)", "không có TeX (no_tex)", "lỗi hoặc bỏ qua (failed/skipped)"])
cov["tỉ lệ (trên %d version)" % tv] = (cov["số version"] / tv).map("{:.2%}".format)
display(cov)
with_tex = int(m["versions_parsed"].sum() + m["versions_bad"].sum())
print(f"Tỉ lệ parse được trong các version CÓ TeX: {int(m['versions_parsed'].sum())}/{with_tex} = {m['versions_parsed'].sum() / with_tex:.2%}")

per = m.assign(coverage=lambda x: x["versions_parsed"] / x["n_versions"])
fig = px.histogram(per, x="n_versions", color="status", barmode="stack",
                   title="Số version của mỗi publication, theo trạng thái", labels={"n_versions": "số version"})
fig
```

## 5.4. Số phần tử và entry trước và sau khử trùng lặp

"Trước" là số lần phần tử xuất hiện qua các version (mỗi version tính riêng); "sau" là số dòng thực tế của bảng sau khi dùng chung `element_id`. Với BibTeX, "trước" là số entry thô đếm được ở mọi version và "sau" là số entry hợp nhất.

```{code-cell} python
:tags: [remove-input]
d = df[has_data].dropna(subset=["elements_before", "elements_after", "bib_before", "bib_after"])
tot = pd.DataFrame({
    "trước": [d["elements_before"].sum(), d["bib_before"].sum()],
    "sau":   [d["elements_after"].sum(),  d["bib_after"].sum()],
}, index=["phần tử (elements)", "entry (bibtex)"]).astype(int)
tot["giảm"] = (1 - tot["sau"] / tot["trước"]).map("{:.1%}".format)
display(tot)

dd = d[d["elements_before"] > 0].assign(ty_le=lambda x: 1 - x["elements_after"] / x["elements_before"])
fig = px.histogram(dd, x="ty_le", nbins=40, title="Tỉ lệ giảm số phần tử nhờ khử trùng lặp (mỗi publication)",
                   labels={"ty_le": "tỉ lệ giảm"})
fig
```

## 5.5. Bảng đầu ra và kiểm tra tính hợp lệ

```{code-cell} python
:tags: [remove-input]
t = pd.DataFrame(sizes).T.rename(columns={"rows": "số dòng", "mb": "dung lượng (MB)"})
display(t)
cc = val["citation_coverage"]
print(f"Kiểm tra bảng cuối: {val['error_total']} lỗi, {val['warning_total']:,} cảnh báo, trên {val['publications']} publication.")
print(f"Độ phủ trích dẫn: {cc['numerator']:,}/{cc['denominator']:,} = {cc['value']:.2%} cặp (arxiv_id, khóa) được trích có dòng trong bảng bibtex.")
print("Cảnh báo theo loại:", val["issues"])
```

```{code-cell} python
:tags: [remove-input]
f = D / "format_residue.json"
if f.exists():
    r = json.loads(f.read_text())
    n = max(r["figure_elements"], 1)
    print(f"Phần tử hình/bảng: {r['figure_elements']:,}")
    print(f"  còn tùy chọn đặt vị trí [htpb]-dạng: {r['with_placement_option']:,} ({r['with_placement_option'] / n:.1%})")
    print(f"  còn \\centering:                     {r['with_centering']:,} ({r['with_centering'] / n:.1%})")
    print(f"  còn \\midrule/\\toprule/\\bottomrule: {r['with_rules']:,} ({r['with_rules'] / n:.1%})")
```

Các cảnh báo `multi_parent` và `duplicate_edge` phản ánh việc một phần tử được dùng chung ở nhiều vị trí (khử trùng lặp theo nội dung), và là hệ quả của thiết kế chứ không phải lỗi dữ liệu. `cite_key_missing` cho biết lệnh `\cite` trỏ tới khóa không có entry (ví dụ khi nguồn tham khảo là tệp `.bbl` hay `.bib` không có trong dữ liệu M1).

## 5.6. Publication có phần tử nhưng không có BibTeX

```{code-cell} python
:tags: [remove-input]
nb = df[has_data & (df["rows_elements"].fillna(0) > 0) & (df["rows_bibtex"].fillna(0) == 0)]
print(f"{len(nb)} publication có phần tử nhưng không có entry BibTeX "
      f"({len(nb) / max(int((has_data & (df['rows_elements'].fillna(0) > 0)).sum()), 1):.1%} số publication có phần tử).")
```

Nguyên nhân chính (đo ở một lần chẩn đoán trước khi chạy lại các publication dùng macro `etoolbox`): phần lớn là tệp `.bib` được gọi nhưng không có trong dữ liệu M1 (đề M1 chỉ giữ `.tex` và `.bib`, không giữ `.bbl`). Đây là giới hạn của dữ liệu đầu vào, không phải của parser.

# 6. Hiệu năng

```{code-cell} python
:tags: [remove-input]
okp = df[df["status"].isin(["success", "partial"]) & df["seconds"].notna()]
print(f"Thời gian xử lý mỗi publication (lần chạy cuối): trung bình {okp['seconds'].mean():.2f} s, trung vị {okp['seconds'].median():.2f} s, lớn nhất {okp['seconds'].max():.1f} s")
s = pd.DataFrame(runs)
s["wall (giờ)"] = (s["wall_seconds"] / 3600).round(2)
s["RAM đỉnh (GB)"] = (s["peak_rss_bytes"] / 1e9).round(2)
display(s[["started", "ids_attempted", "batches", "wall (giờ)", "RAM đỉnh (GB)"]].rename(columns={"started": "bắt đầu", "ids_attempted": "số ID thử", "batches": "số batch"}))
print(f"Tổng wall time cộng các phiên: {s['wall_seconds'].sum() / 3600:.2f} giờ | RAM đỉnh lớn nhất: {s['peak_rss_bytes'].max() / 1e9:.2f} GB | "
      f"dung lượng đầu ra: {sum(v['mb'] for v in sizes.values()):.0f} MB")
fig = px.histogram(okp, x="seconds", nbins=60, log_y=True, title="Phân bố thời gian xử lý mỗi publication",
                   labels={"seconds": "giây"})
fig
```

**Lưu ý khi đọc các số trên (giới hạn của phép đo):**

- Môi trường: Google Colab, chỉ CPU.
- Tổng wall time là tổng của **nhiều phiên**, gồm cả chạy lại sau khi sửa bộ gom và chạy lại ID lỗi; **không** phải thời gian của một lần chạy liên tục từ đầu đến cuối, và không tính thời gian sao chép dữ liệu M1.
- RAM đỉnh là RSS của **cả tiến trình notebook** (gồm `pandas`, `pyarrow`), đo bằng lấy mẫu mỗi 0,2 giây, không riêng bộ parser.
- Thời gian mỗi publication là của **lần chạy cuối** của publication đó.

# 7. Giới hạn đã biết

- **Chọn gốc không tự đoán.** `AMBIGUOUS_ROOT` còn lại là các tài liệu độc lập thực sự; chỉ xử lý được bằng rà soát thủ công, và dữ liệu thiếu có ghi nhận được ưu tiên hơn dữ liệu sai lẫn vào bảng.
- **Macro điều kiện tự định nghĩa.** Các macro `\if...{...}` do tác giả tự định nghĩa (không thuộc bảng macro đã biết) vẫn có thể gây `UNTERMINATED_CONDITIONAL` và làm bỏ sót phần văn bản phía sau. Mức độ phổ biến chưa được đo vì cảnh báo của bước gom không được lưu theo từng publication.
- **Alias của `\bibitem`.** Các bài định nghĩa `\newcommand{\bi}{\bibitem}` rồi viết `\bi{khóa}...` bị bỏ qua phần bibliography (một số ít publication).
- **Bibliography ngoài dữ liệu.** `.bib` không có trong dữ liệu M1 (kể cả khi chỉ có `.bbl`) không thể bù ở M2.
- **Bộ gom không phải trình thông dịch TeX.** Macro và gói không được thực thi; điều kiện chưa xác định được giữ nguyên và đánh dấu `partial`.

# 8. Tái lập kết quả

Mã nguồn nằm trong cùng repository của nhóm (`m2/src/parsing`). Lớp điều phối chạy theo lô (50 publication mỗi lô), ghi kết quả vào thư mục tạm, **đọc lại và kiểm tra** trước khi ghi đè tệp cũ, và chỉ đánh dấu thành công sau khi kiểm tra đạt; chỉ những publication lỗi mới được chạy lại khi retry. Hướng dẫn cài đặt môi trường và chạy nằm trong `README.md` của repository.
