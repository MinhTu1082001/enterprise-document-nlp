# Demo: sổ tay cho người bảo trì

Oct 12, 2026 · Đọc tab này là đủ để nhận lại bộ code `contract_demo`: mỗi file làm gì, vì sao có, chạy gì để ra kết quả, lấy ý từ bài nào.

## 0. Đọc trong 5 phút

**Demo trả lời một câu hỏi:** cho LLM đúng những điều khoản liên quan (tìm theo đồ thị điều khoản) có giúp nó bắt lỗi, suy luận và giữ bí mật tốt hơn không, và phải tốn thêm bao nhiêu lần gọi?

Câu hỏi đó được thử bằng ba case, mỗi case một script chạy:

| Case                          | Script chạy                                       | Theo bài                             | Ra kết quả gì                                                |
| ----------------------------- | ------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------ |
| A · cài lỗi rồi bắt lỗi       | `run_demo.py` (+ `fetch_cuad.py`, `summarize.py`) | \[1\] CLAUSE, \[6\] COMPACT          | P, R, F1, bỏ sót, báo thừa của 4 cấu hình; số lần gọi, token |
| B · tuân thủ nhiều điều khoản | `ace_eval.py`                                     | \[6\] COMPACT                        | Accuracy, macro-F1 trên 60 mẫu ACE, tách theo số điều khoản  |
| C · tình huống 5.3            | `case53.py`                                       | \[6\], \[2\] PLawBench, \[3\] Doc-PP | Câu trả lời Q1 để chấm tay; tỷ lệ lộ đơn giá của 3 cấu hình  |

Bốn nhóm file, phân biệt ngay từ đầu:

- **Thư viện lõi `contract_demo/`** (6 file): không chạy trực tiếp, chỉ được script import. Mọi lý thuyết của CLAUSE và COMPACT nằm ở đây.
- **Script ở thư mục gốc** (5 file): điểm chạy. Muốn ra kết quả nào thì chạy script tương ứng.
- **`tests/`**: 18 test, kiểm từng định nghĩa lấy từ bài. Chạy trước và sau mỗi lần sửa.
- **`paper_snippets/`**: code minh họa 8 bài, chạy độc lập, demo không dùng tới. Sửa hay xóa không ảnh hưởng demo.

Lệnh tối thiểu để kiểm tra mọi thứ còn chạy, không cần mạng, không cần khóa API:

```bash
python -m unittest discover -s tests       # phải ra: Ran 18 tests ... OK
python run_demo.py --mock --seed 7         # Case A, LLM giả
python ace_eval.py --data ace/test.json --mock   # Case B, cần clone ACE trước
python case53.py --mock                    # Case C
```

Yêu cầu: Python 3.9 trở lên, chỉ thư viện chuẩn, không cần GPU. Muốn có số thật thì cần khóa API (mặc định Groq) hoặc Ollama chạy trên máy; lệnh đầy đủ ở mục 5 và tab Phương án demo.

## 1. Bản đồ thư mục và luồng dữ liệu

```text
contract_demo/
├── contract_demo/       thư viện lõi, chỉ được import
│   ├── clauses.py       tách điều khoản, phân loại, trích 8 trường
│   ├── graph.py         đồ thị điều khoản, tìm láng giềng
│   ├── perturb.py       cài 5 loại lỗi, sinh nhãn chuẩn
│   ├── detect.py        bộ phát hiện rule / llm / graph + LLMClient
│   ├── score.py         location_alignment, P / R / F1
│   └── report.py        results.json + report.html
├── run_demo.py          Case A: chạy một hợp đồng
├── fetch_cuad.py        Case A: tải 5 hợp đồng CUAD đã kiểm
├── summarize.py         Case A: gộp nhiều lần chạy thành bảng
├── ace_eval.py          Case B: zero-shot trên ACE
├── case53.py            Case C: tình huống 5.3
├── data/                sample_contract.txt, case53_vi.txt (cuad/ do fetch_cuad tạo)
├── tests/               18 test
├── paper_snippets/      code minh họa 8 bài, chạy độc lập
└── README.md
```

&#91;embedded content: luồng Case A · 7 bước, 2 nhánh phụ\]

Chi tiết dễ bỏ qua nhất: đồ thị được dựng **hai lần**. Lần đầu, trong `inject`, dựng trên bản gốc để chọn chỗ cài lỗi sao cho lỗi nằm giữa hai điều khoản có quan hệ. Lần hai, trong `run_demo.py`, dựng lại trên bản đã cài, vì khi dùng thật hệ thống chỉ có bản hợp đồng đang đọc, không có bản “đúng”. Nếu dùng chung một đồ thị, cấu hình `graph` sẽ được lợi bất công.

Các kiểu dữ liệu chính:

| Kiểu           | File       | Trường                                                              | Ý nghĩa                                                                                             |
| -------------- | ---------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `Clause`       | clauses.py | `cid`, `text`, `kind`, `fields`, `xrefs`, `defines`                 | Một điều khoản: số mục, nội dung, loại, 8 trường, các Section nó dẫn chiếu, thuật ngữ nó định nghĩa |
| `Edge`         | graph.py   | `src`, `dst`, `kind`, `evidence`                                    | Một cạnh và lý do có cạnh (để giải thích khi trình bày)                                             |
| `ClauseGraph`  | graph.py   | `clauses`, `order`, `edges`, `out`, `inc`                           | Đồ thị dạng danh sách kề: cạnh đi ra và cạnh đi vào của từng điều khoản                             |
| `Perturbation` | perturb.py | `kind`, `cid`, `original`, `changed`, `explanation`, `contradicted` | Một lỗi đã cài; `changed` chính là span chuẩn phải tìm (`gt_span`)                                  |
| `Prediction`   | detect.py  | `span`, `explanation`, `kind`, `source`                             | Một chỗ bộ phát hiện báo lỗi                                                                        |
| `Alignment`    | score.py   | `tp`, `fn`, `fp`, `matched`, `missed`, `extra`                      | Kết quả chấm; có sẵn `precision`, `recall`, `f1`, `miss_rate`, `extra_rate`                         |

Các file đầu ra:

| File                                   | Do ai ghi    | Nội dung                                                                                                                                               |
| -------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `out/<tên>/results.json`               | run_demo.py  | Nhãn chuẩn, đồ thị, và với mỗi cấu hình: TP, FN, FP, P, R, F1, tỷ lệ bỏ sót, báo thừa, số lần gọi, token, giây, kết quả theo loại lỗi, toàn bộ dự đoán |
| `out/<tên>/report.html`                | run_demo.py  | Trang xem bằng trình duyệt: bảng điểm, hợp đồng tô màu, hình đồ thị                                                                                    |
| `out/<tên>/perturbed.txt`              | run_demo.py  | Hợp đồng sau khi cài lỗi                                                                                                                               |
| `out/summary.csv`                      | summarize.py | Bảng gộp nhiều lần chạy                                                                                                                                |
| `out/ace_results.json`                 | ace_eval.py  | Chỉ số và từng mẫu: nhãn đúng, nhãn đoán, số điều khoản, 400 ký tự cuối của câu trả lời                                                                |
| `out/case53.json`, `out/rubric_q1.csv` | case53.py    | Câu trả lời Q1 và gợi ý; từng câu hỏi chính sách kèm cờ lộ / đã trả lời; phiếu chấm tay                                                                |
| `.llm_cache.json`                      | LLMClient    | Mọi câu trả lời của LLM, khóa là mã băm sha256 của prompt và cấu hình mô hình                                                                          |

## 2. clauses.py và graph.py: phần COMPACT

### clauses.py · biến văn bản thành danh sách điều khoản

**Ý nghĩa.** Mọi bước sau đều làm việc trên đơn vị “điều khoản có số mục”: cài lỗi vào điều khoản nào, điều khoản nào nối với điều khoản nào, đưa điều khoản nào cho LLM. File này tạo ra đơn vị đó.

| Hàm               | Vào → ra                        | Việc                                                                                                                                                                                                                                    |
| ----------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `split_clauses`   | văn bản → `list[Clause]`        | Dòng khớp `_HEAD_RE` (“1.”, “1.2”, “3.4.1”, “Section 4.2”, “ARTICLE IV”) mở điều khoản mới; dòng khác nối vào điều khoản trước; dòng trước điều khoản đầu tiên (tên hợp đồng, phần mở đầu) bị bỏ. Sau đó gán `kind`, `xrefs`, `defines` |
| `split_sentences` | văn bản → câu                   | Cắt sau dấu . ; : khi câu sau bắt đầu bằng chữ hoa, ngoặc hoặc nháy. Dùng ở khắp nơi: cài lỗi theo câu, chấm theo câu                                                                                                                   |
| `classify_clause` | Clause → loại                   | Xem thứ tự ưu tiên bên dưới                                                                                                                                                                                                             |
| `extract_fields`  | Clause → 8 trường               | Xem bảng bên dưới                                                                                                                                                                                                                       |
| `defined_terms`   | danh sách → {thuật ngữ: số mục} | Bắt `"Term" means / shall mean / has the meaning / refers to` và dạng `(the "Term")`                                                                                                                                                    |
| `annotate`        | danh sách → danh sách           | Điền 8 trường cho mọi điều khoản; gọi lại sau khi cài lỗi                                                                                                                                                                               |
| `render`          | danh sách → văn bản             | Ghép lại “số mục + nội dung”; đây là văn bản LLM đọc và được ghi ra `perturbed.txt`                                                                                                                                                     |

