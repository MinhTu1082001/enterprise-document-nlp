# Code minh họa cho 8 bài báo

Mỗi file là một đoạn code nhỏ, chỉ dùng thư viện chuẩn của Python, cài lại đúng ý chính của một bài để nhóm chạy thử và giải thích. Đây là code của nhóm viết để học, không phải code của tác giả (trừ chỗ ghi rõ là chép lại logic của code chính thức).

| File | Bài | Nội dung |
| --- | --- | --- |
| `docsplit_metrics.py` | [4] DocSplit | Rand Index, V-measure, Kendall's tau, điểm packet |
| `extraction_f1.py` | [5] A Few Good Clauses | Ghép theo loại trường, micro/macro F1, chi phí GPU |
| `techeval_metrics.py` | [7] Technical evaluation | Macro-F1, Span-F1, Exact Match, IoU, ROUGE-1 |
| `clauseminer_prompt.py` | [8] ClauseMiner | Prompt one-shot, bộ tách kết quả của app.py, cách đọc JSON có kiểm trích dẫn |
| `compact_check_split.py` | [6] COMPACT | Tự kiểm trùng lặp train/test trên dữ liệu ACE công bố |
| `plawbench_scoring.py` | [2] PLawBench | Scoring rate, cách gộp điểm 4 phần như `LegalEvaluator`, điểm tổng 2:5:3, hệ số Pearson; thêm đường dẫn file PCA công khai để đếm tỷ lệ điểm |
| `docpp_dva.py` | [3] Doc-PP | DVA hai lần gọi như code chính thức, cách tính leakage và faithfulness; `dva_plus` là phần mở rộng của nhóm (thêm 1 lần kiểm ghép ý), không có trong bài |

[1] CLAUSE nằm trong demo chính: `contract_demo/perturb.py` (cài lỗi) và `contract_demo/score.py` (location_alignment).

Chạy: `python docsplit_metrics.py` (tương tự cho các file khác). `compact_check_split.py` cần tải dữ liệu ACE trước, xem dòng đầu file.
