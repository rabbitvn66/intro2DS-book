---
title: 6. Kiểm nghiệm và lựa chọn cấu hình crawler
short_title: 06. Đánh giá cấu hình
label: m1-06-evaluation
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

# 6. Kiểm nghiệm và lựa chọn cấu hình crawler

Việc lựa chọn được thực hiện theo hai bước: **chọn công cụ discovery/download**, sau đó **chọn cách tổ chức xử lý đồng thời** trên bộ công cụ đã chọn. Các tiêu chí là kết quả crawl, wall time toàn pipeline và RAM. Mục tiêu là hoàn thành cùng lượng công việc với thời gian thấp, bộ nhớ được kiểm soát và không đánh đổi tính hợp lệ của dữ liệu.

Nhóm chỉ trình bày các setting đã chốt sau khảo sát ban đầu; không trình bày quá trình tuning. Các bảng, tỷ lệ, độ lệch chuẩn và biểu đồ bên dưới được tính khi build từ số liệu từng run trong `data/evaluation_benchmarks.json`.

```{code-cell} python
:tags: [remove-input]
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

for candidate in [Path.cwd(), *Path.cwd().parents]:
    data_file = candidate / "data" / "evaluation_benchmarks.json"
    if data_file.is_file():
        break
else:
    raise FileNotFoundError("Cần có book/data/evaluation_benchmarks.json")

benchmark = json.loads(data_file.read_text(encoding="utf-8"))
assert benchmark["schema_version"] == 1
phase_data = {p["key"]: p for p in benchmark["phases"]}
names = {"batch": "Batch lanes", "bounded": "Bounded pipeline", "parallel": "Parallel papers"}
colors = {"batch": "#CB8C2C", "bounded": "#168678", "parallel": "#6C79A8"}
order = ["batch", "bounded", "parallel"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 120})

def summarize_phase(key):
    phase = phase_data[key]
    rows = []
    for variant in order:
        runs = [r for r in phase["runs"] if r["variant"] == variant]
        if not runs:
            continue
        assert len(runs) == phase["repeats_per_setting"]
        assert sorted(r["repeat"] for r in runs) == list(range(1, len(runs) + 1))
        wall = pd.Series([r["wall_seconds"] for r in runs], dtype=float)
        peak = pd.Series([r["rss_peak_bytes"] / 2**20 for r in runs], dtype=float)
        mean_rss = pd.Series([r["rss_mean_bytes"] / 2**20 for r in runs], dtype=float)
        denominator = sum(r["n_ids"] for r in runs)
        ok = sum(r["validated_ok"] for r in runs)
        rows.append(dict(variant=variant, n=len(runs), ids_per_run=phase["n_ids"],
                         wall_mean=wall.mean(), wall_sd=wall.std(ddof=1),
                         wall_per_id=wall.mean()/phase["n_ids"],
                         peak_mean=peak.mean(), peak_sd=peak.std(ddof=1),
                         rss_mean=mean_rss.mean(), ok=ok, denominator=denominator,
                         success_rate=ok/denominator,
                         http429=sum(r["observed_http_429_attempts"] for r in runs)))
    return pd.DataFrame(rows).set_index("variant")

def show_summary(stats):
    table = pd.DataFrame({
        "Cấu hình": [names[v] for v in stats.index],
        "Số lượt": stats["n"].to_numpy(),
        "Wall time (s), TB ± SD": [f"{r.wall_mean:.3f} ± {r.wall_sd:.3f}" for r in stats.itertuples()],
        "Wall / ID (s)": [f"{x:.3f}" for x in stats["wall_per_id"]],
        "RAM đỉnh (MiB), TB ± SD": [f"{r.peak_mean:.3f} ± {r.peak_sd:.3f}" for r in stats.itertuples()],
        "RAM TB/run (MiB)": [f"{x:.3f}" for x in stats["rss_mean"]],
        "Thành công": [f"{r.ok}/{r.denominator} ({r.success_rate:.2%})" for r in stats.itertuples()],
    })
    display(table.style.hide(axis="index"))

def plot_phase(stats, title):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    x = np.arange(len(stats))
    for ax, mean, sd, ylabel in [
        (axes[0], "wall_mean", "wall_sd", "Wall time (giây)"),
        (axes[1], "peak_mean", "peak_sd", "RAM RSS đỉnh (MiB)"),
    ]:
        means, deviations = stats[mean].to_numpy(), stats[sd].to_numpy()
        ax.bar(x, means, yerr=deviations, capsize=5,
               color=[colors[v] for v in stats.index], width=0.58)
        top = float(np.max(means + deviations))
        for position, value, deviation in zip(x, means, deviations):
            ax.text(position, value + deviation + top*0.035, f"{value:.2f}",
                    ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x, [names[v].replace(" ", "\n") for v in stats.index])
        ax.set_ylabel(ylabel)
        ax.set_ylim(0, top*1.24)
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
    fig.suptitle(title + " — trung bình và độ lệch chuẩn mẫu", fontsize=11)
    fig.tight_layout()
    plt.show()

def show_stages(key):
    phase = phase_data[key]
    stage_rows = []
    for variant in order:
        runs = [r for r in phase["runs"] if r["variant"] == variant]
        if not runs:
            continue
        values = {"Discovery": [r["discovery_seconds"] for r in runs]}
        values.update({stage.title(): [r["stages"][stage] for r in runs]
                       for stage in ("download", "extract", "references", "storage")})
        row = {"Cấu hình": names[variant]}
        for stage, measurements in values.items():
            row[stage + " (s)"] = f"{np.mean(measurements):.3f} ± {np.std(measurements, ddof=1):.3f}"
        stage_rows.append(row)
    display(pd.DataFrame(stage_rows).style.hide(axis="index"))
```

