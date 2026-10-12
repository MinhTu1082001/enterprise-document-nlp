# Demo: trợ lý rà soát hợp đồng — phát hiện lỗi xuyên điều khoản

Demo cho báo cáo "NLP cho tài liệu doanh nghiệp". Mục tiêu: trả lời câu hỏi
**"cho LLM thêm ngữ cảnh từ đồ thị điều khoản thì bắt lỗi xuyên điều khoản tốt hơn không?"**

Chỉ dùng thư viện chuẩn của Python 3.9+. Không cài gì thêm. LLM gọi qua HTTP
chuẩn OpenAI bằng `urllib`.

| Module | Việc | Lấy từ bài | Ai viết |
| --- | --- | --- | --- |
| `contract_demo/clauses.py` | tách điều khoản, phân loại 4 kiểu, trích 8 trường, bắt thuật ngữ định nghĩa và dẫn chiếu | COMPACT [6] §3.1.1, Phụ lục B.1 | |
| `contract_demo/graph.py` | đồ thị DEFINES / EXCEPTIONS / DEPENDS_ON, BFS láng giềng, ngữ cảnh cho LLM | COMPACT [6] §3.1.3, B.3 | |
| `contract_demo/perturb.py` | cài 5 loại lỗi in-text bằng luật, kèm nhãn chuẩn | CLAUSE [1] §2, Phụ lục A.3 | |
| `contract_demo/detect.py` | ba bộ phát hiện: luật / LLM cả văn bản (L1, L2) / LLM + đồ thị | CLAUSE [1] §4 (prompt), COMPACT [6] | |
| `contract_demo/score.py` | location_alignment bằng union-find; P/R/F1, miss, extra | CLAUSE [1] §5 | |
| `contract_demo/report.py` | results.json + report.html (tô màu, vẽ đồ thị SVG) | — | |
| `run_demo.py` | chạy toàn bộ trên một hợp đồng | — | |
| `fetch_cuad.py` | tải CUAD (data.zip trên GitHub), mặc định lấy 5 hợp đồng đã kiểm | — | |
| `summarize.py` | gộp `results.json` của nhiều lần chạy thành một bảng (micro P/R/F1, lần gọi, token) | — | |
| `ace_eval.py` | Case B: chấm zero-shot một mẫu nhỏ của bộ ACE | COMPACT [6] §4, Bảng 6 | |
| `case53.py` | Case C: tình huống 5.3 (Điều 1–4), câu hỏi nối điều khoản + chính sách cấm nêu đơn giá | COMPACT [6], PLawBench [2], Doc-PP [3] | |

## Chạy

```bash
python -m unittest discover -s tests          # 18 test
python run_demo.py --mock --seed 1            # thử đường ống, không gọi LLM
python ace_eval.py --data ace/test.json --mock
python case53.py --mock
```

Gọi LLM thật (mặc định Groq, gói miễn phí). Groq đã ngừng `llama-3.3-70b-versatile` và `llama-3.1-8b-instant`
cho gói free/developer từ 16/8/2026, nên mặc định đổi sang `openai/gpt-oss-120b`.

```bash
export LLM_API_KEY=gsk_...                    # tạo ở console.groq.com
export LLM_REASONING_EFFORT=low               # gpt-oss suy nghĩ ngắn, đỡ token

# Case A · CLAUSE [1] + COMPACT [6]: hợp đồng mẫu + 5 hợp đồng CUAD đã kiểm
python fetch_cuad.py                          # tải data.zip (~18 MB), lưu 5 hợp đồng vào data/cuad
python run_demo.py --contract data/sample_contract.txt --seed 7 --out out/sample
for f in data/cuad/*.txt; do python run_demo.py --contract "$f" --seed 7 --out "out/$(basename "$f" .txt)"; done
python summarize.py out/*/results.json        # bảng tổng cho chương demo

# Case B · COMPACT [6]: 60 mẫu ACE, mô hình nhỏ hơn để dùng hạn mức riêng
git clone https://github.com/FujitsuResearch/Fujitsu-Assessing-Compliance-in-Enterprise-Dataset ace
LLM_MODEL=openai/gpt-oss-20b python ace_eval.py --data ace/test.json --per-label 20

# Case C · tình huống 5.3: PLawBench [2] chấm Q1, Doc-PP [3] cho chính sách
python case53.py                              # rồi hai người chấm tay out/rubric_q1.csv
```

Trên Windows (PowerShell), thay `export` và vòng `for` bằng:

```powershell
$env:LLM_API_KEY = "gsk_..."; $env:LLM_REASONING_EFFORT = "low"
Get-ChildItem data\cuad\*.txt | ForEach-Object { python run_demo.py --contract $_.FullName --seed 7 --out ("out\" + $_.BaseName) }
python summarize.py (Get-ChildItem out\*\results.json).FullName
```

Mọi câu trả lời được lưu vào `.llm_cache.json`. Chạy lại cùng lệnh không tốn token. Khi thuyết trình,
đặt `LLM_OFFLINE=1` để chỉ đọc cache, không cần mạng.

Chạy bằng mô hình trên máy (không cần GPU, nên có 8 GB RAM), qua Ollama:

```bash
ollama pull qwen2.5:3b                        # 1,9 GB; đúng một trong các mô hình COMPACT dùng
LLM_BASE_URL=http://localhost:11434/v1 LLM_API_KEY=ollama LLM_MODEL=qwen2.5:3b \
  python ace_eval.py --data ace/test.json --per-label 5     # đo thời gian 15 mẫu trước rồi mới chạy 60
```

Kết quả: `out/<tên>/results.json`, `report.html` (mở bằng trình duyệt), `perturbed.txt`; `out/ace_results.json`;
`out/case53.json`, `out/rubric_q1.csv`.

## Code minh họa 8 bài báo

Thư mục `paper_snippets/` có một file nhỏ cho mỗi bài (cách chấm, cách tính điểm, prompt, kiểm dữ liệu), chạy độc lập bằng `python <tên file>.py`. Xem `paper_snippets/README.md` để biết file nào đi với bài nào.

## Cấu hình so sánh

| Tên | Cách làm | Số lần gọi LLM / hợp đồng |
| --- | --- | --- |
| `rule` | luật + đồ thị, không LLM: dẫn chiếu rỗng, thời hạn lệch, cụm viết hoa lạ, nghĩa vụ bị làm mềm | 0 |
| `llm` | LLM đọc cả hợp đồng, prompt zero-shot phỏng theo Eval_3 L1 | 1 |
| `llm2` | như trên, có một ví dụ (L2) | 1 |
| `graph` | mỗi điều khoản + láng giềng 1 bước trên đồ thị, kèm loại cạnh | ≈ số điều khoản có cạnh |

`--mock` thay LLM bằng bộ luật để kiểm tra đường ống; kết quả mock không có giá trị thí nghiệm.

## Những gì cố ý làm khác bài gốc

- COMPACT dùng GPT-4o cho cả ba bước (trích thực thể, gom cụm, nối cạnh) và 6 loại cạnh; ở đây dùng luật, bỏ bước gom cụm, chỉ 3 loại cạnh.
- CLAUSE sinh lỗi bằng Gemini và lọc bằng Gemini; ở đây lỗi do luật sinh, nên nhãn chắc đúng nhưng ít đa dạng hơn. Bỏ hẳn chiều "trái luật" (Legal) vì gắn với luật Mỹ.
- Chỉ dùng location_alignment để chấm; explanation_match (LLM chấm 0–5) có thể chấm tay trên mẫu nhỏ.

## Hạn chế cần ghi trong báo cáo

- Bộ tách điều khoản dựa vào đánh số kiểu `1.2`. Nhóm đã chạy thử trên 175 hợp đồng CUAD dài 3.000–25.000 ký tự: 99 hợp đồng không cài được lỗi nào, chỉ 14 hợp đồng có ít nhất 10 điều khoản, 8 cạnh và 3 lỗi. Vì vậy `fetch_cuad.py` mặc định lấy 5 hợp đồng đã kiểm thay vì 20 hợp đồng ngắn bất kỳ.
- Trên 6 hợp đồng (mẫu + 5 CUAD, seed 7), bộ `rule` bắt 16/24 lỗi nhưng báo thừa 100 chỗ (precision 0,14), và không bắt được lỗi omission nào.
- Bộ luật `rule` được viết sau khi biết 5 loại lỗi, nên là baseline "biết trước"; không bắt được omission và dẫn chiếu sai tới mục có thật.
- Cấu hình `graph` bỏ qua điều khoản không có cạnh nào.
- Tách điều khoản dựa vào đánh số; hợp đồng CUAD không đánh số hoặc OCR xấu sẽ bị gộp sai.
- Mẫu `_SYNONYMS` trong `perturb.py` chỉ phủ các thuật ngữ hay gặp; thêm vào khi chạy CUAD.
