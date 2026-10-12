#!/usr/bin/env python3
"""Chạy toàn bộ pipeline trên một hợp đồng.

  python run_demo.py --contract data/sample_contract.txt --seed 1 --mock
  python run_demo.py --contract data/cuad/XYZ.txt --seed 3 --configs rule,llm,llm2,graph

Không có --mock thì cần LLM_API_KEY (và LLM_BASE_URL, LLM_MODEL nếu không dùng Groq).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contract_demo.clauses import split_clauses, annotate, render  # noqa: E402
from contract_demo.graph import build_graph  # noqa: E402
from contract_demo.perturb import inject, KINDS  # noqa: E402
from contract_demo.detect import rule_detector, llm_full_document, llm_with_graph, LLMClient, MockClient  # noqa: E402
from contract_demo.score import align, per_kind  # noqa: E402
from contract_demo.report import write_report, write_json  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="data/sample_contract.txt")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--n", type=int, default=1, help="số lỗi mỗi loại")
    ap.add_argument("--configs", default="rule,llm,llm2,graph")
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--mock", action="store_true", help="không gọi LLM; dùng bộ luật giả làm LLM để thử pipeline")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    text = open(a.contract, encoding="utf-8").read()
    clean = annotate(split_clauses(text))
    perturbed, perts = inject(clean, kinds=a.kinds.split(","), n_per_kind=a.n, seed=a.seed)
    annotate(perturbed)
    g = build_graph(perturbed)          # đồ thị dựng trên bản đã cài lỗi, như khi dùng thật
    document = render(perturbed)
    gold = [{"kind": p.kind, "span": p.gt_span, "cid": p.cid, "contradicted": p.contradicted} for p in perts]

    print(f"Điều khoản: {len(clean)}  | cạnh đồ thị: {len(g.edges)}  | lỗi đã cài: {len(perts)}")
    for p in perts:
        print(f"  - {p.kind:24s} tại {p.cid:>5s}  mâu thuẫn với {p.contradicted}")

    client = MockClient(perturbed, g) if a.mock else LLMClient()
    if not a.mock:
        print(f"LLM: {client.model} @ {client.base_url}  (cache: {client.cache_path or 'tắt'})")
    results = {}
    for cfg in a.configs.split(","):
        t0 = time.time()
        tok0 = sum(getattr(client, "usage", {}).values())
        if cfg == "rule":
            preds = rule_detector(perturbed, g); calls = 0
        elif cfg == "llm":
            before = client.calls; preds = llm_full_document(document, client, one_shot=False); calls = client.calls - before
        elif cfg == "llm2":
            before = client.calls; preds = llm_full_document(document, client, one_shot=True); calls = client.calls - before
        elif cfg == "graph":
            before = client.calls; preds = llm_with_graph(perturbed, g, client, hops=a.hops); calls = client.calls - before
        else:
            raise SystemExit(f"cấu hình lạ: {cfg}")
        spans = [p.span for p in preds]
        al = align([x["span"] for x in gold], spans)
        tokens = sum(getattr(client, "usage", {}).values()) - tok0
        results[cfg] = {"alignment": al, "per_kind": per_kind(gold, spans), "pred_spans": spans,
                        "predictions": [p.to_dict() for p in preds], "calls": calls,
                        "tokens": tokens, "seconds": round(time.time() - t0, 1)}
        found = " ".join(f"{k[:5]}={a.tp}/{a.tp + a.fn}" for k, a in results[cfg]["per_kind"].items())
        print(f"{cfg:6s} TP={al.tp} FN={al.fn} FP={al.fp}  P={al.precision:.2f} R={al.recall:.2f} F1={al.f1:.2f}  "
              f"calls={calls:>3} tokens={tokens:>6} time={time.time() - t0:5.1f}s  [{found}]")

    os.makedirs(a.out, exist_ok=True)
    write_json(os.path.join(a.out, "results.json"), gold, results, g)
    write_report(os.path.join(a.out, "report.html"), document, gold, results, g, [p.to_dict() for p in perts])
    with open(os.path.join(a.out, "perturbed.txt"), "w", encoding="utf-8") as f:
        f.write(document)
    print(f"Đã ghi {a.out}/results.json, report.html, perturbed.txt")


if __name__ == "__main__":
    main()
