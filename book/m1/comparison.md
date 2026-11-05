---
title: So sánh bốn cấu hình B / D1 / D2 / S1
short_title: So sánh cấu hình
label: m1-compare
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

:::{note} Phụ trách: Hiền (bảng, hình) — mỗi người điền nhận xét cho cấu hình của mình
:::

# So sánh bốn cấu hình

```{code-cell} python
:tags: [remove-input]
import sys, pathlib
for _p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:
    if (_p / "bookdata.py").exists():
        sys.path.insert(0, str(_p)); break
import bookdata as bd
import pandas as pd
import matplotlib.pyplot as plt
```

```{code-cell} python
:tags: [remove-input]
if bd.need_data() and bd.runs["config"].nunique() > 0:
    rows = []
    for cfg in sorted(bd.runs["config"].dropna().unique()):
        p = bd.paper_success(cfg)
        e = bd.events[(bd.events["config"] == cfg) & (bd.events["event"] == "finished")]
        pt = e[e["stage"] == "paper"]["duration_s"]
        rows.append({"Cấu hình": cfg, "Số bài": len(p),
                     "Tỉ lệ thành công": f"{p['success'].mean():.1%}",
                     "TB giây / bài": round(pt.mean(), 1) if len(pt) else None})
    display(pd.DataFrame(rows))
```

## Nhận xét
- **B (Hương):** *(…)*
- **D1 (Linh):** *(…)*
- **D2 (Châu):** *(…)*
- **S1 (chưa phân công):** *(…)*
