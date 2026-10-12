"""Tách hợp đồng thành điều khoản và trích thông tin cơ bản của từng điều khoản.

Mô phỏng bước 1 của COMPACT [6] (Phụ lục B.1): mỗi điều khoản được gán loại
(operative / definitional / exception / conditional / heading) và 8 trường
deontic-temporal. Bài gốc dùng GPT-4o cho bước này; ở đây dùng luật (regex)
để nhóm hiểu và kiểm tra được từng quyết định.

Chỉ dùng thư viện chuẩn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- 1. Tách điều khoản -----------------------------------------------------

# Một dòng bắt đầu bằng "1.", "1.2", "3.4.1", "Section 4.2", "ARTICLE IV" là đầu điều khoản.
_HEAD_RE = re.compile(
    r"^\s*(?:(?:Section|SECTION|Article|ARTICLE)\s+)?"
    r"(?P<num>\d+(?:\.\d+)*|[IVXLC]+)\s*[.)]?\s+(?P<body>\S.*)$"
)
_SENT_RE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(\"“])")
_XREF_RE = re.compile(r"\b(?:Section|Sections|Article)\s+(\d+(?:\.\d+)*)", re.I)
_DEF_RE = re.compile(
    r"[\"“](?P<term>[A-Z][A-Za-z0-9 \-]{1,60}?)[\"”]\s+"
    r"(?:means|shall mean|has the meaning|refers to)",
)
_INLINE_DEF_RE = re.compile(r"\(\s*(?:the|a|an)?\s*[\"“](?P<term>[A-Z][A-Za-z0-9 \-]{1,40}?)[\"”]\s*\)")


@dataclass
class Clause:
    cid: str                 # "3.1"
    text: str                # toàn văn điều khoản (không gồm số)
    kind: str = "operative"  # operative | definitional | exception | conditional | heading
    fields: dict = field(default_factory=dict)
    xrefs: list = field(default_factory=list)     # các Section được dẫn chiếu
    defines: list = field(default_factory=list)   # thuật ngữ điều khoản này định nghĩa

    def sentences(self) -> list[str]:
        return split_sentences(self.text)

    @property
    def section(self) -> str:
        return self.cid.split(".")[0]


def split_sentences(text: str) -> list[str]:
    parts = _SENT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_clauses(text: str) -> list[Clause]:
    """Mỗi đoạn bắt đầu bằng số mục là một Clause; đoạn không đánh số được nối vào điều khoản trước."""
    clauses: list[Clause] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _HEAD_RE.match(line)
        if m and _looks_like_number(m.group("num")):
            clauses.append(Clause(cid=m.group("num"), text=m.group("body").strip()))
        elif clauses:
            clauses[-1].text += " " + line
        # dòng trước điều khoản đầu tiên (tiêu đề, phần mở đầu) bị bỏ qua
    for c in clauses:
        c.kind = classify_clause(c)
        c.xrefs = sorted(set(_XREF_RE.findall(c.text)))
        c.defines = [m.group("term") for m in _DEF_RE.finditer(c.text)]
        c.defines += [m.group("term") for m in _INLINE_DEF_RE.finditer(c.text)]
    return clauses


def _looks_like_number(num: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)*", num)) or bool(re.fullmatch(r"[IVXLC]+", num))


# --- 2. Phân loại điều khoản (COMPACT, Phụ lục B.1.3) --------------------------

_MODAL_RE = re.compile(
    r"\b(shall not|may not|must not|shall|must|may|will|agrees? to|is entitled to|is prohibited)\b",
    re.I,
)


def classify_clause(c: Clause) -> str:
    t = c.text
    if len(t.split()) <= 6 and t.isupper():
        return "heading"
    if _DEF_RE.search(t):
        return "definitional"
    head = t[:60]
    if re.match(r"(Notwithstanding|Except|Excluding|Nothing in)", head) or re.search(
        r"\bshall not apply\b|\bshall have no obligation\b", t
    ):
        return "exception"
    if re.match(r"(If|Upon|In the event|Where|Provided that)\b", head):
        return "conditional"
    if _MODAL_RE.search(t):
        return "operative"
    return "other"


# --- 3. Tám trường deontic-temporal (COMPACT, Phụ lục B.1.2) --------------------

_TEMPORAL_RE = re.compile(
    r"\b(within\s+[\w\s()]{1,25}?\s(?:days|months|years|business days)"
    r"|for a period of\s+[\w\s()]{1,20}?\s(?:days|months|years)"
    r"|(?:at least|no later than)\s+[\w\s()]{1,25}?\s(?:days|months|years)"
    r"|during the Term|after (?:delivery|termination|expiration|receipt)[^,.;]*"
    r"|upon (?:termination|expiration)[^,.;]*|thereafter)\b",
    re.I,
)
_CONTEXT_RE = re.compile(
    r"\b(provided that[^.;]*|unless[^.;]*|except (?:that|as)[^.;]*|if [^,.;]*|upon (?:reasonable )?request|"
    r"in accordance with[^.;]*|subject to[^.;]*|to the extent[^.;]*)",
    re.I,
)
_PARTY_RE = re.compile(
    r"\b(Provider|Client|Receiving Party|Disclosing Party|Supplier|Buyer|Licensor|Licensee|"
    r"Company|Customer|Either party|Neither party|Each party|The parties)\b"
)


def deontic_of(modal: str) -> str:
    m = modal.lower()
    if m in ("shall not", "may not", "must not", "is prohibited"):
        return "prohibition"
    if m in ("may", "is entitled to"):
        return "permission"
    return "obligation"


def extract_fields(c: Clause, known_terms: set[str] | None = None) -> dict:
    """Trích 8 trường bằng luật. Trường không tìm thấy = 'not specified' (giống bài gốc)."""
    t = c.text
    out = {k: "not specified" for k in (
        "Subject", "Deontic", "Action", "Object", "Temporal_Condition",
        "Contextual_Parameters", "contains_defined_terms", "counterparty")}
    m = _MODAL_RE.search(t)
    if m:
        before = t[: m.start()]
        subj = _PARTY_RE.findall(before)
        out["Subject"] = subj[-1] if subj else before.strip().split(",")[-1].strip()[-40:] or "not specified"
        out["Deontic"] = f"{m.group(1)} ({deontic_of(m.group(1))})"
        after = t[m.end():].strip()
        words = after.split()
        if words:
            out["Action"] = words[0].strip(",.;")
            obj = " ".join(words[1:]).split(",")[0].split(";")[0]
            out["Object"] = obj.strip()[:120] or "not specified"
        others = [p for p in _PARTY_RE.findall(after) if p != out["Subject"]]
        if others:
            out["counterparty"] = others[0]
    tm = _TEMPORAL_RE.search(t)
    if tm:
        out["Temporal_Condition"] = tm.group(1).strip()
    cm = _CONTEXT_RE.search(t)
    if cm:
        out["Contextual_Parameters"] = cm.group(1).strip()[:120]
    if known_terms:
        used = [term for term in sorted(known_terms, key=len, reverse=True)
                if re.search(r"\b" + re.escape(term) + r"s?\b", t) and term not in c.defines]
        if used:
            out["contains_defined_terms"] = ", ".join(used)
    return out


def defined_terms(clauses: list[Clause]) -> dict[str, str]:
    """term -> cid của điều khoản định nghĩa nó."""
    table: dict[str, str] = {}
    for c in clauses:
        for term in c.defines:
            table.setdefault(term, c.cid)
    return table


def annotate(clauses: list[Clause]) -> list[Clause]:
    terms = set(defined_terms(clauses))
    for c in clauses:
        c.fields = extract_fields(c, terms)
    return clauses


def render(clauses: list[Clause]) -> str:
    """Ghép lại thành văn bản (dùng sau khi cài lỗi)."""
    return "\n\n".join(f"{c.cid} {c.text}" for c in clauses)
