"""Chấm vị trí theo location_alignment của CLAUSE [1], mục 5.

Định nghĩa trong bài:
  - f_s(d): tách span d thành TẬP câu đã chuẩn hóa (chữ thường, bỏ khoảng trắng thừa).
  - Đồ thị vô hướng: đỉnh = mọi span chuẩn (GT) và span dự đoán (P);
    cạnh (g, p) tồn tại khi f_s(g) ∩ f_s(p) ≠ ∅. Chỉ nối GT với P, không nối GT–GT hay P–P.
  - Thành phần liên thông có ít nhất 1 GT và 1 P  -> một True Positive (một "match group").
  - GT không thuộc match group nào -> False Negative (bài gọi là Miss).
  - P không thuộc match group nào  -> False Positive (bài gọi là Extra).

Bài gốc dùng networkx; ở đây dùng union-find vài chục dòng.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .clauses import split_sentences

_WS = re.compile(r"\s+")


def norm_sentences(span: str) -> set[str]:
    out = set()
    for s in split_sentences(span.replace("\n", " ")):
        s = _WS.sub(" ", s).strip().lower()
        s = s.replace("“", '"').replace("”", '"').replace("’", "'").rstrip(".;:, ")
        if s:
            out.add(s)
    return out


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


@dataclass
class Alignment:
    tp: int
    fn: int
    fp: int
    matched: list[tuple[list[int], list[int]]] = field(default_factory=list)  # (gt idx, pred idx) mỗi nhóm
    missed: list[int] = field(default_factory=list)
    extra: list[int] = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def miss_rate(self) -> float:
        n = self.tp + self.fn
        return self.fn / n if n else 0.0

    @property
    def extra_rate(self) -> float:
        n = self.tp + self.fp
        return self.fp / n if n else 0.0


def align(gold: list[str], pred: list[str]) -> Alignment:
    gsets = [norm_sentences(g) for g in gold]
    psets = [norm_sentences(p) for p in pred]
    n = len(gold) + len(pred)
    uf = UnionFind(n)
    for i, gs in enumerate(gsets):
        for j, ps in enumerate(psets):
            if gs & ps:                      # giao nhau khác rỗng -> nối
                uf.union(i, len(gold) + j)
    groups: dict[int, tuple[list[int], list[int]]] = {}
    for i in range(len(gold)):
        groups.setdefault(uf.find(i), ([], []))[0].append(i)
    for j in range(len(pred)):
        groups.setdefault(uf.find(len(gold) + j), ([], []))[1].append(j)
    res = Alignment(0, 0, 0)
    for gs, ps in groups.values():
        if gs and ps:
            res.tp += 1
            res.matched.append((gs, ps))
        elif gs:
            res.fn += len(gs)
            res.missed += gs
        else:
            res.fp += len(ps)
            res.extra += ps
    return res


def per_kind(gold_items: list[dict], pred: list[str]) -> dict[str, Alignment]:
    """Chấm riêng từng loại lỗi: gold_items = [{"kind":..., "span":...}]."""
    out = {}
    for kind in sorted({g["kind"] for g in gold_items}):
        spans = [g["span"] for g in gold_items if g["kind"] == kind]
        out[kind] = align(spans, pred)
    return out
