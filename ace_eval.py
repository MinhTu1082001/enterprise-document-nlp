#!/usr/bin/env python3
"""Case B · theo COMPACT [6]: chấm zero-shot một mẫu nhỏ của tập test ACE.

Mỗi mẫu ACE có vài điều khoản hợp đồng, một tình huống và nhãn đúng: Compliant, Non-Compliant
hoặc Not-Applicable. Script hỏi LLM, đọc dòng FINAL_ANSWER, rồi tính accuracy, macro-F1,
ma trận nhầm lẫn và tách kết quả theo số điều khoản (1 so với 2 trở lên).

  git clone https://github.com/FujitsuResearch/Fujitsu-Assessing-Compliance-in-Enterprise-Dataset ace
  python ace_eval.py --data ace/test.json --mock                  # thử đường ống, không gọi LLM
  python ace_eval.py --data ace/test.json --per-label 20          # 60 mẫu, gọi LLM thật

Mô hình và nhà cung cấp đặt bằng biến môi trường như run_demo.py (LLM_BASE_URL, LLM_MODEL, ...).
Prompt phỏng theo cách chấm của bài (Phụ lục D: kết thúc bằng FINAL_ANSWER A/B/C), không phải
nguyên văn. Số của bài tính trên cả 1.100 mẫu test nên chỉ dùng để tham chiếu, không so trực tiếp.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract_demo.detect import LLMClient  # noqa: E402

LETTER = {"A": "Non-Compliant", "B": "Compliant", "C": "Not-Applicable"}
LABELS = list(LETTER.values())

SYSTEM = "You are a careful contract compliance analyst."
PROMPT = """Read the contract clauses and the scenario, then decide whether the scenario complies with the clauses.

Clauses:
{clauses}

Scenario:
{scenario}

Options:
A. Non-Compliant: the scenario violates the clauses.
B. Compliant: the scenario satisfies the clauses.
C. Not-Applicable: the clauses do not govern this scenario.