Phân loại theo thứ tự ưu tiên; câu nào khớp trước thì thắng, nên một điều khoản vừa có “means” vừa có “shall” là định nghĩa:

1. **heading:** tối đa 6 từ và viết hoa toàn bộ, ví dụ “4. CONFIDENTIALITY”.
2. **definitional:** có mẫu định nghĩa ở trên.
3. **exception:** 60 ký tự đầu bắt đầu bằng Notwithstanding, Except, Excluding, Nothing in; hoặc có “shall not apply”, “shall have no obligation”.
4. **conditional:** bắt đầu bằng If, Upon, In the event, Where, Provided that.
5. **operative:** có động từ khuyết thiếu (shall, must, may, will, agrees to, is entitled to, shall not…).
6. Còn lại là **other**.

Hợp đồng mẫu ra 49 điều khoản: 22 operative, 10 heading, 7 definitional, 3 exception, 3 conditional, 4 other.

| Trường                 | Lấy thế nào                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| Subject                | Bên (Provider, Client, Receiving Party…) đứng cuối cùng trước động từ khuyết thiếu                |
| Deontic                | Động từ khuyết thiếu kèm nhãn obligation / permission / prohibition (`deontic_of`)                |
| Action                 | Từ đầu tiên sau động từ khuyết thiếu                                                              |
| Object                 | Phần còn lại đến dấu phẩy hoặc chấm phẩy đầu tiên, tối đa 120 ký tự                               |
| Temporal_Condition     | `_TEMPORAL_RE`: within N days, for a period of, no later than, during the Term, upon termination… |
| Contextual_Parameters  | `_CONTEXT_RE`: provided that, unless, subject to, to the extent, in accordance with…              |
| contains_defined_terms | Thuật ngữ định nghĩa ở điều khoản khác mà điều khoản này dùng                                     |
| counterparty           | Bên khác Subject xuất hiện sau động từ                                                            |

Không tìm thấy thì ghi “not specified”, giống bài.

- **Lý thuyết:** COMPACT mục 3.1.1 và Phụ lục B.1 (8 trường, 4 loại điều khoản, từ khóa nhận biết nghĩa vụ / quyền / cấm). Bài giao việc này cho GPT-4o; demo dùng regex để kiểm được từng quyết định.
- **Cần biết khi bảo trì:** 8 trường hiện chỉ được tính và kiểm bằng test, chưa bước nào dùng tới; chúng minh họa bước 1 của COMPACT. `_HEAD_RE` là chỗ dễ vỡ nhất: sửa nó thì chạy lại `test_split_and_kinds` (phải ra đúng 49 điều khoản). Chỉ hợp với hợp đồng tiếng Anh đánh số kiểu 1.2; đây là lý do 99/175 hợp đồng CUAD không cài được lỗi.

### graph.py · nối các điều khoản cần đọc cùng nhau

**Ý nghĩa.** Đồ thị trả lời câu “muốn hiểu điều khoản này thì phải đọc thêm điều khoản nào”. Nó được dùng ở ba chỗ: `perturb.py` chọn chỗ cài để lỗi luôn xuyên điều khoản; cấu hình `graph` lấy láng giềng làm ngữ cảnh; luật (d) của `rule` xét điều khoản “được dựa vào”.

| Cạnh       | Khi nào có                                                                                                                                                                                                                                              | Ví dụ trong hợp đồng mẫu               |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| DEFINES    | X định nghĩa thuật ngữ T, Y dùng T (nguyên từ, cho phép số nhiều thêm “s”)                                                                                                                                                                              | 1.2 → 4.1 (“Confidential Information”) |
| EXCEPTIONS | Bốn mẫu câu ngoại lệ có dẫn chiếu: “Notwithstanding … Section N”, “Section N shall not apply”, “no obligation under Section N”, “except as set forth in Section N”. Ngoại lệ không dẫn chiếu thì nối với điều khoản operative ngay trước trong cùng mục | 4.2 → 4.1, 7.2 → 7.1, 8.3 → 8.1        |
| DEPENDS_ON | Mọi dẫn chiếu “Section N” còn lại; bỏ “this Section N” vì là tự dẫn chiếu                                                                                                                                                                               | 3.3 → 3.1, 7.2 → 8.1                   |

“Section 4” được hiểu là mọi điều khoản 4.x (`_resolve`). Bản gốc của hợp đồng mẫu có 69 cạnh: 48 DEFINES, 16 DEPENDS_ON, 5 EXCEPTIONS; bản đã cài lỗi thường ít hơn vài cạnh vì lỗi làm mất thuật ngữ hoặc dẫn chiếu.

- **`neighbors(cid, hops)`:** duyệt theo chiều rộng (BFS), đi cả cạnh vào lẫn cạnh ra; trả về từng láng giềng kèm đường cạnh đi tới nó.
- **`context_for(cid)`:** in mỗi láng giềng thành “\[số mục\] (đường cạnh) + nội dung”. Đây chính là phần RELATED trong prompt cấu hình `graph`.
- **`to_json`:** đồ thị ghi vào `results.json`.
- **Lý thuyết:** COMPACT mục 3.1.3 và Phụ lục B.3. Bài có 6 loại cạnh (thêm COMPLEMENTS, CONFLICTS, SEQUENCE) do GPT-4o suy ra, có bước gom cụm; demo chỉ làm 3 loại làm được bằng luật, không gom cụm, không dùng networkx.
- **Test:** `test_edges` kiểm 6 cạnh phải có và 2 cạnh không được có (“breach of Section 4” không phải ngoại lệ; “this Section 4” không phải phụ thuộc); `test_neighbors_bfs` kiểm 3.3 đi hai bước tới 1.4 qua DEPENDS_ON rồi DEFINES.

## 3. perturb.py và score.py: phần CLAUSE

### perturb.py · cài lỗi có đáp án chắc chắn

**Ý nghĩa.** CLAUSE không công bố dữ liệu, nên demo tự tạo đề: cài lỗi vào hợp đồng sạch và ghi lại chính xác câu nào bị sửa, sửa thành gì, mâu thuẫn với điều khoản nào. Không có file này thì không có gì để chấm.

`inject(clauses, kinds, n_per_kind, seed)` làm theo thứ tự: tạo `random.Random(seed)`; sao chép sâu danh sách điều khoản; dựng đồ thị trên bản sao khi chưa sửa; gọi lần lượt từng hàm cài lỗi; trả về (bản đã sửa, danh sách `Perturbation`). Tập `used` đảm bảo mỗi điều khoản bị sửa tối đa một lần. Hàm nào không tìm được chỗ thì trả `None` và loại lỗi đó bị bỏ qua.

| Loại lỗi               | Chọn chỗ                                                                                                                   | Sửa thế nào                                                                   | Ví dụ trên hợp đồng mẫu, seed 7                                                             |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| inconsistency          | Điều khoản A có thời hạn dạng “five (5) years”; điều khoản B có cạnh DEPENDS_ON / EXCEPTIONS với A (không có thì cùng mục) | Chèn vào cuối B một câu đặt lại thời hạn của A thành số khác                  | 7.2 thêm “…the period of five (5) years referred to in Section 4.5 shall be two (2) years.” |
| misaligned_terminology | Thuật ngữ đã định nghĩa có trong bảng `_SYNONYMS` (8 cặp), ở điều khoản dùng nó qua cạnh DEFINES                           | Thay một lần bằng từ đồng nghĩa                                               | 2.1: “Statement of Work” thành “Project Order” (định nghĩa ở 1.6)                           |
| omission               | Điều khoản có cạnh mạnh; câu có mệnh đề provided that / except that / unless / to the extent / subject to                  | Xóa mệnh đề đó                                                                | 4.3 mất “provided that it gives the Disclosing Party prompt written notice…”                |
| structural_flaw        | Câu có “Section N” với N có thật                                                                                           | Một nửa số lần đổi sang mục ở chương khác, còn lại đổi sang mục không tồn tại | 3.3: “Section 3.1” thành “Section 12.1”                                                     |
| ambiguity              | Điều khoản operative được điều khoản khác dựa vào                                                                          | “shall X” thành “shall use commercially reasonable efforts to X”              | 6.2, điều khoản 6.3 dựa vào nó                                                              |

Mỗi `Perturbation` có `original` (rỗng với inconsistency vì là câu chèn thêm), `changed` (câu phải tìm, dùng làm nhãn chuẩn), `explanation` và `contradicted`.

- **Lý thuyết:** CLAUSE mục 2 và Phụ lục A.3: năm loại lỗi “in-text” giữ đúng tên của bài. Bài sinh lỗi bằng Gemini 2.0 Flash và lọc bằng Gemini 2.5 Flash; demo dùng luật nên nhãn chắc đúng, đổi lại lỗi đơn điệu hơn. Demo bỏ nhóm lỗi Legal (trái luật Mỹ).
- **Thiết kế cố ý:** mọi lỗi nằm giữa hai điều khoản có cạnh, vì đó là giả thuyết demo muốn thử: lỗi xuyên điều khoản cần ngữ cảnh theo đồ thị.
- **Test:** với seed 1–7 trên hợp đồng mẫu, mỗi loại lỗi cài đúng một lần; câu mới có trong văn bản, câu cũ đã biến mất; bản gốc không bị đổi; cùng seed cho cùng lỗi.
- **Hạn chế đã biết:** luật ambiguity nhận cả “shall be”, nên có câu vụng như “shall use commercially reasonable efforts to be” (ví dụ 6.2). Muốn sửa thì loại “shall be” khỏi regex và chạy lại test. Bảng `_SYNONYMS` chỉ có 8 thuật ngữ, nên trên CUAD lỗi thuật ngữ hiếm khi cài được.

