"""Cài lỗi vào hợp đồng theo 5 loại "in-text" của CLAUSE [1], mục 2.

Bài gốc dùng Gemini 2.0 Flash với prompt đóng vai để sinh lỗi, rồi Gemini 2.5
lọc YES/NO. Ở đây mỗi loại lỗi là một hàm luật, để nhãn chuẩn (span + lời giải
thích + điều khoản bị mâu thuẫn) chắc chắn đúng và nhóm giải thích được.

Mọi lỗi đều được chọn sao cho mâu thuẫn nằm GIỮA hai điều khoản có cạnh trong
đồ thị (DEFINES / EXCEPTIONS / DEPENDS_ON). Đó là giả thuyết demo muốn thử:
bộ phát hiện có ngữ cảnh đồ thị sẽ bắt được các lỗi này tốt hơn.
"""
from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass, asdict

from .clauses import Clause, split_sentences, defined_terms
from .graph import ClauseGraph, build_graph

KINDS = ("inconsistency", "misaligned_terminology", "omission", "structural_flaw", "ambiguity")


@dataclass
class Perturbation:
    kind: str
    cid: str               # điều khoản bị sửa
    original: str          # câu trước khi sửa
    changed: str           # câu sau khi sửa (= nhãn chuẩn, span phải tìm)
    explanation: str
    contradicted: str      # điều khoản bị mâu thuẫn

    @property
    def gt_span(self) -> str:
        return self.changed

    def to_dict(self) -> dict:
        return asdict(self)


_NUM_WORDS = {1: "one", 2: "two", 3: "three", 5: "five", 6: "six", 10: "ten", 12: "twelve", 15: "fifteen",
              30: "thirty", 45: "forty-five", 60: "sixty", 90: "ninety"}
_DAYS_RE = re.compile(r"\b(\w+(?:-\w+)?)\s*\((\d+)\)\s*(business days|days|months|years)\b", re.I)
_QUALIFIER_RE = re.compile(
    r"(,?\s*(?:provided,? (?:however,? )?that|except (?:that|as)|unless|to the extent|subject to)\b[^.;]*)", re.I)
_SYNONYMS = {
    "Confidential Information": "Proprietary Data",
    "Deliverables": "Work Product",
    "Fees": "Charges",
    "Services": "Work",
    "Statement of Work": "Project Order",
    "Affiliate": "Related Company",
    "Term": "Contract Period",
    "Provider Materials": "Background Materials",
}


def _replace_sentence(c: Clause, old: str, new: str) -> None:
    assert old in c.text, (old, c.text)
    c.text = c.text.replace(old, new, 1)


def _linked(g: ClauseGraph, cid: str, strong_only: bool = False) -> list[str]:
    """Điều khoản có cạnh với cid. Ưu tiên cạnh DEPENDS_ON / EXCEPTIONS (quan hệ nghĩa vụ),
    cạnh DEFINES chỉ dùng khi không còn gì khác."""
    strong = [e.dst if e.src == cid else e.src for e in g.out[cid] + g.inc[cid] if e.kind != "DEFINES"]
    if strong or strong_only:
        return strong
    return [e.dst if e.src == cid else e.src for e in g.out[cid] + g.inc[cid]]


# --- 1. Inconsistency: hai thời hạn khác nhau cho cùng một nghĩa vụ ----------------

