"""A Few Good Clauses [5]: cham trich xuat theo truong, micro/macro F1 va chi phi.

Quy tac ghep theo Bang 2 cua bai (khong chuan hoa ngay, tien, chu hoa):
  text        : doan du doan co phan chung voi doan chuan
  duration/date/currency : cau tra loi CHUA gia tri chuan
  category/id : bang nhau dung tung ky tu
Bai khong noi ro cach dem TP/FP/FN; quy uoc duoi day la cua nhom.
"""
from collections import defaultdict


def match(kind, pred, gold):
    if pred is None:
        return False
    if kind == "text":                       # co tu chung (gian luoc cho 'span overlap')
        return bool(set(pred.lower().split()) & set(gold.lower().split()))
    if kind in ("duration", "date", "currency"):
        return gold in pred                  # "contains", khong chuan hoa
    return pred == gold                      # category / identifier: exact


def score(items):
    """items: (field, kind, pred, gold). Tra ve dem TP/FP/FN theo truong."""
    c = defaultdict(lambda: [0, 0, 0])       # tp, fp, fn
    for field, kind, pred, gold in items:
        if gold is None and pred is not None:
            c[field][1] += 1                 # bao thua
        elif gold is not None and pred is None:
            c[field][2] += 1                 # bo sot
        elif gold is not None:
            if match(kind, pred, gold):
                c[field][0] += 1
            else:                            # tra loi sai = vua thua vua sot
                c[field][1] += 1
                c[field][2] += 1
    return c


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def micro_macro(counts):
    tp, fp, fn = (sum(v[i] for v in counts.values()) for i in range(3))
    micro = prf(tp, fp, fn)[2]
    macro = sum(prf(*v)[2] for v in counts.values()) / len(counts)
    return round(micro, 3), round(macro, 3)


def cost_per_doc(seconds, docs=1, usd_per_gpu_hour=4.01, gpus=1):
    return round(seconds / 3600 * usd_per_gpu_hour * gpus / docs, 4)


if __name__ == "__main__":
    items = [
        ("Governing Law", "id", "Delaware", "Delaware"),
        ("Governing Law", "id", "State of New York", "New York"),       # exact -> sai
        ("Effective Date", "date", "January 5, 2021", "January 5, 2021"),
        ("Effective Date", "date", "05/01/2021", "January 5, 2021"),    # khong chuan hoa -> sai
        ("Termination", "text", "either party may terminate upon notice", "Either party may terminate"),
        ("Renewal Type", "category", None, "Automatic"),                # bo sot
    ]
    c = score(items)
    for f, v in c.items():
        print(f, v, [round(x, 2) for x in prf(*v)])
    print("micro, macro F1:", micro_macro(c))
    # Bang 6 cua bai: lo 24 hop dong chay het 6 phut 27 giay; 1 hop dong chay rieng 131,55 giay
    print("batched  1 GPU:", cost_per_doc(387, docs=24), " 2 GPU:", cost_per_doc(387, docs=24, gpus=2))
    print("unbatched 1 GPU:", cost_per_doc(131.55), " 2 GPU:", cost_per_doc(131.55, gpus=2))