## 6.1. Chọn công cụ: thay discovery/download, giữ các stage chung

Trước khi tối ưu xử lý đồng thời, nhóm so sánh ba cách lấy metadata và tải source. Khối chức năng chung từ **extract → references → storage/validation** được giữ làm cơ sở đối chiếu. Ba phương án đều hướng tới cùng schema đầu ra; khác nhau ở nguồn discovery và cách đưa dữ liệu vào pipeline.

```{mermaid}
flowchart LR
    IDs["Cùng tập arXiv ID"] --> B["B: arXiv API"]
    IDs --> K["K: Kaggle snapshot"]
    IDs --> D["D1: OAI-PMH"]
    B --> HTTP["HTTP /src/: source các version"]
    K --> HTTP
    D --> HTTP
    HTTP --> Common["Extract → References → Storage / Validation"]
```

Đầu vào gồm cùng 40 ID theo cùng thứ tự; các run là cold, không resume. Delay arXiv là 3 giây, timeout 30 giây và tối đa 3 retry.

```{code-cell} python
:tags: [remove-input]
tools = pd.DataFrame(benchmark["tool_runs"])
tools["success_rate"] = tools["paper_ok"] / tools["n_ids"]
tools["wall_per_id"] = tools["wall_seconds"] / tools["n_ids"]
tools["rss_peak_mib"] = tools["rss_peak_bytes"].map(
    lambda value: value / 2**20 if pd.notna(value) else np.nan)
tool_table = tools[["variant", "discovery", "n_ids", "paper_ok", "paper_failed",
                    "success_rate", "wall_seconds", "wall_per_id"]].copy()
tool_table.columns = ["Công cụ", "Discovery", "ID đầu vào", "Thành công", "Thất bại",
                      "Tỷ lệ đạt", "Wall time (s)", "Wall / ID (s)"]
display(tool_table.style.hide(axis="index").format(
    {"Tỷ lệ đạt": "{:.1%}", "Wall time (s)": "{:.3f}",
     "Wall / ID (s)": "{:.3f}"}, na_rep="Chưa cung cấp"))

fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
tool_colors = ["#168678", "#CB8C2C", "#6C79A8"]
for ax, column, label, fmt in [
    (axes[0], "wall_seconds", "Wall time (giây)", "{:.1f}"),
    (axes[1], "success_rate", "Paper thành công (%)", "{:.1f}%"),
]:
    values = tools[column].to_numpy() * (100 if column == "success_rate" else 1)
    bars = ax.bar(tools["variant"], values, color=tool_colors, width=0.55)
    ax.bar_label(bars, labels=[fmt.format(v) for v in values], padding=5)
    ax.set_ylabel(label)
    ax.set_ylim(0, max(values)*1.18)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
fig.suptitle("Chọn công cụ — cùng 40 ID, một run mỗi phương án")
fig.tight_layout()
plt.show()

base_wall = tools.set_index("variant").loc["B", "wall_seconds"]
for variant in ("K", "D1"):
    wall = tools.set_index("variant").loc[variant, "wall_seconds"]
    print(f"{variant} lâu hơn B: {wall-base_wall:.3f} s, tương ứng {(wall/base_wall-1)*100:.2f}%.")
```

