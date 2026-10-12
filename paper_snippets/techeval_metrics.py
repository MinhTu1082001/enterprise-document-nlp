"""Technical evaluation [7]: Macro-F1 (phan loai), Span-F1 / Exact Match / IoU (trich xuat),
ROUGE-1 (tom tat). Cong thuc theo muc 3.8 cua bai (Eq. 9-12); tach tu don gian bang khoang trang."""
import re
from collections import Counter


def macro_f1(y_true, y_pred):
    f1s = []
    for c in sorted(set(y_true) | set(y_pred)):
        tp = sum(t == c and p == c for t, p in zip(y_true, y_pred))
        fp = sum(t != c and p == c for t, p in zip(y_true, y_pred))
        fn = sum(t == c and p != c for t, p in zip(y_true, y_pred))
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(f1s) / len(f1s)


def tokens(text):
    return re.findall(r"\w+", text.lower())


def span_scores(pred, gold):
    """Span tinh theo tap token: Span-F1 (Eq. 10), Exact Match, IoU (Eq. 11)."""
    P, G = set(tokens(pred)), set(tokens(gold))
    inter = len(P & G)
    return {"span_f1": round(2 * inter / (len(P) + len(G)), 3),
            "exact": float(tokens(pred) == tokens(gold)),
            "iou": round(inter / len(P | G), 3)}


def rouge1(reference, candidate):
    """ROUGE-1 (Eq. 12): so unigram trung / so unigram cua ban tham chieu (recall)."""
    ref, cand = Counter(tokens(reference)), Counter(tokens(candidate))
    overlap = sum(min(n, cand[w]) for w, n in ref.items())
    return round(overlap / sum(ref.values()), 3)


if __name__ == "__main__":
    print("macro-F1:", round(macro_f1(["NDA", "NDA", "NDA", "Lease"], ["NDA", "NDA", "NDA", "NDA"]), 3))
    gold = "The Receiving Party shall keep all Confidential Information strictly confidential."
    print("cat thieu:", span_scores("shall keep all Confidential Information", gold))
    ref = "Supplier shall not disclose Confidential Information without prior written consent."
    flipped = "Supplier shall disclose Confidential Information without prior written consent."
    print("ROUGE-1 khi nghia bi dao nguoc:", rouge1(ref, flipped))