def inject_inconsistency(clauses, g, rng, used) -> Perturbation | None:
    cands = []
    for c in clauses:
        if c.cid in used or c.kind == "heading":
            continue
        m = _DAYS_RE.search(c.text)
        if not m:
            continue
        # chọn điều khoản B có quan hệ nghĩa vụ với A để chèn câu mâu thuẫn;
        # không có thì lấy điều khoản cùng mục (mâu thuẫn nội bộ một mục)
        partners = [p for p in _linked(g, c.cid, strong_only=True) if p not in used and g.clauses[p].kind != "heading"]
        if not partners:
            partners = [x.cid for x in clauses if x.section == c.section and x.cid != c.cid
                        and x.kind not in ("heading", "definitional") and x.cid not in used]
        if partners:
            cands.append((c, m, partners))
    if not cands:
        return None
    a, m, partners = rng.choice(cands)
    b = g.clauses[rng.choice(partners)]
    n = int(m.group(2))
    unit = m.group(3).lower()
    plausible = {"years": (1, 2, 3, 5), "months": (3, 6, 12), "days": (10, 15, 30, 45, 60, 90), "business days": (5, 10, 15)}
    choices = [k for k in plausible.get(unit, tuple(_NUM_WORDS)) if k != n and k in _NUM_WORDS]
    new_n = rng.choice(choices)
    sent = (f"For the avoidance of doubt, the period of {m.group(1)} ({n}) {unit} referred to in "
            f"Section {a.cid} shall be {_NUM_WORDS[new_n]} ({new_n}) {unit}.")
    original = b.text
    b.text = b.text.rstrip() + " " + sent
    used.update({a.cid, b.cid})
    return Perturbation(
        kind="inconsistency", cid=b.cid, original="", changed=sent,
        explanation=f"Section {b.cid} nêu thời hạn {new_n} {unit} cho nghĩa vụ ở Section {a.cid}, "
                    f"trong khi Section {a.cid} quy định {n} {unit}.",
        contradicted=a.cid)


# --- 2. Misaligned terminology: dùng từ khác cho thuật ngữ đã định nghĩa ------------

def inject_misaligned_terminology(clauses, g, rng, used) -> Perturbation | None:
    terms = defined_terms(clauses)
    cands = []
    for term, def_cid in terms.items():
        if term not in _SYNONYMS:
            continue
        pat = re.compile(r"\b" + re.escape(term) + r"\b")
        for e in g.out[def_cid]:
            if e.kind != "DEFINES" or e.dst in used:
                continue
            c = g.clauses[e.dst]
            for s in split_sentences(c.text):
                if pat.search(s):
                    cands.append((term, def_cid, c, s))
    if not cands:
        return None
    term, def_cid, c, s = rng.choice(cands)
    new_s = re.sub(r"\b" + re.escape(term) + r"\b", _SYNONYMS[term], s, count=1)
    _replace_sentence(c, s, new_s)
    used.update({c.cid, def_cid})
    return Perturbation(
        kind="misaligned_terminology", cid=c.cid, original=s, changed=new_s,
        explanation=f'Section {c.cid} dùng "{_SYNONYMS[term]}", không phải thuật ngữ "{term}" '
                    f"đã định nghĩa ở Section {def_cid}; không rõ hai khái niệm có trùng nhau không.",
        contradicted=def_cid)


# --- 3. Omission: bỏ điều kiện/ngoại lệ mà điều khoản khác dựa vào -----------------

def inject_omission(clauses, g, rng, used) -> Perturbation | None:
    cands = []
    for c in clauses:
        if c.cid in used or c.kind == "heading":
            continue
        partners = [p for p in _linked(g, c.cid, strong_only=True) if g.clauses[p].kind != "heading"]
        if not partners:
            continue  # chỉ bỏ điều kiện ở điều khoản mà điều khoản khác dựa vào
        for s in split_sentences(c.text):
            m = _QUALIFIER_RE.search(s)
            if m and len(s) - len(m.group(1)) > 40:
                cands.append((c, s, m, partners))
    if not cands:
        return None
    c, s, m, partners = rng.choice(cands)
    new_s = (s[: m.start(1)] + s[m.end(1):]).replace(" ,", ",").strip()
    if not new_s.endswith("."):
        new_s = new_s.rstrip(",;") + "."
    _replace_sentence(c, s, new_s)
    used.add(c.cid)
    return Perturbation(
        kind="omission", cid=c.cid, original=s, changed=new_s,
        explanation=f"Section {c.cid} đã mất điều kiện \"{m.group(1).strip(', ')}\"; "
                    f"nghĩa vụ trở thành tuyệt đối và không còn khớp với Section {partners[0]}.",
        contradicted=partners[0])