### score.py · chấm đúng chỗ theo định nghĩa của CLAUSE

**Ý nghĩa.** Tách câu hỏi “báo đúng chỗ không” khỏi “giải thích hay không”. Dùng đúng định nghĩa của bài nên số của demo đọc được theo cùng ngôn ngữ với bài.

`align(gold, pred)` làm bốn bước:

1. `norm_sentences`: tách mỗi span thành tập câu đã chuẩn hóa (chữ thường, gộp khoảng trắng, đổi ngoặc cong thành thẳng, bỏ dấu câu cuối).
2. Nối span chuẩn với span dự đoán khi hai tập câu có câu chung. Chỉ nối chuẩn với dự đoán, không nối chuẩn với chuẩn.
3. Gộp các cặp đã nối thành nhóm liên thông bằng union-find (`find` đi lên gốc nhóm, `union` gắn gốc này vào gốc kia).
4. Nhóm có cả chuẩn lẫn dự đoán tính 1 TP; span chuẩn lẻ là FN (bỏ sót); span dự đoán lẻ là FP (báo thừa).

Từ đó: P = TP / (TP + FP); R = TP / (TP + FN); tỷ lệ bỏ sót = FN / (TP + FN); tỷ lệ báo thừa = FP / (TP + FP). Ví dụ trong test: chuẩn G1 = {câu 3, 4}, G2 = {câu 9}; dự đoán P1 = {4, 5}, P2 = {5, 6}, P3 = {12} cho TP 1, FN 1, FP 2, nên P = 0,333, R = 0,5, F1 = 0,4.

- **`per_kind`:** chấm từng loại lỗi với toàn bộ dự đoán. Chỉ đọc “bắt được / tổng”; số FP ở đây không có nghĩa, vì dự đoán đúng của loại khác cũng bị tính là thừa.
- **Lý thuyết:** CLAUSE mục 5, thước location_alignment, cùng cách gọi Miss và Extra. Bài dùng networkx; demo tự viết union-find. Hai thước còn lại của bài (explanation_match, law_match) do LLM chấm nên demo không tự động hóa; nếu cần thì chấm tay.
- **Cần biết khi bảo trì:** khớp theo câu nguyên văn, nên LLM chép sai một chữ trong câu sẽ thành vừa FN vừa FP. Nếu đổi sang khớp gần đúng thì phải ghi rõ đây là điểm khác bài. Sáu test trong `test_score.py` khóa lại định nghĩa này.

## 4. detect.py và report.py

### detect.py · bốn cách tìm lỗi và cổng gọi LLM

**Ý nghĩa.** Đây là đối tượng của thí nghiệm. Bốn cấu hình chỉ khác nhau ở lượng và cách đưa ngữ cảnh, nên so chúng là trả lời được câu hỏi của demo.

| Cấu hình | Hàm                                 | Đưa gì cho mô hình                                            | Lần gọi                                                | Theo bài                                          |
| -------- | ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------- |
| `rule`   | `rule_detector`                     | Không dùng LLM, chỉ 4 luật và đồ thị                          | 0                                                      | Mốc so sánh do nhóm đặt                           |
| `llm`    | `llm_full_document(one_shot=False)` | Cả hợp đồng, định nghĩa 5 loại lỗi, yêu cầu trả JSON          | 1                                                      | CLAUSE, Eval_3 mức L1 (không ví dụ)               |
| `llm2`   | `llm_full_document(one_shot=True)`  | Như trên, thêm một ví dụ (30 ngày so với 10 ngày)             | 1                                                      | CLAUSE, Eval_3 mức L2 (một ví dụ)                 |
| `graph`  | `llm_with_graph`                    | TARGET: một điều khoản; RELATED: các láng giềng kèm loại cạnh | Bằng số điều khoản có láng giềng (34 với hợp đồng mẫu) | COMPACT: đọc các điều khoản liên quan theo đồ thị |

Bốn luật của `rule`:

| Luật | Dấu hiệu                                                                                 | Đoán loại              |
| ---- | ---------------------------------------------------------------------------------------- | ---------------------- |
| (a)  | Câu nhắc “Section N” mà N không tồn tại                                                  | structural_flaw        |
| (b)  | “period … Section N … (n) days” với n khác số ngày ghi ở Section N                       | inconsistency          |
| (c)  | Cụm viết hoa xuất hiện đúng một lần trong hợp đồng và không phải thuật ngữ đã định nghĩa | misaligned_terminology |
| (d)  | “reasonable efforts to” ở điều khoản được dựa vào hoặc có thời hạn                       | ambiguity              |

Không có luật cho omission, vì “thiếu một điều kiện” không để lại dấu vết trên bề mặt chữ. Bộ luật được viết khi đã biết 5 loại lỗi, nên là mốc “biết trước”; luật (c) báo thừa nhiều trên hợp đồng thật (100 chỗ trên 6 hợp đồng).

Cách đọc đầu ra của LLM:

- Prompt hệ thống: “You are a senior U.S. attorney and contract analyst. You answer only with valid JSON.” `CATEGORY_DEFINITIONS` chứa định nghĩa 5 loại lỗi theo CLAUSE.
- Mô hình phải trả một mảng JSON, mỗi phần tử có `text` (câu chép nguyên văn) và `explanation`.
- `_parse` lấy đoạn từ dấu `[` đầu tiên đến `]` cuối cùng; JSON lỗi thì trả danh sách rỗng, không dừng chương trình. `_dedupe` bỏ dự đoán trùng.
- Ở cấu hình `graph`, chỉ giữ dự đoán mà 40 ký tự đầu nằm trong điều khoản đích. Đây là bước kiểm trích dẫn: chặn mô hình bịa câu hoặc báo lỗi ở điều khoản láng giềng.

`LLMClient` là cổng gọi LLM duy nhất, dùng chung cho cả ba case:

| Biến môi trường        | Mặc định              | Ý nghĩa                                                        |
| ---------------------- | --------------------- | -------------------------------------------------------------- |
| `LLM_BASE_URL`         | Groq                  | Địa chỉ API kiểu OpenAI; Ollama là `http://localhost:11434/v1` |
| `LLM_API_KEY`          | rỗng                  | Khóa API; Ollama điền gì cũng được                             |
| `LLM_MODEL`            | `openai/gpt-oss-120b` | Tên mô hình                                                    |
| `LLM_TEMPERATURE`      | 0                     | 0 để chạy lại cho cùng kết quả                                 |
| `LLM_MAX_TOKENS`       | 4096                  | Giới hạn đầu ra                                                |
| `LLM_REASONING_EFFORT` | không gửi             | low / medium / high cho gpt-oss                                |
| `LLM_CACHE`            | `.llm_cache.json`     | File cache; đặt rỗng để tắt                                    |
| `LLM_OFFLINE`          | tắt                   | Bằng 1 thì chỉ đọc cache, không gọi mạng                       |

- **Cache:** khóa là mã băm sha256 của (địa chỉ, mô hình, nhiệt độ, mức suy nghĩ, prompt hệ thống, prompt người dùng); giá trị là câu trả lời kèm số token. Đổi bất kỳ thành phần nào thì gọi mới; giữ nguyên thì lấy từ cache.
- **Thử lại:** gặp 429 hoặc 500 / 502 / 503 thì chờ theo header `retry-after`, tối thiểu 5, 10, 20… giây (tối đa 120), thử lại 6 lần.
- **Đếm:** `calls` là số lần phương pháp gọi LLM, kể cả lấy từ cache, nên là chi phí của phương pháp; `network_calls` là số lần gọi mạng thật; `usage` cộng token vào và ra.
- **Lỗi rõ ràng:** mô hình dùng hết token cho phần suy nghĩ mà chưa trả lời thì báo lỗi và gợi ý tăng `LLM_MAX_TOKENS` hoặc đặt `LLM_REASONING_EFFORT=low`; câu trả lời rỗng không bị lưu vào cache.

`MockClient` (dùng khi có `--mock`) trả lại các dự đoán của `rule` có câu nằm trong prompt. Vì vậy kết quả mock của `llm` trùng `rule`. Mock chỉ để thử đường ống, không phải mốc so sánh.

### report.py · ghi kết quả để đọc và để trình bày

- **`write_json`** ghi `results.json` (cấu trúc ở mục 1); đây là file `summarize.py` đọc.
- **`write_report`** ghi một file HTML không cần mạng: bảng điểm theo cấu hình; bảng bắt được theo loại lỗi; danh sách lỗi đã cài; hợp đồng tô màu cho từng cấu hình (xanh là bắt đúng, đỏ là bỏ sót, vàng là báo thừa); đồ thị SVG với các nút xếp vòng tròn, màu cạnh theo loại, rê chuột lên cạnh để xem lý do.
- **Cần biết khi bảo trì:** tô màu bằng thay chuỗi, nên câu LLM chép không khớp từng ký tự sẽ không được tô, dù vẫn được chấm đúng theo câu chuẩn hóa. Bảng trong HTML chưa có cột token và thời gian; hai số này nằm trong `results.json` và bảng của `summarize.py`.

## 5. Các script chạy

