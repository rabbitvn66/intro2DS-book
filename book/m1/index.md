---
title: Milestone 1 — Data Crawling
short_title: Tổng quan M1
label: m1-crawling
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  name: python3
  display_name: Python 3
---

:::{note} Phụ trách: Hương
Xoá khung này khi viết xong. Các đoạn *(in nghiêng trong ngoặc)* là gợi ý — thay bằng nội dung của bạn.
:::

# Milestone 1 — Data Crawling

## Tổng quan
*(Dải ID của nhóm, tổng số bài, mỗi thành viên chạy phần nào, 4 cấu hình B / D1 / D2 / S1.)*

```{mermaid}
flowchart LR
  A[Danh sách ID] --> B[Discovery]
  B --> C[Download từng version]
  C --> D[Extract .tex/.bib]
  B --> E[References<br/>Semantic Scholar]
  D --> F[Storage + Validation]
  E --> F
```

## Bốn cấu hình thử nghiệm
| Cấu hình | Discovery | Tải nguồn | Người phụ trách |
|:--|:--|:--|:--|
| B | arXiv API | HTTP `/src/` | Hương |
| D1 | OAI-PMH | giống B | Linh |
| D2 | Kaggle | giống B | Châu |
| S1 | arXiv API | arxiv-downloader | *(chưa phân công)* |

## Mục lục báo cáo
- [](#m1-discovery-arxiv) · [](#m1-discovery-oai) · [](#m1-discovery-kaggle)
- [](#m1-download) · [](#m1-extract) · [](#m1-references)
- [](#m1-stats) · [](#m1-perf) · [](#m1-compare)
