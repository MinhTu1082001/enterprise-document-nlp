"""ClauseMiner [8]: prompt one-shot va bo doc ket qua trong code chinh thuc (app.py),
so voi mot cach doc ket qua chac chan hon (JSON + kiem tra trich dan co trong van ban)."""
import json
import re

ONE_SHOT_PROMPT = """The following is an example of a contract clause extraction task. ...
Example:
Input Contract Text:
{example_in}
Expected Output:
{example_out}
Your task:
Given the following contract text:
{contract}
Please extract the clauses and their content in the format below:
- Document Type: <document_type>
- Clause 1: <Clause Name> - <Clause Content>
...
But the clause description should be taken only from the document."""


def parse_like_app_py(message):
    """Chep lai logic tach chuoi cua app.py (dong 131-143)."""
    document_type, clauses = "", {}
    if "Document Type:" in message:
        start = message.find("Document Type:") + len("Document Type:")
        document_type = message[start:message.find("\n", start)].strip()
    for line in message.split("- Clause"):
        if line.strip():
            parts = line.split(":", 1)
            if len(parts) == 2:
                clauses[parts[0].strip()] = parts[1].strip()
    return document_type, clauses


JSON_PROMPT_TAIL = """Return only JSON: {"document_type": str,
 "clauses": [{"name": str, "text": str}]}. "text" must be copied verbatim from the contract."""


def parse_json_grounded(message, contract):
    """Doc JSON; giu dieu khoan nao ma 'text' that su nam trong hop dong (chong bia)."""
    m = re.search(r"\{.*\}", message, re.S)
    if not m:
        return None, [], ["khong co JSON"]
    data = json.loads(m.group(0))
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    doc = norm(contract)
    kept, dropped = [], []
    for c in data.get("clauses", []):
        (kept if norm(c.get("text", "")) in doc else dropped).append(c)
    return data.get("document_type"), kept, [f"bi loai: {c['name']}" for c in dropped]


if __name__ == "__main__":
    reply = ("- Document Type: Service Agreement\n"
             "- Clause 1: Confidentiality - Each party shall keep the terms confidential.\n"
             "- Clause 2: Payment - Fees are due within 30 days: no set-off.\n")
    print(parse_like_app_py(reply))
    contract = "Each party shall keep the terms confidential. Fees are due within 30 days."
    reply_json = ('{"document_type": "Service Agreement", "clauses": ['
                  '{"name": "Confidentiality", "text": "Each party shall keep the terms confidential."},'
                  '{"name": "Payment", "text": "Fees are due within 45 days."}]}')
    print(parse_json_grounded(reply_json, contract))