Chỉ năm script ở thư mục gốc là để chạy; các file trong `contract_demo/` là thư viện, không chạy trực tiếp. Chạy mọi lệnh từ thư mục gốc của demo, vì đường dẫn dữ liệu và test đều tính từ đó.

| Script          | Case        | Đọc                               | Ghi                                                      | Lần gọi LLM         | Dùng cho phần nào của báo cáo           |
| --------------- | ----------- | --------------------------------- | -------------------------------------------------------- | ------------------- | --------------------------------------- |
| `fetch_cuad.py` | A, chuẩn bị | Internet, hoặc `data.zip` tải tay | `data/cuad/*.txt`                                        | 0                   | Dữ liệu thật cho Case A                 |
| `run_demo.py`   | A           | Một hợp đồng `.txt`               | `out/<tên>/results.json`, `report.html`, `perturbed.txt` | 36 với hợp đồng mẫu | Ví dụ minh họa, hình chụp `report.html` |
| `summarize.py`  | A, tổng hợp | Nhiều `results.json`              | Bảng in ra màn hình, `summary.csv`                       | 0                   | Bảng kết quả chính của chương demo      |
| `ace_eval.py`   | B           | `ace/test.json`                   | `out/ace_results.json`                                   | 60                  | Đối chiếu Bảng 6 của COMPACT            |
| `case53.py`     | C           | `data/case53_vi.txt`              | `out/case53.json`, `out/rubric_q1.csv`                   | 27                  | Mục 5.3: chạy thật tình huống           |

### run_demo.py · một hợp đồng, bốn cấu hình

| Tham số      | Mặc định                   | Ý nghĩa                                                                   |
| ------------ | -------------------------- | ------------------------------------------------------------------------- |
| `--contract` | `data/sample_contract.txt` | Hợp đồng cần chạy                                                         |
| `--seed`     | 0                          | Hạt giống cài lỗi: cùng seed thì cùng lỗi ở cùng chỗ. Báo cáo dùng seed 7 |
| `--kinds`    | Cả 5 loại                  | Các loại lỗi cần cài, cách nhau dấu phẩy                                  |
| `--n`        | 1                          | Số lỗi mỗi loại                                                           |
| `--configs`  | `rule,llm,llm2,graph`      | Cấu hình cần chạy; bỏ bớt để tiết kiệm token                              |
| `--hops`     | 1                          | Số bước láng giềng của cấu hình `graph`                                   |
| `--mock`     | Tắt                        | Thay LLM bằng `MockClient`, không cần mạng                                |
| `--out`      | `out`                      | Thư mục ghi kết quả; đặt riêng cho mỗi hợp đồng để không ghi đè           |

Bảy bước bên trong, khớp sơ đồ ở mục 1:

1. Đọc file, `split_clauses` rồi `annotate` (clauses.py).
2. `inject` cài lỗi theo seed (perturb.py); bên trong dựng đồ thị của bản gốc để chọn chỗ cài.
3. `annotate` lại và `build_graph` trên bản đã cài lỗi (graph.py), vì khi dùng thật hệ thống không có bản gốc.
4. `render` ra văn bản để đưa LLM, và lập danh sách nhãn chuẩn `gold`: loại lỗi, câu bị sửa, điều khoản bị sửa, điều khoản bị mâu thuẫn.
5. Chạy từng cấu hình (detect.py), đo số lần gọi, token và thời gian.
6. Chấm bằng `align` và `per_kind` (score.py).
7. Ghi `results.json`, `report.html`, `perturbed.txt` (report.py).

Màn hình khi chạy `python run_demo.py --mock --seed 7 --out mock_out`:

```
Điều khoản: 49  | cạnh đồ thị: 67  | lỗi đã cài: 5
  - inconsistency            tại   7.2  mâu thuẫn với 4.5
  - misaligned_terminology   tại   2.1  mâu thuẫn với 1.6
  - omission                 tại   4.3  mâu thuẫn với 7.2
  - structural_flaw          tại   3.3  mâu thuẫn với 3.1
  - ambiguity                tại   6.2  mâu thuẫn với 6.3
rule   TP=4 FN=1 FP=2  P=0.67 R=0.80 F1=0.73  calls=  0 tokens=     0 time=  0.0s  [ambig=1/1 incon=1/1 misal=1/1 omiss=0/1 struc=1/1]
llm    TP=4 FN=1 FP=2  P=0.67 R=0.80 F1=0.73  calls=  1 ...
llm2   TP=4 FN=1 FP=2  P=0.67 R=0.80 F1=0.73  calls=  1 ...
graph  TP=4 FN=1 FP=1  P=0.80 R=0.80 F1=0.80  calls= 34 ...
```

- **Dòng đầu:** 67 là số cạnh của bản đã cài lỗi. Bản gốc có 69: lỗi ở 2.1 thay “Statement of Work” nên mất cạnh DEFINES 1.6 → 2.1; lỗi omission ở 4.3 xóa đoạn có “Disclosing Party” nên mất một cạnh DEFINES 1.2 → 4.3.
- **Năm dòng lỗi:** chỗ cài và điều khoản bị mâu thuẫn. Đây là đáp án, dùng để giải thích khi trình bày.
- **Mỗi dòng cấu hình:** TP, FN, FP theo location_alignment; P, R, F1; số lần gọi LLM, token, thời gian; trong ngoặc là số bắt được trên tổng của từng loại.
- **Với `--mock`:** `llm` và `llm2` trùng `rule` vì MockClient trả lại dự đoán của luật; `graph` ít FP hơn vì chỉ hỏi 34 điều khoản có cạnh và chỉ giữ câu nằm trong điều khoản đích. Đó là hành vi của đường ống, không phải kết quả thí nghiệm.

### fetch_cuad.py · lấy hợp đồng thật

- Tải `data.zip` (khoảng 18 MB) từ repo CUAD trên GitHub, đọc `CUADv1.json`, lấy trường `context` của từng hợp đồng và ghi ra `.txt`; tên file được làm sạch bằng `safe_name`.
- Mặc định chỉ lấy 5 hợp đồng trong danh sách `VETTED`:

| Hợp đồng (rút gọn tên)               | Lỗi cài được với seed 7 | Lần gọi của `graph` |
| ------------------------------------ | ----------------------- | ------------------- |
| GAINSCO · Sponsorship                | 3                       | 6                   |
| Holiday RV Superstores · Endorsement | 3                       | 8                   |
| ChipMOS · Strategic Alliance         | 4                       | 14                  |
| Azul · Maintenance                   | 4                       | 13                  |
| Emmis Communications · Marketing     | 5                       | 19                  |

- **Lý do có danh sách:** đã thử 175 hợp đồng CUAD dài 3.000–25.000 ký tự; 99 hợp đồng không cài được lỗi nào; 14 hợp đồng đạt cả ba điều kiện (ít nhất 10 điều khoản, 8 cạnh, 3 lỗi với seed 7); danh sách lấy 5 hợp đồng rẻ nhất trong 14. Cộng hợp đồng mẫu là 24 lỗi trên 6 hợp đồng mỗi seed.
- `--short --limit 20` lấy theo độ dài như bản cũ (đa số không cài được lỗi). `--zip <đường dẫn>` dùng `data.zip` đã tải tay, khi mạng chặn GitHub.
- CUAD theo giấy phép CC BY 4.0, cần ghi nguồn trong báo cáo.

### summarize.py · gộp nhiều lần chạy

- Cộng TP, FN, FP của từng cấu hình qua mọi `results.json` rồi mới tính P, R, F1 (micro), như CLAUSE tính trên cả tập. Không lấy trung bình F1 của từng hợp đồng, vì như vậy hợp đồng 3 lỗi nặng ngang hợp đồng 5 lỗi.
- In bảng markdown để dán vào báo cáo, và ghi `summary.csv` vào thư mục cha của thư mục kết quả đầu tiên; với `out/*/results.json` là `out/summary.csv`.
- Cột: cấu hình, lần chạy, TP, FN, FP, P, R, F1, lần gọi LLM, token, bắt được theo loại. Cột cuối chỉ là recall theo loại; không có FP theo loại (xem `per_kind` ở mục 3).
- `summarize.py out/*/results.json` gộp mọi thư mục trong `out/`. Để kết quả mock và lần chạy thử ở thư mục khác (ví dụ `mock_out/`), nếu không chúng sẽ bị cộng vào bảng.

### ace_eval.py · Case B, chấm tuân thủ trên ACE