**Lựa chọn công cụ: arXiv API + HTTP.** B đạt 40/40 paper và có wall time thấp nhất trong lần đối chiếu này. K và D1 đều đạt 35/40; các log ghi nhận lỗi references liên quan HTTP 429. Vì vậy, có thể coi ba phương án tương đồng về mục tiêu/schema và nhóm quyết định giữ phương án hoàn thiện B - phương án hoàn thiện ban đầu. 


## 6.2. Từ baseline tuần tự đến ba cách tổ chức đồng thời

Sau khi chọn arXiv API + HTTP, nhóm thay cách điều phối công việc. Các hàm extraction, references và storage vẫn giữ mục tiêu xử lý chung; thứ tự và khả năng chồng lấp giữa các paper/stage phụ thuộc phương án. Vì vậy, tiêu chí chính là **wall time từ bắt đầu đến khi mọi ID kết thúc**.

| Phương án | Cách xử lý đã kiểm tra từ source | Setting dùng trong các pilot |
|---|---|---|
| **Batch lanes** | Discovery theo batch. Với từng paper, references chạy song song nhánh download → extract; chờ hai nhánh xong mới storage. Vòng paper không dùng pool nhiều paper. | discovery batch size = 20. |
| **Bounded pipeline** | Một producer thực hiện discovery/download; pool extract và một consumer references chồng lấp công việc giữa các paper. Chỉ storage khi hai consumer hoàn tất; semaphore giới hạn paper đang xử lý. | Max inflight = **5**, extract workers = **2**, references worker = 1; extract queue = 2, references queue = 4, prefetch remaining = 5; discovery batch size = 20. |
| **Parallel papers** | Pool xử lý nhiều paper. Trong mỗi paper, extract → references → storage tuần tự sau download; khóa dùng chung giới hạn truy cập arXiv và references. | `max_workers` = **2**; discovery batch size mặc định = 1 trong snapshot thực nghiệm. |

Các setting trên là kết quả đã chọn sau khảo sát nhiều giá trị trên cùng tập ID. Nhóm chỉ trình bày các pilot kiểm chứng setting cuối, không trình bày grid tuning. Số worker extract và số worker paper là hai khái niệm khác nhau.

**Quy tắc đo:** cùng tập ID và thứ tự trong từng đợt; cold application cache, output/run ID riêng; cùng pacing/retry và chế độ references không API key. Các run chạy tuần tự, xáo thứ tự cấu hình theo vòng; không loại run chậm hoặc paper lỗi. RAM là RSS của cây tiến trình do ResourceMonitor đo; mỗi thanh RAM là trung bình đỉnh của các run, không phải một đỉnh toàn bộ các lần chạy.

Các bảng dùng trung bình và **độ lệch chuẩn mẫu (SD)** qua các run, không phải sai số chuẩn. Thành công trong pilot là validation đạt; một run `completed` vẫn có thể chứa paper thất bại. Với n ID/run và k lần lặp, mẫu số tỷ lệ là n × k lượt paper, không phải số paper duy nhất.

## 6.3. Kiểm chứng ba cấu hình đã chốt

Mỗi cấu hình chạy **5 lần**, tổng 15 run. Đây là tập 40 ID của đợt pilot xử lý đồng thời, khác tập đối chiếu B/K/D1 trước đó; nhóm không dùng hai tập để suy ra trực tiếp mức tăng tốc từ baseline sang đa luồng.

