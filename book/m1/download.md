---
title: Tải mã nguồn và tầng HTTP
short_title: Download / HTTP
label: m1-download
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

# Tải mã nguồn và tầng HTTP

*(Baseline B: endpoint `export.arxiv.org/src/{id}vN`; `Throttle` giữ khoảng cách 3 giây; retry/backoff; timeout; phân biệt NOT_FOUND / HTTP_429 / HTTP_5XX; User-Agent. Bảng mã lỗi và cách xử lý từng mã.)*