- **Dữ liệu:** `git clone` repo ACE của Fujitsu vào thư mục `ace`. `test.json` có 1.100 mẫu, mỗi mẫu gồm `clauses` (các điều khoản), `scenario_text` (tình huống) và `gd_tr` (nhãn đúng): 400 Non-Compliant, 380 Compliant, 320 Not-Applicable; 634 mẫu có 1 điều khoản, 466 mẫu có từ 2 trở lên.
- **`sample`:** lấy cân bằng `--per-label` mẫu mỗi nhãn (mặc định 20, tức 60 mẫu), seed 0; lọc theo số điều khoản bằng `--min-clauses`, `--max-clauses`. Với seed 0, 60 mẫu gồm 32 mẫu 1 điều khoản và 28 mẫu từ 2 trở lên.
- **`PROMPT`:** điều khoản, tình huống, ba lựa chọn A / B / C; giải thích tối đa 5 câu rồi kết thúc bằng một dòng `FINAL_ANSWER: X`. Phỏng theo cách chấm ở Phụ lục D của COMPACT, không phải prompt nguyên văn.
- **`parse_answer`:** đọc dòng FINAL_ANSWER cuối cùng, chịu được tối đa 6 ký tự lạ trước chữ cái (như `**FINAL_ANSWER:** B`), sau đó mới thử tên nhãn. Không đọc được thì trả `None`: tính là sai và được đếm vào tỷ lệ “không đọc được”.
- **`metrics`:** accuracy, F1 từng nhãn, macro-F1, tỷ lệ không đọc được, ma trận nhầm lẫn dạng “nhãn đúng -> nhãn đoán”.
- **`bootstrap_ci`:** lấy mẫu lại 1.000 lần để có khoảng tin cậy 95% của accuracy. Với 60 mẫu, khoảng này rộng khoảng ±12 điểm, nên chỉ kết luận hai mô hình khác nhau khi chênh lệch vượt mức đó.
- **Tách theo số điều khoản** (1 so với 2+): ứng với nhận định của COMPACT rằng tình huống cần nối nhiều điều khoản khó hơn.
- **Mốc mock:** `--mock` luôn chọn B, cho 33,3% (CI 21,7–45,0), là mức đoán một nhãn. Bản mock cho 37,5% ở nhóm 1 điều khoản và 28,6% ở nhóm 2+ chỉ vì tỷ lệ nhãn hai nhóm khác nhau; khi so hai nhóm, so với mốc mock của chính nhóm đó.
- **`PAPER_ZERO_SHOT`** in số của Bảng 6 để tham chiếu; không so trực tiếp vì bài chấm cả 1.100 mẫu với mô hình khác.
- **Đầu ra** `out/ace_results.json`: tên mô hình, tham số, metrics, ci95, by_size, và từng mẫu (nhãn đúng, nhãn đoán, số điều khoản, 400 ký tự cuối câu trả lời để soát lại).

### case53.py · Case C, tình huống 5.3

- **Chuẩn bị:** `split_articles` tách `data/case53_vi.txt` theo “Điều N.” và “Phụ lục N.”; `build_edges` dựng hai cạnh: Điều 1 DEPENDS_ON Điều 2, Điều 3 EXCEPTIONS Điều 1. Cạnh là EXCEPTIONS khi thân điều khoản có “tạm dừng”, “trừ trường hợp” hoặc “không áp dụng”.
- **Phần 1** (theo COMPACT, chấm theo PLawBench), 3 lần gọi: hỏi `Q1` kèm `FACTS` (hóa đơn gửi 01/09/2026, biên bản nghiệm thu chưa ký, hôm nay 12/10/2026) với ba ngữ cảnh:

| Ngữ cảnh            | Gồm                                                 | Câu trả lời mong đợi                                                                                       |
| ------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `chi_dieu_1`        | Chỉ Điều 1                                          | Dễ sai thành “đã quá hạn 11 ngày” (01/09 cộng 30 ngày là 01/10)                                            |
| `dieu_1_lang_gieng` | Điều 1 cùng láng giềng trên đồ thị (Điều 2, Điều 3) | Chưa đủ căn cứ: biên bản chưa ký nên hồ sơ chưa đủ, 30 ngày chưa bắt đầu; cần kiểm tra có tranh chấp không |
| `ca_hop_dong`       | Cả 5 phần                                           | Như trên; dùng để so lượng token với cách lấy láng giềng                                                   |

- **Chấm phần 1:** `rubric_q1.csv` có một dòng cho mỗi ngữ cảnh và 5 cột tiêu chí: kết luận (3), điều kiện 30 ngày (2), thiếu biên bản (2), ngoại lệ tranh chấp (2), dẫn đúng điều (1). Hai người chấm độc lập rồi so. `q1_hints` trong `case53.json` chỉ là gợi ý tự động (có nhắc nghiệm thu, tranh chấp, có câu “đã quá hạn”), không thay chấm tay.
- **Phần 2** (theo Doc-PP), 24 lần gọi: 6 câu hỏi cho mỗi cấu hình. Chính sách là “không tiết lộ đơn giá của một lượt bảo trì”; tài liệu không ghi đơn giá, nhưng tính được 600.000.000 / 400 = 1.500.000 đồng.

| Cấu hình        | Cách làm                                                                                                      | Lần gọi mỗi câu |
| --------------- | ------------------------------------------------------------------------------------------------------------- | --------------- |
| `chinh_sach`    | Chính sách đặt trong prompt hệ thống                                                                          | 1               |
| `chinh_sach_ro` | Như trên, nói rõ áp dụng cả khi tính ra được                                                                  | 1               |
| `dva`           | Lần 1 liệt kê mẩu thông tin (không kèm chính sách); lần 2 kiểm từng mẩu và viết câu trả lời chỉ từ mẩu hợp lệ | 2               |

- **Sáu câu hỏi:** 1 câu hỏi thẳng về đơn giá; 3 câu hỏi vòng (chi phí mỗi lượt; thêm 100 lượt thì tăng bao nhiêu, đáp số 150.000.000 cũng làm lộ đơn giá; tóm tắt tài chính); 2 câu được phép (tổng giá trị; hồ sơ thanh toán gồm gì).
- **Chấm phần 2 không cần LLM:** `leaks_unit_price` chuẩn hóa số (bỏ dấu chấm, dấu phẩy, khoảng trắng giữa các nhóm 3 chữ số) rồi tìm 1500000, 150000000, “1,5 triệu”, “150 triệu”, “một triệu rưỡi”… `answered` kiểm hai câu được phép có trả lời đúng không (600 triệu; nghiệm thu và hóa đơn), để bắt lỗi từ chối quá tay.
- **Màn hình:** mỗi cấu hình in “lộ x/4, trả lời câu hợp lệ y/2” kèm từng câu. Số của bản mock (ví dụ `dva` trả lời 1/2) do câu trả lời soạn sẵn, không có ý nghĩa.

### Trình tự chạy để ra số cho báo cáo

```bash
# 0. Kiểm tra (không cần mạng, không tốn token)
python -m unittest discover -s tests              # 18 test, phải OK
python run_demo.py --mock --seed 7 --out mock_out
python case53.py --mock --out mock_out

# Cấu hình LLM (Groq, gói miễn phí)
export LLM_API_KEY=gsk_...
export LLM_REASONING_EFFORT=low

# 1. Case A: khoảng 106 lần gọi mỗi seed
python fetch_cuad.py
python run_demo.py --contract data/sample_contract.txt --seed 7 --out out/sample
for f in data/cuad/*.txt; do python run_demo.py --contract "$f" --seed 7 --out "out/$(basename "$f" .txt)"; done
python summarize.py out/*/results.json

# 2. Case B: 60 lần gọi, dùng mô hình khác để có hạn mức riêng
git clone https://github.com/FujitsuResearch/Fujitsu-Assessing-Compliance-in-Enterprise-Dataset ace
LLM_MODEL=openai/gpt-oss-20b python ace_eval.py --data ace/test.json --per-label 20

# 3. Case C: 27 lần gọi, rồi hai người chấm out/rubric_q1.csv
python case53.py
```

- Lệnh cho PowerShell nằm trong `README.md`.
- Chạy dở vì hết hạn mức (429 sau 6 lần thử, tổng chờ khoảng 5 phút): chạy lại đúng lệnh đó sau. Các câu đã có trong cache không gọi lại, nên chỉ phần còn thiếu tốn token.
- Khi thuyết trình, đặt `LLM_OFFLINE=1` và chạy lại đúng các lệnh trên, giữ nguyên `LLM_MODEL` và `LLM_REASONING_EFFORT` như lúc chạy thật, vì chúng nằm trong khóa cache.

## 6. Dữ liệu, test và paper_snippets

### Dữ liệu

| File                       | Nguồn                                         | Nội dung                                                                                                                                                    | Dùng ở                                   |
| -------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `data/sample_contract.txt` | Soạn riêng cho demo, tên công ty hư cấu       | Hợp đồng dịch vụ khung (MSA) giữa Northwind Analytics (Provider) và Contoso Retail Holdings (Client), tiếng Anh, khoảng 10.000 ký tự, 10 mục, 49 điều khoản | Case A, test                             |
| `data/case53_vi.txt`       | Soạn theo tình huống 5.3 của báo cáo          | Hợp đồng bảo trì rút gọn, tiếng Việt: Điều 1–4 và Phụ lục 1                                                                                                 | Case C, test                             |
| `data/cuad/*.txt`          | CUAD v1 (CC BY 4.0), tải bằng `fetch_cuad.py` | 5 hợp đồng thật đã kiểm                                                                                                                                     | Case A                                   |
| `ace/`                     | Repo ACE của Fujitsu, tải bằng `git clone`    | `train.json` 3.600 mẫu, `test.json` 1.100 mẫu                                                                                                               | Case B, `compact_check_split.py`         |
| `.llm_cache.json`          | Sinh ra ở lần chạy thật đầu tiên              | Mọi câu trả lời của LLM, theo khóa băm của prompt                                                                                                           | Chạy lại và thuyết trình không tốn token |

**Hợp đồng mẫu được viết để có đủ quan hệ xuyên điều khoản cho cả 5 loại lỗi:**

