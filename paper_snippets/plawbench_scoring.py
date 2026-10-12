"""PLawBench [2]: diem rubric (scoring rate), diem tong co trong so, va he so Pearson
dung de chon giam khao. So lieu GPT-5.2 va Claude-opus-4.5 lay tu Bang 3 (ban ACL).

Chay:  python plawbench_scoring.py
       python plawbench_scoring.py duong/dan/practical_case_analysis_250.jsonl   (tuy chon)
"""
import json
import sys
from math import sqrt


def scoring_rate(items):
    """items: [(diem dat, diem toi da), ...] cua mot cau tra loi (Eq. 1)."""
    got, best = sum(a for a, _ in items), sum(b for _, b in items)
    return 100 * got / best if best else 0.0


def pca_rates(details):
    """Giong LegalEvaluator._calculate_metrics (prompt_zh.py): ty le tung phan
    va ty le chung = tong diem dat / tong diem toi da (gop diem, KHONG lay trung binh)."""
    rates = {k: 100 * a / b if b else 0.0 for k, (a, b) in details.items()}
    got = sum(a for a, _ in details.values())
    best = sum(b for _, b in details.values())
    rates["acc"] = 100 * got / best if best else 0.0
    return rates


def overall(t1, t2, t3, w=(2, 5, 3)):
    return sum(x * k for x, k in zip((t1, t2, t3), w)) / sum(w)


def pearson(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


def point_shares(jsonl_path):
    """Ty le diem cua 4 phan tren file PCA cong khai (moi dong co 4 khoi rubric)."""
    totals = {}
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            for block in json.loads(line)["rubrics"]:
                totals[block["tags"]] = totals.get(block["tags"], 0) + float(block["points"])
    s = sum(totals.values())
    return {k: round(100 * v / s, 1) for k, v in totals.items()}, s


if __name__ == "__main__":
    # Mot cau phan tich vu viec: 4 nhom tieu chi, diem dat / toi da (vi du tu dat)
    answer = [(10, 10), (12, 15), (10, 30), (2, 10)]   # ket luan, du kien, lap luan, dieu luat
    print("scoring rate:", round(scoring_rate(answer), 2))

    # Cau dau tien cua file PCA cong khai (vu quay phim dam cuoi): toi da 5 + 20 + 20 + 15 = 60
    wedding = {"conclusion": (5, 5), "facts": (15, 20), "reasoning": (10, 20), "statute": (5, 15)}
    r = pca_rates(wedding)
    mean4 = sum(r[k] for k in wedding) / 4
    print("PCA tung phan:", {k: round(v, 1) for k, v in r.items()}, "| TB 4 cot:", round(mean4, 1))

    gpt52 = dict(t1=79.57, t2=66.37, t3=68.58)
    print("GPT-5.2 2:5:3 =", round(overall(**gpt52), 2))
    print("GPT-5.2 neu T3 = TB(58.25, 63.42):", round(overall(79.57, 66.37, (58.25 + 63.42) / 2), 2))
    print("GPT-5.2 trong so theo so cau 60:750:40:", round(overall(**gpt52, w=(60, 750, 40)), 2))
    print("Claude-opus-4.5 theo so cau:", round(overall(68.92, 68.00, 62.27, w=(60, 750, 40)), 2))
    human = [62, 70, 55, 81, 90, 45]                    # diem chuyen gia (vi du tu dat)
    judge = [65, 72, 50, 85, 88, 52]                    # diem giam khao LLM
    print("Pearson nguoi - giam khao:", round(pearson(human, judge), 3))

    if len(sys.argv) > 1:
        print("Ty le diem 4 phan tren file PCA:", point_shares(sys.argv[1]))
