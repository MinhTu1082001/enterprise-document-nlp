#!/usr/bin/env python3
"""Gộp kết quả Case A (nhiều hợp đồng, nhiều seed) thành một bảng cho chương demo.

  python summarize.py out/*/results.json

Cộng TP, FN, FP của từng cấu hình qua mọi lần chạy rồi mới tính P, R, F1 (micro), giống cách
CLAUSE [1] cộng dồn trên cả tập. In bảng markdown và ghi summary.csv cạnh thư mục đầu tiên.
"""
import csv
import json
import os
import sys
from collections import defaultdict


def main(paths: list[str]) -> None:
    if not paths:
        raise SystemExit("Cần ít nhất một file results.json")
    tot = defaultdict(lambda: defaultdict(int))
    kinds = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for p in paths:
        res = json.load(open(p, encoding="utf-8"))["results"]
        for cfg, r in res.items():
            for k in ("tp", "fn", "fp", "llm_calls"):
                tot[cfg][k] += r[k]
            tot[cfg]["tokens"] += r.get("tokens") or 0
            tot[cfg]["runs"] += 1
            for kind, v in r["per_kind"].items():
                kinds[cfg][kind][0] += v["found"]
                kinds[cfg][kind][1] += v["total"]

    rows = []
    for cfg, t in tot.items():
        p = t["tp"] / (t["tp"] + t["fp"]) if t["tp"] + t["fp"] else 0.0
        r = t["tp"] / (t["tp"] + t["fn"]) if t["tp"] + t["fn"] else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        found = ", ".join(f"{k} {a}/{b}" for k, (a, b) in sorted(kinds[cfg].items()))
        rows.append([cfg, t["runs"], t["tp"], t["fn"], t["fp"], round(p, 3), round(r, 3), round(f1, 3),
                     t["llm_calls"], t["tokens"], found])

    head = ["cấu hình", "lần chạy", "TP", "FN", "FP", "P", "R", "F1", "lần gọi LLM", "token", "bắt được theo loại"]
    print("| " + " | ".join(head) + " |")
    print("|" + " --- |" * len(head))
    for row in rows:
        print("| " + " | ".join(str(x) for x in row) + " |")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(paths[0]))), "summary.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    print("Đã ghi", out)


if __name__ == "__main__":
    main(sys.argv[1:])
