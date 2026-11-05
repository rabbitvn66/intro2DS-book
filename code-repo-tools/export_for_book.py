"""Gộp kết quả crawl (nhiều run) thành vài file CSV/JSONL NHỎ cho Jupyter Book.

Chạy từ gốc repo code (repo intro2DS):
    python -m src.tools.export_for_book experiments/B_run_a experiments/B_run_b \
        --out ../intro2DS-book/book/data

Đầu ra (không chứa file .tex, chỉ số liệu tóm tắt):
    papers.csv      1 dòng / bài báo  (metadata + số version + trạng thái)
    versions.csv    1 dòng / version  (manifest: trạng thái, kích thước trước/sau khi bỏ hình)
    references.csv  1 dòng / reference đã crawl (mọi reference, có cột has_arxiv_id)
    events.jsonl    sự kiện đo thời gian/tài nguyên (metrics_events.jsonl của các run, đã gộp)
    runs.csv        1 dòng / run (run.json rút gọn: thời điểm bắt đầu/kết thúc, trạng thái)
"""
import argparse
import csv
import json
import pathlib


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"{path}: {len(rows)} dòng")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="+", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    papers, versions, refs, runs = [], [], [], []
    events = open(args.out / "events.jsonl", "w", encoding="utf-8")

    for run in args.run_dirs:
        rj = read_json(run / "run.json") or {}
        config = rj.get("config_name") or run.name.split("_")[0]  # B, D1, D2, S1 ...
        runs.append({
            "run_id": run.name, "config": config, "run_status": rj.get("run_status"),
            "cache_mode": rj.get("cache_mode"), "started_at": rj.get("started_at"),
            "finished_at": rj.get("finished_at"), "n_ids": len(rj.get("input_ids", [])),
        })
        ev = run / "metrics_events.jsonl"
        if ev.exists():
            events.write(ev.read_text(encoding="utf-8"))

        for pdir in sorted((run / "papers").glob("*/")):
            meta = read_json(pdir / "metadata.json") or {}
            aid = meta.get("arxiv_id")
            if not aid:
                continue
            r = read_json(pdir / "references.json") or {}
            val = read_json(pdir / "validation.json") or {}
            papers.append({
                "run_id": run.name, "config": config, "arxiv_id": aid, "title": meta.get("title"),
                "n_authors": len(meta.get("authors") or []),
                "submission_date": meta.get("submission_date"),
                "latest_version": meta.get("latest_version"),
                "venue": meta.get("venue"), "metadata_status": meta.get("status"),
                "references_status": r.get("status"),
                "validation_status": val.get("status", val.get("validation_status")),
            })
            for vdir in sorted((pdir / "versions").glob("v*/")):
                m = read_json(vdir / "manifest.json") or {}
                versions.append({"run_id": run.name, "config": config, "arxiv_id": aid, **m})
            for ref in r.get("references") or []:
                refs.append({
                    "run_id": run.name, "arxiv_id": aid,
                    "ref_arxiv_id": ref.get("ref_arxiv_id"),
                    "ref_s2_id": ref.get("ref_s2_id"),
                    "ref_title": ref.get("ref_title"),
                    "has_arxiv_id": bool(ref.get("ref_arxiv_id")),
                })
    events.close()

    write_csv(args.out / "runs.csv", runs,
              ["run_id", "config", "run_status", "cache_mode", "started_at", "finished_at", "n_ids"])
    write_csv(args.out / "papers.csv", papers,
              ["run_id", "config", "arxiv_id", "title", "n_authors", "submission_date", "latest_version",
               "venue", "metadata_status", "references_status", "validation_status"])
    vfields = ["run_id", "config", "arxiv_id", "version", "versioned_id", "download_status",
               "extract_status", "source_format", "archive_bytes",
               "unpacked_total_bytes", "kept_source_bytes", "error_code"]
    write_csv(args.out / "versions.csv", versions, vfields)
    write_csv(args.out / "references.csv", refs,
              ["run_id", "arxiv_id", "ref_arxiv_id", "ref_s2_id", "ref_title", "has_arxiv_id"])


if __name__ == "__main__":
    main()