```{code-cell} python
:tags: [remove-input]
s40 = summarize_phase("pilot40")
show_summary(s40)
plot_phase(s40, "Pilot 40 ID — 5 run/cấu hình")
gap40 = s40.loc["batch", "wall_mean"] - s40.loc["bounded", "wall_mean"]
print(f"Bounded thấp hơn Batch trung bình {gap40:.3f} s ({100*gap40/s40.loc['batch','wall_mean']:.2f}%).")
```

Cả ba phương án đều đạt 38/40 paper trong từng run. Hai ID `2507.15396` và `2507.16398` thất bại tại references với `NOT_FOUND`, nên tỷ lệ của mỗi cấu hình là 190/200 lượt paper. Bounded có wall time trung bình thấp nhất, nhưng chênh lệch với Batch chỉ khoảng một giây và nhỏ so với độ biến thiên quan sát được. RAM của hai phương án cũng gần nhau; Batch có SD wall nhỏ hơn trong đợt này.

Parallel papers chậm hơn rõ rệt trong pilot 40 ID dù cùng kết quả crawl. Nhóm tiếp tục kiểm chứng **Batch và Bounded** trên 100 ID. Đây là quyết định nhằm thu hẹp phương án cho bước tiếp.

## 6.4. Pilot 100 ID, đợt 1: giữ nguyên lượt biến thiên lớn

Batch và Bounded mỗi cấu hình chạy **3 lần** trên cùng 100 ID. Tập 100 ID khác tập pilot 40 ID; mọi so sánh hiệu năng được thực hiện giữa các cấu hình trong cùng đợt.

```{code-cell} python
:tags: [remove-input]
s100a = summarize_phase("pilot100_first")
show_summary(s100a)
plot_phase(s100a, "Pilot 100 ID, đợt 1 — 3 run/cấu hình")
first_runs = pd.DataFrame([{
    "Vòng": r["repeat"], "Cấu hình": names[r["variant"]],
    "Wall time (s)": r["wall_seconds"], "Validation đạt": f"{r['validated_ok']}/{r['n_ids']}",
    "Attempt HTTP 429 được ghi nhận": r["observed_http_429_attempts"],
    "Attempt NETWORK_ERROR được ghi nhận": sum(e["count"] for e in r["observed_request_errors"] if e["error_code"] == "NETWORK_ERROR"),
} for r in phase_data["pilot100_first"]["runs"]])
display(first_runs.style.hide(axis="index").format({"Wall time (s)":"{:.3f}"}))
```

Ở đợt này, Batch có trung bình wall time thấp hơn. Tuy nhiên, Bounded vòng 1 kéo dài 1.786,047 giây, chỉ đạt 89/100 và ghi nhận 37 attempt HTTP 429 cùng 70 attempt NETWORK_ERROR ở download. Hai run Bounded sau đạt 100/100, với wall time quanh 512–525 giây. Batch vòng 1 cũng có lỗi tải và đạt 97/100; hai vòng sau đạt 100/100.

Các quan sát này phù hợp với giả thuyết thời gian chờ/retry dịch vụ bên ngoài góp phần làm tăng biến thiên. Chúng **không tách được chính xác phần ảnh hưởng của mạng khỏi cách điều phối**. Bounded vòng 1 được giữ trong trung bình và SD, không bị loại để cải thiện kết quả. Với độ biến thiên lớn và chỉ ba run, nhóm chưa chốt lựa chọn từ đợt này mà thực hiện thêm một đợt độc lập.

Tổng thời gian thao tác từng stage dưới đây được tính lại từ từng run. Discovery gồm cả batch và thao tác từng paper; các stage chồng lấp, nên không cộng chúng để suy ra wall time.

```{code-cell} python
:tags: [remove-input]
show_stages("pilot100_first")
```

## 6.5. Pilot 100 ID, đợt 2: tăng số lần lặp và kiểm thử lần cuối

Giữ nguyên setting và cùng tập 100 ID của đợt 1, nhóm chạy **5 lần mới cho mỗi cấu hình**, tổng 10 run. Đợt này được báo cáo độc lập, không gộp thành tám run với đợt trước; mọi lượt lỗi/chậm vẫn được tính.

