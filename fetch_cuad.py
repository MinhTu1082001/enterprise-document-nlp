#!/usr/bin/env python3
"""Tải CUAD (CC BY 4.0) và lưu một số hợp đồng thành file .txt để chạy demo.

  python fetch_cuad.py                      # 5 hợp đồng đã kiểm (mặc định, nên dùng)
  python fetch_cuad.py --short --limit 20   # lấy theo độ dài như bản cũ (đa số sẽ không cài được lỗi)
  python fetch_cuad.py --zip duong/dan/data.zip   # khi đã tải tay file data.zip

Nguồn: file data.zip trong repo https://github.com/TheAtticusProject/cuad (khoảng 18 MB),
bên trong có CUADv1.json; mỗi hợp đồng nằm ở trường "context". Repo này không có CUAD_v1.zip,
nên đường dẫn của bản cũ bị lỗi 404.

Vì sao có danh sách VETTED: nhóm đã chạy thử bộ tách điều khoản và cài lỗi trên 175 hợp đồng CUAD
dài 3.000–25.000 ký tự. 99 hợp đồng không cài được lỗi nào (đánh số điều khoản kiểu khác, ít dẫn
chiếu "Section N"), chỉ 14 hợp đồng đạt cả ba điều kiện: ít nhất 10 điều khoản, 8 cạnh đồ thị và
3 lỗi cài được với --seed 7. Năm hợp đồng dưới đây là năm hợp đồng rẻ nhất trong số đó.
"""
import argparse
import io
import json
import os
import re
import urllib.request
import zipfile

URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"

# (tên trong CUAD, số lỗi cài được với --seed 7, số lần gọi LLM của cấu hình graph)
VETTED = [
    ("GAINSCOINC_01_21_2010-EX-10.41-SPONSORSHIP AGREEMENT", 3, 6),
    ("HOLIDAYRVSUPERSTORESINC_04_15_2002-EX-10.13-ENDORSEMENT AGREEMENT", 3, 8),
    ("CHIPMOSTECHNOLOGIESBERMUDALTD_04_18_2016-EX-4.72-Strategic Alliance Agreement", 4, 14),
    ("AzulSa_20170303_F-1A_EX-10.3_9943903_EX-10.3_Maintenance Agreement2", 4, 13),
    ("EmmisCommunicationsCorp_20191125_8-K_EX-10.6_11906433_EX-10.6_Marketing Agreement", 5, 19),
]


def safe_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", title).strip("_")[:80] + ".txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/cuad")
    ap.add_argument("--zip", default="", help="đường dẫn data.zip đã tải tay")
    ap.add_argument("--short", action="store_true", help="lấy theo độ dài thay vì danh sách đã kiểm")
    ap.add_argument("--min-chars", type=int, default=3000)
    ap.add_argument("--max-chars", type=int, default=15000)
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()

    if a.zip:
        data = open(a.zip, "rb").read()
    else:
        print("Đang tải", URL, "(khoảng 18 MB)")
        data = urllib.request.urlopen(URL, timeout=600).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        cuad = json.loads(z.read("CUADv1.json"))
    contracts = {d["title"]: d["paragraphs"][0]["context"] for d in cuad["data"]}

    if a.short:
        picked = [t for t, txt in sorted(contracts.items())
                  if a.min_chars <= len(txt) <= a.max_chars and txt.count("\n") > 20][: a.limit]
    else:
        picked = [t for t, _, _ in VETTED if t in contracts]

    os.makedirs(a.out, exist_ok=True)
    for t in picked:
        with open(os.path.join(a.out, safe_name(t)), "w", encoding="utf-8") as f:
            f.write(contracts[t])
    print(f"Đã lưu {len(picked)} hợp đồng vào {a.out}")


if __name__ == "__main__":
    main()