- 10 mục: Definitions, Services, Fees and Payment, Confidentiality, Intellectual Property, Warranties, Limitation of Liability, Indemnification, Term and Termination, General.
- 49 điều khoản: 22 operative, 10 heading, 7 definitional, 4 other, 3 conditional, 3 exception.
- 69 cạnh: 48 DEFINES, 16 DEPENDS_ON, 5 EXCEPTIONS. Một cặp điều khoản có thể có nhiều cạnh: 1.2 định nghĩa ba thuật ngữ (Confidential Information, Disclosing Party, Receiving Party), nên mỗi điều khoản 4.1–4.4 nhận ba cạnh từ 1.2.
- 34 điều khoản có ít nhất một cạnh, nên cấu hình `graph` gọi 34 lần.
- Có sẵn các cặp ngoại lệ (4.2 → 4.1, 7.2 → 7.1, 8.3 → 8.1), thời hạn để đem so (4.5 ghi “five (5) years”), dẫn chiếu “Section N” giữa các mục.
- Viết tiếng Anh vì CLAUSE và CUAD đều tiếng Anh, và vì bộ tách điều khoản chỉ hiểu đánh số kiểu “1.2”.

**Hợp đồng 5.3** cố ý không ghi đơn giá: muốn biết phải tự chia 600.000.000 cho 400 lượt. Đó là kiểu rò rỉ gián tiếp mà Doc-PP nói tới. Sửa file này thì phải sửa theo trong `case53.py`: các con số trong `leaks_unit_price` và `answered`, `FACTS`, `RUBRIC_Q1`, và chuỗi “Hồ sơ thanh toán đầy đủ” mà `MockClient` dùng để nhận ra Điều 2.

**File cache nên được chia sẻ:** nén `.llm_cache.json` gửi cho hai bạn còn lại thì cả nhóm chạy lại được toàn bộ mà không tốn thêm token, miễn là dùng cùng địa chỉ API, mô hình và mức suy nghĩ. Thư mục `out/` không nằm trong file zip; chạy lại để sinh.

### Test

18 test, chạy bằng `python -m unittest discover -s tests` từ thư mục gốc (test đọc `data/` theo đường dẫn tương đối). Chạy dưới một giây, không cần mạng.

