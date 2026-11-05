"""Nạp dữ liệu tóm tắt trong data/ cho mọi trang của sách. KHÔNG gọi mạng, KHÔNG đọc file ngoài data/."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"


def _csv(name):
    p = DATA / name
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


papers = _csv("papers.csv")
versions = _csv("versions.csv")
refs = _csv("references.csv")
runs = _csv("runs.csv")
events = (pd.read_json(DATA / "events.jsonl", lines=True)
          if (DATA / "events.jsonl").exists() else pd.DataFrame())
if len(events) and len(runs):
    events["config"] = events["run_id"].map(runs.set_index("run_id")["config"])

HAS_DATA = len(papers) > 0


def need_data():
    """Gọi đầu cell; trả False và in thông báo nếu chưa có dữ liệu."""
    if not HAS_DATA:
        print("Chưa có dữ liệu trong book/data/ — Hiền chạy export_for_book.py rồi commit.")
    return HAS_DATA


def paper_success(config=None):
    """Bài thành công = metadata ok và không version nào failed. Trả về DataFrame papers + cột success."""
    p = papers if config is None else papers[papers["config"] == config]
    v = versions if config is None else versions[versions["config"] == config]
    bad = set(v.loc[v["extract_status"].eq("failed") | v["download_status"].eq("failed"), "arxiv_id"])
    p = p.copy()
    p["success"] = p["metadata_status"].eq("ok") & ~p["arxiv_id"].isin(bad)
    return p