```{code-cell} python
:tags: [remove-input]
s100b = summarize_phase("pilot100_repeat")
show_summary(s100b)
plot_phase(s100b, "Pilot 100 ID, đợt 2 — 5 run/cấu hình")

paired = pd.DataFrame(phase_data["pilot100_repeat"]["runs"]).pivot(
    index="repeat", columns="variant", values="wall_seconds").sort_index()
paired["Bounded giảm wall (%)"] = (1 - paired["bounded"] / paired["batch"]) * 100
display(paired.rename(columns={"batch":"Batch (s)","bounded":"Bounded (s)"})
        .rename_axis("Vòng").style.format("{:.3f}"))
gain = 100*(1-s100b.loc["bounded","wall_mean"]/s100b.loc["batch","wall_mean"])
seconds_saved = s100b.loc["batch","wall_mean"]-s100b.loc["bounded","wall_mean"]
win_count = int((paired["bounded"] < paired["batch"]).sum())
ram_gap = s100b.loc["batch","peak_mean"]-s100b.loc["bounded","peak_mean"]
print(f"Bounded giảm wall time trung bình: {seconds_saved:.3f} s, tương ứng {gain:.2f}%.")
print(f"Bounded có wall thấp hơn trong {win_count}/{len(paired)} vòng quan sát.")
print(f"Chênh lệch RAM đỉnh trung bình (Batch - Bounded): {ram_gap:.3f} MiB.")
```

Bounded có wall time trung bình thấp hơn và SD nhỏ hơn Batch trong đợt kiểm chứng này. Nó đạt 500/500 lượt paper; Batch đạt 499/500. Lỗi duy nhất làm Batch thất bại ở vòng 5 là lỗi truy cập file khi cập nhật manifest trong extraction của `2507.01720v4`; không có bằng chứng để quy lỗi đó cho thiết kế Batch.

RAM đỉnh trung bình của Bounded thấp hơn nhẹ, nhưng chênh lệch chỉ khoảng vài phần mười MiB và nằm trong vùng biến thiên của các run. RAM trung bình theo run lại cao hơn Batch rất nhẹ; vì vậy **không kết luận Bounded tiết kiệm RAM đáng kể**. Lợi thế quan sát rõ hơn ở wall time và mức hoàn thành trong đợt cuối.

```{code-cell} python
:tags: [remove-input]
show_stages("pilot100_repeat")
```

Discovery + download gần tương đương giữa hai phương án ở đợt cuối, trong khi wall time toàn pipeline của Bounded thấp hơn. Kết quả này cho thấy chỉ đánh giá discovery/download sẽ bỏ qua ảnh hưởng của chồng lấp extraction, references và storage. Tuy nhiên, số HTTP 429 cũng khác nhau; chưa đủ dữ liệu để quy toàn bộ mức giảm wall time cho cơ chế pipeline.

## 6.6. Quyết định cấu hình

| Bước lựa chọn | Phương án chọn | Căn cứ và giới hạn |
|---|---|---|
| Công cụ discovery/download | **arXiv API + HTTP** | Wall time thấp nhất và 40/40 paper thành công trong phép đối chiếu công cụ. Chưa có RAM B/K/D1; mỗi công cụ mới có một run. |
| Cách tổ chức xử lý | **Bounded pipeline** | Pilot 40 ID gần ngang Batch; đợt 100 ID đầu biến thiên lớn; đợt 100 ID lặp 5 lần cho wall time thấp hơn, RAM tương đương và 500/500 lượt paper đạt. |
| Setting triển khai | **Max inflight = 5, extract workers = 2** | Discovery batch size = 20, một references worker; các queue/prefetch giữ như bảng setting. |

Các tham số tương ứng trên `main` hiện tại:

```yaml
config_name: A_PIPELINE
discovery_batch_size: 20
pipeline_max_inflight: 5
pipeline_extract_workers: 2
pipeline_extract_queue: 2
pipeline_references_queue: 4
pipeline_prefetch_remaining: 5
```

Đây là lựa chọn dựa trên các lần chạy đã ghi nhận, không phải chứng minh một cấu hình tối ưu cho mọi workload. SD mô tả biến thiên quan sát được, không phải kiểm định khác biệt có ý nghĩa thống kê. Retry, rate limit và trạng thái dịch vụ bên ngoài vẫn ảnh hưởng kết quả.
