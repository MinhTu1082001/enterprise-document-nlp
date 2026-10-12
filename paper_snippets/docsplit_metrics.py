"""DocSplit [4], muc 5: diem clustering, ordering, packet. Chi dung thu vien chuan.

truth[i] / pred[i]   : tai lieu (nhom) cua trang i theo dap an / theo mo hinh
true_pos[i] / pred_pos[i] : vi tri cua trang i trong tai lieu cua no
"""
from collections import Counter
from itertools import combinations
from math import log


def rand_index(truth, pred):
    """Ty le cap trang ma hai ben 'dong y' (cung nhom / khac nhom)."""
    pairs = list(combinations(range(len(truth)), 2))
    if not pairs:
        return 1.0
    agree = sum((truth[i] == truth[j]) == (pred[i] == pred[j]) for i, j in pairs)
    return agree / len(pairs)


def _entropy(labels):
    n = len(labels)
    return -sum(c / n * log(c / n) for c in Counter(labels).values())


def _cond_entropy(a, b):
    """H(a | b): biet b roi thi a con 'lon xon' bao nhieu."""
    n = len(a)
    return sum(nb / n * _entropy([x for x, y in zip(a, b) if y == bv]) for bv, nb in Counter(b).items())


def v_measure(truth, pred):
    ht, hp = _entropy(truth), _entropy(pred)
    h = 1.0 if ht == 0 else 1 - _cond_entropy(truth, pred) / ht   # homogeneity: moi cum chi chua 1 tai lieu
    c = 1.0 if hp == 0 else 1 - _cond_entropy(pred, truth) / hp   # completeness: moi tai lieu nam tron 1 cum
    return 0.0 if h + c == 0 else 2 * h * c / (h + c)


def kendall_tau(true_order, pred_order):
    """(cap cung chieu - cap nguoc chieu) / tong so cap, trong [-1, 1]."""
    pairs = list(combinations(range(len(true_order)), 2))
    if not pairs:
        return 1.0
    s = 0
    for i, j in pairs:
        d = (true_order[i] - true_order[j]) * (pred_order[i] - pred_order[j])
        s += (d > 0) - (d < 0)
    return s / len(pairs)


def packet_score(truth, pred, true_pos, pred_pos, w=0.5, alpha=0.5):
    clustering = w * v_measure(truth, pred) + (1 - w) * rand_index(truth, pred)
    taus = []
    for doc in sorted(set(truth)):
        idx = [i for i, t in enumerate(truth) if t == doc]
        if len(idx) > 1:                       # bai goc bo tai lieu chi co 1 trang
            taus.append(kendall_tau([true_pos[i] for i in idx], [pred_pos[i] for i in idx]))
    ordering = sum(taus) / len(taus) if taus else 1.0
    return {"clustering": round(clustering, 4), "ordering": round(ordering, 4),
            "packet": round(alpha * clustering + (1 - alpha) * ordering, 4)}


if __name__ == "__main__":
    truth = ["A", "A", "A", "B", "B"]          # hoa don A: trang 1-3, hoa don B: trang 4-5
    pos = [1, 2, 3, 1, 2]
    # Truong hop 1: mo hinh gop ca 5 trang thanh 1 tai lieu, thu tu giu nguyen
    print("gop nham:", rand_index(truth, ["X"] * 5), v_measure(truth, ["X"] * 5),
          packet_score(truth, ["X"] * 5, pos, [1, 2, 3, 4, 5]))
    # Truong hop 2: tach dung, nhung trong A dao trang 2 va 3
    print("dao trang:", packet_score(truth, ["A", "A", "A", "B", "B"], pos, [1, 3, 2, 1, 2]))