# --- 4. Structural flaw: dẫn chiếu sai mục ------------------------------------------

def inject_structural_flaw(clauses, g, rng, used) -> Perturbation | None:
    cands = []
    for c in clauses:
        if c.cid in used or c.kind == "heading":
            continue
        for s in split_sentences(c.text):
            for m in re.finditer(r"\bSection (\d+(?:\.\d+)*)\b", s):
                if m.group(1) in g.clauses:
                    cands.append((c, s, m))
    if not cands:
        return None
    c, s, m = rng.choice(cands)
    target = m.group(1)
    others = [cid for cid in g.order if "." in cid and cid.split(".")[0] != target.split(".")[0]
              and g.clauses[cid].kind != "heading"]
    if others and rng.random() < 0.5:   # hợp đồng không có mục con khác thì dùng nhánh "mục không tồn tại"
        wrong = rng.choice(others)
        why = f"Section {wrong} nói về việc khác"
    else:
        tops = [int(x.split(".")[0]) for x in g.order if x.split(".")[0].isdigit()]
        wrong = f"{max(tops, default=0) + 2}.{rng.randint(1, 4)}"
        why = f"Section {wrong} không tồn tại"
    new_s = s[: m.start()] + f"Section {wrong}" + s[m.end():]
    _replace_sentence(c, s, new_s)
    used.add(c.cid)
    return Perturbation(
        kind="structural_flaw", cid=c.cid, original=s, changed=new_s,
        explanation=f"Section {c.cid} dẫn chiếu Section {wrong} ({why}) thay vì Section {target}.",
        contradicted=target)


# --- 5. Ambiguity: biến nghĩa vụ cứng thành "cố gắng hợp lý" -------------------------

def inject_ambiguity(clauses, g, rng, used) -> Perturbation | None:
    cands = []
    for c in clauses:
        if c.cid in used or c.kind != "operative":
            continue
        dependents = [e.src for e in g.inc[c.cid] if e.kind in ("DEPENDS_ON", "EXCEPTIONS")]
        if not dependents:
            continue  # chỉ cài vào điều khoản mà điều khoản khác dựa vào
        for s in split_sentences(c.text):
            if re.search(r"\bshall (?!not\b)[a-z]+", s):
                cands.append((c, s, dependents))
    if not cands:
        return None
    c, s, dependents = rng.choice(cands)
    new_s = re.sub(r"\bshall (?!not\b)", "shall use commercially reasonable efforts to ", s, count=1)
    _replace_sentence(c, s, new_s)
    used.add(c.cid)
    return Perturbation(
        kind="ambiguity", cid=c.cid, original=s, changed=new_s,
        explanation=f"Section {c.cid} đổi \"shall\" thành \"shall use commercially reasonable efforts to\", "
                    f"nghĩa vụ không còn bắt buộc, trong khi Section {dependents[0]} dựa vào nó như một nghĩa vụ cứng.",
        contradicted=dependents[0])


INJECTORS = {
    "inconsistency": inject_inconsistency,
    "misaligned_terminology": inject_misaligned_terminology,
    "omission": inject_omission,
    "structural_flaw": inject_structural_flaw,
    "ambiguity": inject_ambiguity,
}


def inject(clauses: list[Clause], kinds=KINDS, n_per_kind: int = 1, seed: int = 0):
    """Trả về (bản sao điều khoản đã cài lỗi, danh sách lỗi). Đồ thị được dựng từ bản gốc."""
    rng = random.Random(seed)
    work = copy.deepcopy(clauses)
    g = build_graph(work)
    used: set[str] = set()
    perts: list[Perturbation] = []
    for kind in kinds:
        for _ in range(n_per_kind):
            p = INJECTORS[kind](work, g, rng, used)
            if p:
                perts.append(p)
    return work, perts
