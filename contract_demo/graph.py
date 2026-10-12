"""Đồ thị điều khoản (clause graph) theo COMPACT [6], mục 3.1.3 và Phụ lục B.3.

Bài gốc có 6 loại cạnh: DEFINES, COMPLEMENTS, EXCEPTIONS, DEPENDS_ON, CONFLICTS,
SEQUENCE, do GPT-4o suy ra. Ở đây chỉ dựng 3 loại làm được bằng luật:

  DEFINES     điều khoản định nghĩa thuật ngữ T  -> điều khoản dùng T
  EXCEPTIONS  điều khoản ngoại lệ              -> điều khoản bị nó giới hạn
  DEPENDS_ON  điều khoản dẫn chiếu "Section X" -> điều khoản X

Đồ thị là dict kề; tìm láng giềng bằng BFS. Không dùng networkx.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from .clauses import Clause, defined_terms

EDGE_TYPES = ("DEFINES", "EXCEPTIONS", "DEPENDS_ON")


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    evidence: str  # vì sao có cạnh này (để nhóm giải thích khi trình bày)


class ClauseGraph:
    def __init__(self, clauses: list[Clause]):
        self.clauses = {c.cid: c for c in clauses}
        self.order = [c.cid for c in clauses]
        self.edges: list[Edge] = []
        self.out: dict[str, list[Edge]] = {c.cid: [] for c in clauses}
        self.inc: dict[str, list[Edge]] = {c.cid: [] for c in clauses}

    def add(self, src: str, dst: str, kind: str, evidence: str) -> None:
        if src == dst or src not in self.clauses or dst not in self.clauses:
            return
        e = Edge(src, dst, kind, evidence)
        if e in self.edges:
            return
        self.edges.append(e)
        self.out[src].append(e)
        self.inc[dst].append(e)

    def neighbors(self, cid: str, hops: int = 1) -> dict[str, list[Edge]]:
        """BFS trên đồ thị vô hướng; trả về {cid láng giềng: đường cạnh đi tới nó}."""
        seen = {cid: []}
        q = deque([(cid, 0)])
        while q:
            cur, d = q.popleft()
            if d == hops:
                continue
            for e in self.out[cur] + self.inc[cur]:
                nxt = e.dst if e.src == cur else e.src
                if nxt not in seen:
                    seen[nxt] = seen[cur] + [e]
                    q.append((nxt, d + 1))
        seen.pop(cid)
        return seen

    def context_for(self, cid: str, hops: int = 1) -> str:
        """Văn bản ngữ cảnh đưa cho LLM ở cấu hình 3: điều khoản + láng giềng + loại cạnh."""
        lines = []
        for nid, path in sorted(self.neighbors(cid, hops).items(), key=lambda kv: _key(kv[0])):
            rel = " -> ".join(f"{e.src} {e.kind} {e.dst}" for e in path)
            lines.append(f"[{nid}] ({rel})\n{self.clauses[nid].text}")
        return "\n\n".join(lines)

    def to_json(self) -> dict:
        return {
            "nodes": [{"id": cid, "kind": self.clauses[cid].kind} for cid in self.order],
            "edges": [e.__dict__ for e in self.edges],
        }


def _key(cid: str):
    return tuple(int(x) if x.isdigit() else 0 for x in cid.split("."))


def _resolve(ref: str, graph: ClauseGraph) -> list[str]:
    """'Section 4' -> mọi điều khoản 4.x; 'Section 3.1' -> chính nó."""
    if ref in graph.clauses and graph.clauses[ref].kind != "heading":
        return [ref]
    return [cid for cid in graph.order if cid.startswith(ref + ".") and graph.clauses[cid].kind != "heading"]


def build_graph(clauses: list[Clause]) -> ClauseGraph:
    g = ClauseGraph(clauses)
    terms = defined_terms(clauses)

    # DEFINES: từ điều khoản định nghĩa tới mọi điều khoản dùng thuật ngữ (whole word, có số nhiều)
    for term, def_cid in terms.items():
        pat = re.compile(r"\b" + re.escape(term) + r"s?\b")
        for c in clauses:
            if c.cid != def_cid and c.kind != "heading" and pat.search(c.text):
                g.add(def_cid, c.cid, "DEFINES", f'"{term}" được định nghĩa ở {def_cid}')

    for c in clauses:
        if c.kind == "heading":
            continue
        # EXCEPTIONS: bốn mẫu câu ngoại lệ dẫn chiếu rõ mục bị giới hạn
        exc_patterns = (
            r"Notwithstanding[^.;]*?Sections?\s+(\d+(?:\.\d+)*)",            # Notwithstanding Section 4.1, ...
            r"Sections?\s+(\d+(?:\.\d+)*)\s+shall not apply",               # Section 7.1 shall not apply to ...
            r"no obligation under Sections?\s+(\d+(?:\.\d+)*)",               # ... shall have no obligation under Section 8.1 to the extent ...
            r"except as (?:expressly )?set forth in (?:this )?Sections?\s+(\d+(?:\.\d+)*)",
        )
        exc_targets = set()
        for pat in exc_patterns:
            for m in re.finditer(pat, c.text, re.I):
                for dst in _resolve(m.group(1), g):
                    g.add(c.cid, dst, "EXCEPTIONS", m.group(0)[:80])
                    exc_targets.add(m.group(1))
        if c.kind == "exception" and not g.out[c.cid]:
            # ngoại lệ không dẫn chiếu rõ -> giới hạn điều khoản operative đứng ngay trước trong cùng mục
            prev = _previous_operative(c, clauses)
            if prev:
                g.add(c.cid, prev.cid, "EXCEPTIONS", "ngoại lệ không dẫn chiếu; lấy điều khoản đứng trước")
        # DEPENDS_ON: mọi dẫn chiếu còn lại
        for ref in c.xrefs:
            if ref in exc_targets:
                continue
            if ref == c.section and re.search(r"this Section\s+" + re.escape(ref) + r"\b", c.text, re.I):
                continue  # "this Section 4" là tự dẫn chiếu, không phải phụ thuộc
            for dst in _resolve(ref, g):
                if not any(e.dst == dst and e.src == c.cid for e in g.out[c.cid]):
                    g.add(c.cid, dst, "DEPENDS_ON", f"dẫn chiếu Section {ref}")
    return g


def _previous_operative(c: Clause, clauses: list[Clause]) -> Clause | None:
    idx = [x.cid for x in clauses].index(c.cid)
    for prev in reversed(clauses[:idx]):
        if prev.section != c.section:
            return None
        if prev.kind == "operative":
            return prev
    return None