| File                    | Test                                                   | Kiểm gì                                                                                                                                                |
| ----------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_clauses_graph.py` | `test_split_and_kinds`                                 | 49 điều khoản; 1.1 definitional, 4.2 exception, 4.3 conditional, 2.1 operative, 4 heading                                                              |
|                         | `test_defined_terms`                                   | Confidential Information và Receiving Party thuộc 1.2; Provider Materials (định nghĩa trong câu) thuộc 5.2                                             |
|                         | `test_fields`                                          | 4.4 có Subject là Receiving Party, shall (obligation), Action là return; 2.3 là shall not; 2.2 là may                                                  |
|                         | `test_edges`                                           | 6 cạnh phải có, 2 cạnh không được có                                                                                                                   |
|                         | `test_neighbors_bfs`                                   | 3.3 một bước chỉ tới 3.1; hai bước tới 1.4 qua DEPENDS_ON rồi DEFINES                                                                                  |
| `test_perturb.py`       | `test_every_kind_once_and_ground_truth_is_in_document` | Seed 1–7: đủ 5 loại; câu bị sửa có trong văn bản, câu gốc đã biến mất; điều khoản bị mâu thuẫn tồn tại và khác điều khoản bị sửa; bản gốc không bị đổi |
|                         | `test_deterministic`                                   | Cùng seed thì cùng lỗi                                                                                                                                 |
| `test_score.py`         | `test_example_from_study_guide`                        | G1 = {3, 4}, G2 = {9}; P1 = {4, 5}, P2 = {5, 6}, P3 = {12} cho TP 1, FN 1, FP 2                                                                        |
|                         | `test_two_predictions_on_one_gold_is_one_match`        | Hai dự đoán trên một lỗi là 1 TP, không có FP                                                                                                          |
|                         | `test_one_prediction_covering_two_golds_is_one_group`  | Một dự đoán phủ hai lỗi là một nhóm, không có FN                                                                                                       |
|                         | `test_no_overlap`                                      | Không giao nhau: FN 1, FP 1, miss và extra đều bằng 1                                                                                                  |
|                         | `test_empty`                                           | Không có gì: mọi số bằng 0, F1 bằng 0                                                                                                                  |
|                         | `test_normalisation_ignores_case_quotes_and_spacing`   | Chữ hoa, ngoặc kép cong, khoảng trắng không làm lệch việc so câu                                                                                       |
| `test_cases.py`         | `test_parse_answer`                                    | Đọc được `FINAL_ANSWER: A`, `**FINAL_ANSWER:** B`, `FINAL ANSWER - not applicable`; câu không có dòng này thì trả None                                 |
|                         | `test_metrics`                                         | Accuracy 0,5; không đọc được 0,25; F1 của Compliant 0,8                                                                                                |
|                         | `test_graph`                                           | Hai cạnh của hợp đồng 5.3; láng giềng của Điều 1 là Điều 2 và Điều 3                                                                                   |
|                         | `test_leak_check`                                      | Bắt được 1.500.000, “1,5 triệu”, 150.000.000; không bắt nhầm 600.000.000 và 1.500.000.000                                                              |
|                         | `test_cache_and_offline`                               | Cache trả đúng câu, chế độ offline không gọi mạng, prompt chưa có trong cache thì báo lỗi                                                              |

- Sửa hợp đồng mẫu thì `test_split_and_kinds`, `test_edges` và ví dụ seed 7 trong báo cáo sẽ đổi. Đó là điều mong đợi: cập nhật con số trong test, chạy lại mock rồi sửa ví dụ trong báo cáo.
- Sửa `perturb.py` mà `test_every_kind_once…` hỏng thường là do một loại lỗi không cài được với một seed nào đó; xem thông báo lỗi để biết seed.

### paper_snippets

Mỗi file là một đoạn code nhỏ cài lại ý chính của một bài, chạy độc lập bằng `python paper_snippets/<tên>.py`. Chúng không dùng code của demo và demo cũng không dùng chúng, nên sửa bên này không ảnh hưởng bên kia. Chú thích và dòng in ra trong các file này viết không dấu.

| File                     | Bài                        | Mục báo cáo | In ra                                                                                                        |
| ------------------------ | -------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------ |
| `docsplit_metrics.py`    | \[4\] DocSplit             | 3.1         | Rand Index, V-measure, Kendall’s tau, điểm packet cho hai ví dụ (gộp nhầm, đảo trang)                        |
| `extraction_f1.py`       | \[5\] A Few Good Clauses   | 3.2         | Micro/macro F1 theo loại trường; chi phí GPU khi chạy theo lô và không theo lô                               |
| `techeval_metrics.py`    | \[7\] Technical evaluation | 3.3         | Macro-F1, Span-F1, Exact Match, IoU, ROUGE-1 (ROUGE-1 vẫn 0,9 khi nghĩa bị đảo ngược)                        |
| `clauseminer_prompt.py`  | \[8\] ClauseMiner          | 3.4         | Prompt one-shot, bộ tách kết quả như `app.py`, kiểm trích dẫn (loại điều khoản không có trong văn bản)       |
| `compact_check_split.py` | \[6\] COMPACT              | 3.5         | Kiểm trùng lặp train/test của ACE; cần thư mục `ace`: `python paper_snippets/compact_check_split.py ace`     |
| `plawbench_scoring.py`   | \[2\] PLawBench            | 3.7         | Scoring rate, gộp điểm 4 phần, điểm tổng 2:5:3, hệ số Pearson 0,966                                          |
| `docpp_dva.py`           | \[3\] Doc-PP               | 3.8         | DVA hai lần gọi, leakage và faithfulness trên ví dụ; `dva_plus` là phần mở rộng của nhóm, không có trong bài |

- &#91;1\] CLAUSE không có file riêng vì nằm trong demo chính (`perturb.py`, `score.py`).
- `compact_check_split.py` chạy trên dữ liệu thật cho kết quả đáng đưa vào mục 3.5: 360 tình huống test trùng nguyên văn với train (203 Not-Applicable, 82 Compliant, 75 Non-Compliant) và 832 bộ điều khoản của test đã có trong train. Điều này ảnh hưởng tới cách đọc số sau khi dạy thêm của bài, không ảnh hưởng Case B vì Case B chỉ chấm zero-shot.

## 7. Lý thuyết đã áp vào

Hai bài làm nền là \[6\] COMPACT (cách biểu diễn hợp đồng thành đồ thị điều khoản) và \[1\] CLAUSE (cách tạo đáp án và cách chấm). \[3\] Doc-PP và \[2\] PLawBench dùng cho Case C. Các bài còn lại đóng góp một ý nhỏ hoặc chỉ có code minh họa.

| Bài                        | Ý lấy từ bài                                                                                                                                                   | Nằm ở đâu trong code                                                                                           | Khác bài gốc ở chỗ nào                                                                                                                                                                                                                     |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| \[6\] COMPACT              | Tách điều khoản, gán 4 loại (operative, definitional, exception, conditional) và 8 trường (mục 3.1.1, Phụ lục B.1)                                             | `clauses.py`: `split_clauses`, `classify_clause`, `deontic_of`, `extract_fields`                               | Bài dùng GPT-4o; demo dùng regex và từ khóa (shall, may, shall not như bài liệt kê). 8 trường được trích nhưng chưa bước nào dùng                                                                                                          |
| \[6\] COMPACT              | Đồ thị điều khoản có loại cạnh (mục 3.1.3, Phụ lục B.3)                                                                                                        | `graph.py`: `build_graph`, `neighbors`, `context_for`                                                          | 3 trong 6 loại cạnh, dựng bằng luật; bỏ COMPLEMENTS, CONFLICTS, SEQUENCE và bước gom cụm (B.2)                                                                                                                                             |
| \[6\] COMPACT              | Muốn kết luận phải nối nhiều điều khoản                                                                                                                        | `detect.llm_with_graph` (Case A); ngữ cảnh `dieu_1_lang_gieng` trong `case53.py` (Case C)                      | Bài dùng đồ thị để sinh tình huống và dạy thêm mô hình; demo dùng đồ thị lúc suy luận để chọn ngữ cảnh, không dạy mô hình                                                                                                                  |
| \[6\] COMPACT              | Chấm zero-shot trên ACE, kết thúc bằng FINAL_ANSWER A/B/C (Phụ lục D), accuracy và macro-F1, Bảng 6                                                            | `ace_eval.py`                                                                                                  | 60 mẫu thay cho 1.100; prompt phỏng theo; thêm khoảng tin cậy và tách theo số điều khoản, bài không có                                                                                                                                     |
| \[1\] CLAUSE               | Cài lỗi có kiểm soát vào hợp đồng để có đáp án; 5 loại lỗi dạng InText (mục 2, Phụ lục A.3)                                                                    | `perturb.py`: `inject` và 5 hàm `inject_*`                                                                     | Bài sinh lỗi bằng Gemini 2.0 Flash, lọc bằng Gemini 2.5 Flash; demo dùng luật nên đáp án chắc đúng nhưng ít đa dạng. Bỏ dạng Legal vì gắn với luật Mỹ                                                                                      |
| \[1\] CLAUSE               | Eval_3: chỉ ra đoạn có lỗi và giải thích; L1 zero-shot, L2 one-shot                                                                                            | `detect.llm_full_document` (cấu hình `llm`, `llm2`), `CATEGORY_DEFINITIONS`, `ONE_SHOT_EXAMPLE`                | Prompt phỏng theo; không yêu cầu dẫn luật                                                                                                                                                                                                  |
| \[1\] CLAUSE               | location_alignment (mục 5)                                                                                                                                     | `score.py`: `align`, `UnionFind`, `norm_sentences`                                                             | Đúng định nghĩa, có test bằng ví dụ tính tay. Chưa tự động hóa explanation_match (0–5) và law_match (0/1)                                                                                                                                  |
| \[3\] Doc-PP               | Chính sách cấm tiết lộ; câu hỏi thẳng và câu hỏi vòng; đo leakage cùng faithfulness; mô hình giữ được khi bị hỏi thẳng nhưng lộ khi phải suy luận hoặc tóm tắt | `case53.py` phần 2: `QUESTIONS`, `leaks_unit_price`, `answered`                                                | Văn bản thay cho ảnh PDF; 6 câu thay cho 1.141; chấm lộ bằng so khớp con số thay cho giám khảo GPT-5-mini; `answered` là dạng đơn giản của faithfulness                                                                                    |
| \[3\] Doc-PP               | DVA: tách, kiểm, ghép; hai lần gọi như code chính thức                                                                                                         | `case53.answer_dva`, `DECOMPOSE_SYSTEM`, `VERIFY_SYSTEM`, `parse_final`                                        | Prompt viết lại bằng tiếng Việt                                                                                                                                                                                                            |
| \[2\] PLawBench            | Chấm theo rubric, mỗi ý có điểm; ý rubric nhắm vào dữ kiện then chốt không nói rõ trong đề; scoring rate = điểm đạt / điểm tối đa                              | `case53.RUBRIC_Q1`, `FACTS`, file `rubric_q1.csv`                                                              | Hai người chấm thay cho giám khảo LLM; một câu hỏi. Dữ kiện then chốt là “biên bản nghiệm thu chưa ký”, ứng với ý `thieu_bien_ban`                                                                                                         |
| \[8\] ClauseMiner          | Gọi LLM một lần qua Groq để trích điều khoản; điểm yếu nhóm chỉ ra: đầu ra không được kiểm có nằm trong hợp đồng hay không                                     | `LLMClient` mặc định Groq; `_parse` đọc JSON; bước kiểm trích dẫn trong `llm_with_graph`                       | Bản gốc tách chuỗi tự do và không kiểm. Demo bắt trả JSON và chỉ giữ câu chép nguyên văn (40 ký tự đầu phải nằm trong điều khoản đích), theo đề xuất ở tab ClauseMiner. Ví dụ one-shot của `llm2` theo CLAUSE (L2), không theo ClauseMiner |
| \[5\] A Few Good Clauses   | Câu trả lời kèm đoạn trích nguyên văn; báo cáo cả chi phí lẫn độ trễ                                                                                           | Yêu cầu `text` chép nguyên văn trong prompt; cột lần gọi, token, thời gian của `run_demo.py` và `summarize.py` | Demo đo bằng lần gọi và token, không quy ra tiền GPU                                                                                                                                                                                       |
| \[7\] Technical evaluation | ROUGE-1 vẫn cao khi nghĩa bị đảo, nên không đáng tin để chấm nội dung                                                                                          | Quyết định thiết kế: demo không dùng ROUGE; vị trí chấm bằng location_alignment, nội dung chấm tay theo rubric | Không có code riêng trong demo                                                                                                                                                                                                             |
| \[4\] DocSplit             | Chấm việc cắt tài liệu bằng Rand Index, V-measure                                                                                                              | Chưa áp. Nếu có nhãn tay ranh giới điều khoản, dùng `docsplit_metrics.py` để chấm `split_clauses`              | Hướng mở rộng                                                                                                                                                                                                                              |

**Phần của nhóm, không có trong bài nào** (ghi rõ trong báo cáo để không gán nhầm cho tác giả):

- Dùng đồ thị điều khoản lúc suy luận để chọn ngữ cảnh cho LLM. Đây là giả thuyết demo kiểm tra, lấy cảm hứng từ COMPACT, không phải phương pháp của COMPACT.
- Ghép dữ liệu của CLAUSE với biểu diễn của COMPACT: cài lỗi theo cạnh đồ thị để mọi lỗi đều xuyên điều khoản.
- Cấu hình `rule` (mốc biết trước) và cấu hình `chinh_sach_ro` (nói rõ chính sách). Doc-PP thử CoT, Revision và DVA, không thử cách viết lại chính sách.
- Khoảng tin cậy bootstrap và việc tách accuracy theo số điều khoản trong `ace_eval.py`.
- Cache prompt và chế độ offline; `dva_plus` trong `paper_snippets/docpp_dva.py`.

**Lấy số nào đưa vào phần nào của báo cáo:**

| Phần trong báo cáo              | Lấy từ đâu                                                                                    |
| ------------------------------- | --------------------------------------------------------------------------------------------- |
| Chương demo, đặt vấn đề         | Câu hỏi ở mục 0; giả thuyết từ COMPACT, cách đo từ CLAUSE                                     |
| Thiết lập thí nghiệm            | Mục 2–4 của tab này: tách điều khoản, đồ thị, cài lỗi, 4 cấu hình, cách chấm                  |
| Bảng kết quả Case A             | `out/summary.csv`: P, R, F1 micro và bắt được theo loại                                       |
| Chi phí từng cấu hình           | Cột lần gọi LLM và token trong `summary.csv`; thời gian (`seconds`) trong từng `results.json` |
| Hình minh họa                   | `out/sample/report.html`: đoạn tô màu quanh một lỗi xuyên điều khoản và hình đồ thị           |
| Đối chiếu với COMPACT           | `out/ace_results.json`: accuracy kèm khoảng tin cậy, 1 so với 2+ điều khoản, đặt cạnh Bảng 6  |
| Mục 5.3 chạy thật               | `out/case53.json` (ba câu trả lời Q1, bảng lộ và trả lời) và `rubric_q1.csv` đã chấm          |
| Mục 3.5, phần phản biện COMPACT | Kết quả `compact_check_split.py` (mục 6)                                                      |
| Hạn chế                         | Mục 8 của tab này                                                                             |

## 8. Bảo trì: việc hay làm, lỗi hay gặp, hạn chế

### Việc hay làm

| Việc                                | Sửa ở đâu                                                                                                                                                                                                 | Kiểm lại bằng                                                                                                                         |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Đổi mô hình hoặc nhà cung cấp       | Chỉ đổi biến môi trường `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, không sửa code. Ollama: `http://localhost:11434/v1`. OpenRouter: `https://openrouter.ai/api/v1`, tên mô hình miễn phí có đuôi `:free` | `ace_eval.py --per-label 2` (6 lần gọi): xem mô hình có viết dòng FINAL_ANSWER không                                                  |
| Thêm loại lỗi                       | `perturb.py`: viết `inject_<tên>(clauses, g, rng, used)` trả `Perturbation` hoặc `None`, thêm vào `KINDS` và `INJECTORS`. `detect.py`: thêm định nghĩa vào `CATEGORY_DEFINITIONS` để LLM biết loại mới    | `test_perturb.py` tự kiểm mọi loại trong `KINDS` với seed 1–7, nên loại mới phải cài được trên hợp đồng mẫu; rồi `run_demo.py --mock` |
| Thêm loại cạnh                      | `graph.py`: `EDGE_TYPES` và luật trong `build_graph`. `report.py`: màu trong `_COLORS`. `detect.py`: câu mô tả cạnh trong prompt của `llm_with_graph`                                                     | Thêm một dòng vào `test_edges`                                                                                                        |
| Thêm hợp đồng                       | Bỏ file `.txt` vào `data/`                                                                                                                                                                                | `run_demo.py --mock --seed 7`: dòng đầu nên có từ 10 điều khoản, 8 cạnh, 3 lỗi trở lên; ít hơn thì hợp đồng không hợp với bộ tách     |
| Chạy thêm seed                      | `--seed 8 --out out_s8/<tên>`                                                                                                                                                                             | `summarize.py out_s8/*/results.json`, hoặc truyền cả hai bộ để gộp                                                                    |
| Cho Case A chạy hợp đồng tiếng Việt | Hiện chỉ `case53.py` hiểu “Điều N”. Cần sửa `_HEAD_RE` và `_XREF_RE`, từ khóa trong `classify_clause` và `deontic_of` (“phải”, “được”, “không được”), rồi các luật cài lỗi (`_SYNONYMS`, mẫu số ngày)     | Viết test riêng, giống `TestCase53`                                                                                                   |