Explain your reasoning in at most five sentences, then end with exactly one line in the form
FINAL_ANSWER: A
(or B, or C)."""

# Bảng 6 của COMPACT: accuracy zero-shot trên cả 1.100 mẫu test, trước khi dạy thêm
PAPER_ZERO_SHOT = {"Llama-3.2-3B": 42.4, "Llama-3.1-8B": 34.5, "Qwen2.5-1.5B": 45.2,
                   "Qwen2.5-3B": 42.5, "Qwen2.5-7B": 56.8}


def parse_answer(text: str) -> str | None:
    """Đọc nhãn sau dòng FINAL_ANSWER cuối cùng; chấp nhận A/B/C hoặc tên nhãn. Không đọc được thì None."""
    starts = [m.end() for m in re.finditer(r"FINAL[_ ]ANSWER", text, re.I)]
    if not starts:
        return None
    tail = text[starts[-1]:starts[-1] + 40]
    m = re.match(r"\W{0,6}([ABC])\b", tail, re.I)
    if m:
        return LETTER[m.group(1).upper()]
    low = tail.lower()
    for word, lab in (("non-compliant", "Non-Compliant"), ("not-applicable", "Not-Applicable"),
                      ("not applicable", "Not-Applicable"), ("compliant", "Compliant")):
        if word in low:
            return lab
    return None


def sample(rows: list[dict], per_label: int, min_clauses: int, max_clauses: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for lab in LABELS:
        pool = [r for r in rows if r["gd_tr"] == lab and min_clauses <= len(r["clauses"]) <= max_clauses]
        out += rng.sample(pool, min(per_label, len(pool)))
    return out


def metrics(gold: list[str], pred: list[str | None]) -> dict:
    n = len(gold)
    acc = sum(g == p for g, p in zip(gold, pred)) / n if n else 0.0
    f1s = {}
    for lab in LABELS:
        tp = sum(g == lab and p == lab for g, p in zip(gold, pred))
        fp = sum(g != lab and p == lab for g, p in zip(gold, pred))
        fn = sum(g == lab and p != lab for g, p in zip(gold, pred))
        f1s[lab] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    confusion = Counter((g, p or "không đọc được") for g, p in zip(gold, pred))
    return {"n": n, "accuracy": acc, "macro_f1": sum(f1s.values()) / len(f1s), "f1": f1s,
            "unparsed": sum(p is None for p in pred) / n if n else 0.0,
            "confusion": {f"{g} -> {p}": c for (g, p), c in sorted(confusion.items())}}


def bootstrap_ci(gold: list[str], pred: list[str | None], k: int = 1000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    idx = range(len(gold))
    accs = sorted(sum(gold[i] == pred[i] for i in s) / len(gold)
                  for s in ([rng.choice(idx) for _ in idx] for _ in range(k)))
    return accs[int(0.025 * k)], accs[int(0.975 * k) - 1]


class AlwaysCompliant:
    """--mock: luôn chọn B. Vừa để thử đường ống, vừa là mốc 'đoán một nhãn' (khoảng 33%)."""
    def __init__(self):
        self.calls, self.usage = 0, {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, system: str, user: str) -> str:
        self.calls += 1
        return "The scenario appears to follow the clauses.\nFINAL_ANSWER: B"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ace/test.json")
    ap.add_argument("--per-label", type=int, default=20)
    ap.add_argument("--min-clauses", type=int, default=1)
    ap.add_argument("--max-clauses", type=int, default=99)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default="out/ace_results.json")
    a = ap.parse_args()

    rows = json.load(open(a.data, encoding="utf-8"))["scenarios"]   # file có dạng {"scenarios": [...]}
    items = sample(rows, a.per_label, a.min_clauses, a.max_clauses, a.seed)
    client = AlwaysCompliant() if a.mock else LLMClient()
    if not a.mock:
        print(f"LLM: {client.model} @ {client.base_url}")

    preds, records = [], []
    for i, r in enumerate(items, 1):
        clauses = "\n".join(f"[{k}] {v}" for k, v in r["clauses"].items())
        raw = client.chat(SYSTEM, PROMPT.format(clauses=clauses, scenario=r["scenario_text"]))
        p = parse_answer(raw)
        preds.append(p)
        records.append({"gold": r["gd_tr"], "pred": p, "n_clauses": len(r["clauses"]), "raw": raw[-400:]})
        print(f"\r{i}/{len(items)}", end="", flush=True)
    print()

    gold = [r["gd_tr"] for r in items]
    m = metrics(gold, preds)
    lo, hi = bootstrap_ci(gold, preds)
    by_size = {}
    for name, keep in (("1 điều khoản", lambda n: n == 1), ("2+ điều khoản", lambda n: n >= 2)):
        idx = [i for i, r in enumerate(records) if keep(r["n_clauses"])]
        if idx:
            by_size[name] = metrics([gold[i] for i in idx], [preds[i] for i in idx])

    print(f"Mẫu: {m['n']}  accuracy = {100 * m['accuracy']:.1f}% (95% CI {100 * lo:.1f}–{100 * hi:.1f})  "
          f"macro-F1 = {100 * m['macro_f1']:.1f}  không đọc được = {100 * m['unparsed']:.1f}%")
    for name, s in by_size.items():
        print(f"  {name:14s} n={s['n']:3d}  accuracy = {100 * s['accuracy']:.1f}%")
    print("  Ma trận nhầm lẫn:", m["confusion"])
    print("  Tham chiếu COMPACT Bảng 6 (zero-shot, cả 1.100 mẫu):",
          ", ".join(f"{k} {v}" for k, v in PAPER_ZERO_SHOT.items()))
    print(f"  LLM calls = {client.calls}, tokens = {sum(client.usage.values())}")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"model": getattr(client, "model", "mock"), "args": vars(a), "metrics": m,
                   "ci95": [lo, hi], "by_size": by_size, "items": records}, f, ensure_ascii=False, indent=2)
    print("Đã ghi", a.out)


if __name__ == "__main__":
    main()
