"""Ba bộ phát hiện lỗi để so sánh (kế hoạch thí nghiệm ở mục 6.1 báo cáo):

  C1  rule_detector     chỉ dùng luật + đồ thị, không gọi LLM
  C2  llm_full_document LLM đọc cả hợp đồng, prompt phỏng theo Eval_3 L1/L2 của CLAUSE [1]
  C3  llm_with_graph    LLM đọc từng điều khoản kèm láng giềng trên đồ thị (COMPACT [6])

LLM được gọi qua HTTP chuẩn OpenAI (/chat/completions) bằng urllib, nên dùng
được với Groq, OpenRouter, Together, Gemini (chế độ tương thích), hay Ollama
chạy máy. Không cần SDK.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict

from .clauses import Clause, split_sentences, defined_terms
from .graph import ClauseGraph

CATEGORY_DEFINITIONS = """\
Ambiguities: language so vague or open to multiple reasonable interpretations that different sections can be read in incompatible ways.
Inconsistencies: conflicting deadlines, obligations or penalties between different sections of the same document.
Misaligned Terminology: different or undefined terms used for the same concept, or a defined term replaced by another phrase, creating conflicting obligations.
Omissions: a required term, condition, definition or disclosure is missing although it is referenced or relied on elsewhere in the contract.
Structural Flaws: the placement or cross-referencing of clauses undermines coherence, such as a reference to the wrong or a non-existent section."""


@dataclass
class Prediction:
    span: str
    explanation: str
    kind: str = ""          # loại lỗi mô hình đoán (tùy chọn)
    source: str = ""        # bộ phát hiện nào, điều khoản nào

    def to_dict(self) -> dict:
        return asdict(self)


# --- C1: luật ----------------------------------------------------------------------

def rule_detector(clauses: list[Clause], g: ClauseGraph) -> list[Prediction]:
    preds: list[Prediction] = []
    terms = defined_terms(clauses)
    known = {cid for cid in g.clauses}
    # (a) dẫn chiếu tới mục không tồn tại -> structural_flaw
    for c in clauses:
        for s in split_sentences(c.text):
            for m in re.finditer(r"\bSection (\d+(?:\.\d+)*)\b", s):
                ref = m.group(1)
                exists = ref in known or any(k.startswith(ref + ".") for k in known)
                if not exists:
                    preds.append(Prediction(s, f"Section {ref} không tồn tại.", "structural_flaw", f"rule:{c.cid}"))
    # (b) thời hạn khác nhau cho cùng một Section -> inconsistency
    period_re = re.compile(r"period[^.;]*?Section (\d+(?:\.\d+)*)[^.;]*?\((\d+)\)\s*(business days|days|months|years)", re.I)
    for c in clauses:
        for s in split_sentences(c.text):
            for m in period_re.finditer(s):
                tgt = g.clauses.get(m.group(1))
                if tgt:
                    nums = re.findall(r"\((\d+)\)\s*" + re.escape(m.group(3)), tgt.text, re.I)
                    if nums and m.group(2) not in nums:
                        preds.append(Prediction(s, f"Thời hạn {m.group(2)} {m.group(3)} khác với Section {m.group(1)} ({nums[0]}).",
                                                "inconsistency", f"rule:{c.cid}"))
    # (c) cụm viết hoa giữa câu, xuất hiện đúng một lần và không được định nghĩa -> misaligned_terminology
    #     (thuật ngữ thật được dùng lặp lại; một cụm viết hoa lạ, chỉ gặp một lần, là dấu hiệu lệch thuật ngữ)
    doc = " ".join(c.text for c in clauses)
    cap_re = re.compile(r"(?<![.;:]\s)(?<!^)\b((?:[A-Z][a-z]{2,}\s){0,2}[A-Z][a-z]{3,})\b")
    stop = {"Agreement", "Section", "Sections", "Article", "Exhibit", "Schedule", "Provider", "Client", "Party", "Parties"}
    for c in clauses:
        for s in split_sentences(c.text):
            for m in cap_re.finditer(s):
                phrase = m.group(1)
                if phrase in stop or phrase.split()[-1] in stop or phrase in terms:
                    continue
                if any(phrase in t or t in phrase for t in terms):
                    continue
                if len(re.findall(r"\b" + re.escape(phrase) + r"\b", doc)) == 1:
                    preds.append(Prediction(s, f'"{phrase}" chỉ xuất hiện một lần và không được định nghĩa.',
                                            "misaligned_terminology", f"rule:{c.cid}"))
                    break
    # (d) nghĩa vụ bị làm mềm ("reasonable efforts") ở điều khoản có thời hạn hoặc được điều khoản khác dựa vào -> ambiguity
    for c in clauses:
        relied_on = any(e.kind in ("DEPENDS_ON", "EXCEPTIONS") for e in g.inc[c.cid])
        for s in split_sentences(c.text):
            hedged = re.search(r"(commercially )?reasonable efforts to", s)
            if hedged and (relied_on or re.search(r"\(\d+\)\s*(business days|days|months|years)", s)):
                preds.append(Prediction(s, "Nghĩa vụ đi kèm 'reasonable efforts' nên không còn bắt buộc.", "ambiguity", f"rule:{c.cid}"))
    # Omission không có dấu hiệu bề mặt: luật không bắt được (đây là kết quả đáng ghi trong báo cáo).
    return _dedupe(preds)


def _dedupe(preds: list[Prediction]) -> list[Prediction]:
    seen, out = set(), []
    for p in preds:
        key = p.span.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


# --- LLM client ---------------------------------------------------------------------

class LLMClient:
    """Gọi endpoint tương thích OpenAI (/chat/completions) bằng urllib.

    Biến môi trường:
      LLM_BASE_URL          mặc định Groq: https://api.groq.com/openai/v1
      LLM_API_KEY           khóa API (Ollama chạy máy thì điền gì cũng được)
      LLM_MODEL             mặc định openai/gpt-oss-120b. Groq đã ngừng llama-3.3-70b-versatile
                            và llama-3.1-8b-instant cho gói free/developer từ 16/8/2026.
      LLM_TEMPERATURE       mặc định 0, để chạy lại cho cùng kết quả
      LLM_MAX_TOKENS        mặc định 4096
      LLM_REASONING_EFFORT  low / medium / high, chỉ gửi khi có đặt (dùng cho gpt-oss)
      LLM_CACHE             file cache, mặc định .llm_cache.json; đặt rỗng để tắt
      LLM_OFFLINE=1         chỉ đọc cache, không gọi mạng (dùng khi thuyết trình)

    Cache theo nội dung prompt: chạy lại cùng prompt thì không tốn token, không cần mạng.
    Gặp 429 (vượt hạn mức) hoặc lỗi 5xx thì chờ theo header retry-after rồi thử lại.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None,
                 temperature: float | None = None, max_tokens: int | None = None,
                 cache_path: str | None = None, max_retries: int = 6):
        env = os.environ.get
        self.base_url = (base_url or env("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.api_key = api_key or env("LLM_API_KEY", "")
        self.model = model or env("LLM_MODEL", "openai/gpt-oss-120b")
        self.temperature = float(env("LLM_TEMPERATURE", "0")) if temperature is None else temperature
        self.max_tokens = int(env("LLM_MAX_TOKENS", "4096")) if max_tokens is None else max_tokens
        self.reasoning_effort = env("LLM_REASONING_EFFORT", "")
        self.cache_path = env("LLM_CACHE", ".llm_cache.json") if cache_path is None else cache_path
        self.offline = env("LLM_OFFLINE", "") == "1"
        self.max_retries = max_retries
        self.calls = 0            # số lần phương pháp gọi LLM (kể cả lấy từ cache): đây là chi phí của phương pháp
        self.network_calls = 0    # số lần gọi mạng thật
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self._cache: dict = {}
        if self.cache_path and os.path.exists(self.cache_path):
            with open(self.cache_path, encoding="utf-8") as f:
                self._cache = json.load(f)

    def _key(self, system: str, user: str) -> str:
        raw = json.dumps([self.base_url, self.model, self.temperature, self.reasoning_effort, system, user],
                         ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _add_usage(self, usage: dict) -> None:
        for k in self.usage:
            self.usage[k] += int(usage.get(k) or 0)

    def chat(self, system: str, user: str) -> str:
        key = self._key(system, user)
        self.calls += 1
        if key in self._cache:
            hit = self._cache[key]
            self._add_usage(hit.get("usage", {}))
            return hit["text"]
        if self.offline:
            raise RuntimeError("LLM_OFFLINE=1 nhưng prompt này chưa có trong cache: chạy một lần có mạng trước.")
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        body = json.dumps(payload).encode()
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                self.base_url + "/chat/completions", data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries:
                    try:
                        wait = float(e.headers.get("retry-after") or 0)
                    except ValueError:
                        wait = 0.0
                    time.sleep(min(max(wait, 5 * 2 ** attempt), 120))
                    continue
                raise
        self.network_calls += 1
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
        if not text.strip() and choice.get("finish_reason") == "length":
            raise RuntimeError("Mô hình hết token trước khi trả lời: tăng LLM_MAX_TOKENS hoặc đặt LLM_REASONING_EFFORT=low.")
        usage = data.get("usage") or {}
        self._add_usage(usage)
        self._cache[key] = {"text": text, "usage": {k: usage.get(k, 0) for k in self.usage}}
        if self.cache_path:
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
        return text


class MockClient:
    """Chạy offline: trả lời bằng bộ luật để thử toàn bộ pipeline. Không thay cho LLM thật."""

    def __init__(self, clauses: list[Clause], g: ClauseGraph):
        self.preds = rule_detector(clauses, g)
        self.calls = 0

    def chat(self, system: str, user: str) -> str:
        self.calls += 1
        items = [p.to_dict() for p in self.preds if p.span in user]
        return json.dumps([{"text": p["span"], "explanation": p["explanation"]} for p in items])


# --- prompt (phỏng theo CLAUSE, Phụ lục B, Eval_3 L1 / L2 in-text) ------------------

SYSTEM = "You are a senior U.S. attorney and contract analyst. You answer only with valid JSON."

ONE_SHOT_EXAMPLE = """
Example of an in-text discrepancy and the expected entry:
Section 3.1 says "Client shall pay the Fees within thirty (30) days after receipt of an invoice" while Section 3.3 says "the period referred to in Section 3.1 shall be ten (10) days".
Expected JSON entry:
[{"text": "the period referred to in Section 3.1 shall be ten (10) days.", "explanation": "Conflicts with the thirty-day payment period in Section 3.1."}]
"""


def _task_prompt(document: str, one_shot: bool) -> str:
    return (
        "Task: read the legal document below in full and detect every in-text discrepancy: a statement, clause, "
        "term or definition that conflicts with, negates or is irreconcilable with another part of the same document.\n\n"
        f"Discrepancy categories:\n{CATEGORY_DEFINITIONS}\n"
        + (ONE_SHOT_EXAMPLE if one_shot else "")
        + "\nOutput format: return exactly one JSON array, no markdown, no commentary. Each object has "
        '"text" (the exact sentence(s) copied verbatim from the document that contain the issue) and '
        '"explanation" (what it contradicts and why). If no discrepancy exists, return [].\n\n'
        f'Document: """\n{document}\n"""'
    )


def _parse(raw: str, source: str) -> list[Prediction]:
    raw = raw.strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items:
        if isinstance(it, dict) and it.get("text"):
            out.append(Prediction(str(it["text"]), str(it.get("explanation", "")), str(it.get("category", "")), source))
    return out


# --- C2: LLM đọc cả hợp đồng ----------------------------------------------------------

def llm_full_document(document: str, client, one_shot: bool = False) -> list[Prediction]:
    raw = client.chat(SYSTEM, _task_prompt(document, one_shot))
    return _dedupe(_parse(raw, "full_doc" + ("_L2" if one_shot else "_L1")))


# --- C3: LLM đọc từng điều khoản kèm láng giềng đồ thị ------------------------------

def llm_with_graph(clauses: list[Clause], g: ClauseGraph, client, hops: int = 1) -> list[Prediction]:
    preds: list[Prediction] = []
    for c in clauses:
        if c.kind == "heading":
            continue
        ctx = g.context_for(c.cid, hops)
        if not ctx:
            continue  # điều khoản không có láng giềng: bỏ qua (ghi nhận trong báo cáo là hạn chế)
        user = (
            "Task: decide whether the TARGET clause below contains an in-text discrepancy with any of the RELATED "
            "clauses. Related clauses are linked to the target by edges of a clause graph: DEFINES (a term used in "
            "the target is defined there), EXCEPTIONS (one limits the other), DEPENDS_ON (one refers to the other).\n\n"
            f"Discrepancy categories:\n{CATEGORY_DEFINITIONS}\n\n"
            f"TARGET [{c.cid}]:\n{c.text}\n\nRELATED:\n{ctx}\n\n"
            "Output: exactly one JSON array, no markdown. Each object has \"text\" (the exact sentence copied verbatim "
            "from the TARGET clause that contains the issue) and \"explanation\". Return [] if the target is consistent."
        )
        raw = client.chat(SYSTEM, user)
        for p in _parse(raw, f"graph:{c.cid}"):
            if p.span.strip() and p.span.strip()[:40].lower() in c.text.lower():
                preds.append(p)
    return _dedupe(preds)