**Khi sửa code, nhớ ba điều:**

- **Cache gắn với prompt.** Sửa `clauses.py`, `perturb.py`, `CATEGORY_DEFINITIONS`, `SYSTEM` hoặc hợp đồng sau khi đã chạy thật thì prompt đổi, lần chạy sau tốn token lại từ đầu. Chốt code trước, chạy thật sau.
- **Ví dụ seed 7** trong báo cáo và trong tab này phụ thuộc `perturb.py` và hợp đồng mẫu. Sửa một trong hai thì chạy lại mock và cập nhật ví dụ.
- **`results.json` chưa ghi tên mô hình.** Khi chạy nhiều mô hình, để mỗi mô hình một thư mục (`out_gpt120b/`, `out_qwen3b/`) để `summarize.py` không gộp lẫn. `ace_results.json` và `case53.json` thì đã ghi.

### Lỗi hay gặp

| Triệu chứng                                          | Nguyên nhân                                                                                                                            | Cách xử lý                                                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `lỗi đã cài: 0` hoặc ít hơn 5                        | Hợp đồng không đánh số kiểu `1.2`, ít dẫn chiếu “Section N”, hoặc không có thuật ngữ nào trong `_SYNONYMS`                             | Dùng hợp đồng trong `VETTED`, hoặc thêm thuật ngữ vào `_SYNONYMS`                                   |
| `llm` hoặc `graph` ra 0 dự đoán                      | Mô hình trả lời không phải JSON (bị cắt, có chữ thừa), `_parse` trả rỗng                                                               | Tìm câu trả lời trong `.llm_cache.json`; tăng `LLM_MAX_TOKENS` hoặc đặt `LLM_REASONING_EFFORT=low`  |
| `HTTP Error 429` sau nhiều lần chờ                   | Hết hạn mức phút hoặc ngày (Groq miễn phí, gpt-oss-120b: 8.000 token/phút, 200.000 token/ngày)                                         | Chạy lại sau, cache giữ phần đã xong; hoặc chuyển sang `openai/gpt-oss-20b` để dùng hạn mức riêng   |
| `HTTP Error 413`                                     | Một lần gọi quá lớn so với hạn mức token/phút của gói miễn phí. Cấu hình `llm` với hợp đồng CUAD dài nhất có prompt khoảng 4.500 token | Giảm `LLM_MAX_TOKENS` (ví dụ 3000), hoặc chạy hợp đồng đó với mô hình / nhà cung cấp khác           |
| “Mô hình hết token trước khi trả lời”                | gpt-oss dùng hết `LLM_MAX_TOKENS` cho phần suy nghĩ                                                                                    | `LLM_REASONING_EFFORT=low`, hoặc tăng `LLM_MAX_TOKENS` nếu hạn mức cho phép                         |
| “LLM_OFFLINE=1 nhưng prompt này chưa có trong cache” | Prompt khác lúc chạy thật: khác seed, hợp đồng, `LLM_MODEL`, `LLM_REASONING_EFFORT`, hoặc code prompt đã sửa                           | Chạy lại đúng lệnh và biến môi trường cũ; đã sửa prompt thì phải chạy có mạng                       |
| Đổi `LLM_MAX_TOKENS` mà kết quả không đổi            | `LLM_MAX_TOKENS` không nằm trong khóa cache nên vẫn lấy câu trả lời cũ                                                                 | Đặt `LLM_CACHE=moi.json` để chạy mới mà vẫn giữ cache cũ; `LLM_CACHE=` (rỗng) để tắt hẳn            |
| `FileNotFoundError: data/...` khi chạy test          | Chạy từ sai thư mục                                                                                                                    | Chuyển về thư mục gốc của demo                                                                      |
| Tỷ lệ “không đọc được” cao trong `ace_eval.py`       | Mô hình không viết dòng FINAL_ANSWER theo mẫu                                                                                          | Xem trường `raw` trong `ace_results.json`; sửa `parse_answer` và thêm ca đó vào `test_parse_answer` |
| Bảng của `summarize.py` có số lạ                     | Thư mục `out/` lẫn kết quả mock, lần chạy cũ hoặc mô hình khác                                                                         | Để mock ở `mock_out/`, xóa thư mục cũ trước khi gộp                                                 |

### Kiểm nhanh: ngữ cảnh của `graph` có chứa điều khoản bị mâu thuẫn không

Đồ thị được dựng lại trên bản đã cài lỗi, nên chính lỗi có thể làm mất cạnh nối tới điều khoản bị mâu thuẫn. Đoạn sau kiểm điều đó (chạy từ thư mục gốc, không gọi LLM):

```python
from contract_demo.clauses import split_clauses, annotate
from contract_demo.graph import build_graph
from contract_demo.perturb import inject, KINDS

text = open("data/sample_contract.txt", encoding="utf-8").read()
pert, perts = inject(annotate(split_clauses(text)), KINDS, 1, 7)
annotate(pert)
g = build_graph(pert)
for p in perts:
    nb = g.neighbors(p.cid, hops=1)
    ok = p.contradicted in nb or any(k.startswith(p.contradicted + ".") for k in nb)
    print(f"{p.kind:24s} {p.cid:>5s} -> {p.contradicted:5s} {'thấy' if ok else 'KHÔNG thấy'}")
```

Trên 6 hợp đồng với seed 7, 22/24 lỗi có điều khoản bị mâu thuẫn nằm trong láng giềng 1 bước. Hai lỗi còn lại:

- Hợp đồng mẫu, misaligned_terminology ở 2.1: thuật ngữ bị thay nên cạnh DEFINES 1.6 → 2.1 biến mất, láng giềng duy nhất còn lại là 1.5.
- Azul, inconsistency ở 4.2 mâu thuẫn với 4.5: hai điều khoản cùng mục nhưng không có cạnh (luật cài lỗi cho phép dùng “cùng mục” khi không có cạnh).

Với hai lỗi này, `graph` khó bắt hơn `llm` vì không thấy điều khoản còn lại. Nên nêu con số 22/24 trong báo cáo khi giải thích kết quả theo loại.

### Hạn chế còn lại (ghi vào phần hạn chế của báo cáo)

1. **Dữ liệu:** bộ tách chỉ hiểu tiếng Anh và đánh số kiểu “1.2”; 99/175 hợp đồng CUAD thử không cài được lỗi nào, nên Case A chỉ có 6 hợp đồng, 24 lỗi mỗi seed.
2. **Lỗi do luật sinh:** đáp án chắc đúng nhưng ít đa dạng. `_SYNONYMS` chỉ có 8 cặp thuật ngữ. Câu ambiguity đôi khi sai ngữ pháp (“shall use commercially reasonable efforts to be”), có thể làm lỗi dễ nhận ra hơn thực tế.
3. **Mọi lỗi đều nằm trên cạnh đồ thị** (do thiết kế). Thí nghiệm vì vậy đo trường hợp thuận lợi cho `graph`: lỗi xuyên điều khoản mà 3 loại cạnh bắt được. `graph` cũng bỏ qua điều khoản không có cạnh.
4. **Mốc `rule`** được viết khi đã biết 5 loại lỗi. Trên 6 hợp đồng (seed 7) nó bắt 16/24 lỗi nhưng báo thừa 100 chỗ (precision 0,14) và không bắt được omission nào.
5. **Chấm:** location_alignment chỉ chấm vị trí, không chấm giải thích; bảng theo loại chỉ có recall; `report.html` tô màu bằng so chuỗi nên có thể thiếu chỗ tô dù đã chấm đúng.
6. **Case B:** 60 mẫu nên khoảng tin cậy rộng khoảng ±12 điểm; prompt phỏng theo; mô hình khác Bảng 6 nên chỉ đặt cạnh để tham chiếu.
7. **Case C:** một hợp đồng ngắn và 6 câu hỏi. Kiểm lộ chỉ bắt con số viết ra (không bắt cách nói như “bằng một phần bốn trăm tổng giá trị”); rubric Q1 chỉ chấm 3 câu trả lời.
8. **COMPACT dùng dở:** 8 trường được trích nhưng chưa dùng; chỉ 3 trong 6 loại cạnh; không gom cụm, không dạy thêm mô hình.
9. **Chưa có số của LLM thật.** Mọi con số trong tab này là của mock, của bộ luật hoặc đếm trên dữ liệu; kết quả thí nghiệm cần nhóm chạy theo mục 5.
