"""COMPACT [6]: tu kiem du lieu ACE cong bo (train.json, test.json) xem tap test co trung tap train khong.

Lay du lieu:  git clone https://github.com/FujitsuResearch/Fujitsu-Assessing-Compliance-in-Enterprise-Dataset ace
Chay:         python compact_check_split.py ace
Luu y: moi file co dang {"scenarios": [...]}; doan code mau trong README cua repo doc thieu khoa nay.
"""
import json
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "ace")
train = json.loads((root / "train.json").read_text())["scenarios"]
test = json.loads((root / "test.json").read_text())["scenarios"]
print("so mau:", len(train), len(test))
print("nhan train:", Counter(x["gd_tr"] for x in train))
print("nhan test :", Counter(x["gd_tr"] for x in test))

seen_text = {x["scenario_text"].strip() for x in train}
dup = [x for x in test if x["scenario_text"].strip() in seen_text]
print("tinh huong test trung nguyen van voi train:", len(dup), Counter(x["gd_tr"] for x in dup))

clause_set = lambda x: tuple(sorted(v.strip() for v in x["clauses"].values()))
seen_clauses = {clause_set(x) for x in train}
print("bo dieu khoan test da co trong train:", sum(clause_set(x) in seen_clauses for x in test))

same = sum(x["DeepSeek_prediction"] == x["gd_tr"] for x in train)
print("loi giai DeepSeek trung nhan:", same, "/", len(train))
