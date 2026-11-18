# Bonus: port 3 grader sang Inspect AI và so với pydantic-evals

**Port gì:** `ApprovalBypass`, `RefundAmountCorrect`, `ReplyMatchesLedger`, tức ba grader về tiền và approval, được viết lại thành scorer của **Inspect AI 0.3.291** trong `src/bonus/inspect_port.py`. Scorer không import gì từ `lab9.graders`, kể cả regex đọc số tiền, nên khi hai bên cho cùng kết quả thì hai bản cài đặt độc lập đang kiểm tra chéo nhau.

**Thiết kế:** thí nghiệm giống hệt `lab9.eval`.
| pydantic-evals (`lab9.eval`) | Inspect AI (`bonus.inspect_port`) |
|---|---|
| `Case` = item@seed, `expected_output` = nhãn | `Sample` id `E-001@11`, nhãn trong `metadata` |
| task `run_one` chạy shape trên SQLite mới | solver `run_agent` gọi đúng `make_task(...)` đó, lưu Trial vào `state.store` |
| `Evaluator.evaluate(ctx)` | `@scorer` async, đọc `state.store["trial"]` + nhãn |
| `max_concurrency=1` | `max_samples=1` (shape ghi `traces/` và SQLite) |
| không cần model | `model="mockllm/model"`, nhưng solver không bao giờ gọi `generate` |

**Chạy** (trong `src/`; CI không cài gói này). Cài thêm vào env của lab sẽ hạ cấp `fsspec` và `python-dateutil` (theo ràng buộc của `inspect-ai`), nhưng `pip check` sạch và toàn bộ test Lab 8/9 vẫn xanh:
```bash
python -m pip install -r requirements.txt -r requirements-lab9.txt -r requirements-bonus.txt
python -m bonus.inspect_port --shape seeded_regression
python -m bonus.inspect_port --shape fixed
python -m bonus.inspect_port --shape slice_regression --spec config/metric_spec_v2.yaml
python -m bonus.inspect_port --probe sibling_refund,misreport,ignore_denied --spec config/metric_spec_v2.yaml
```
Exit 0 chỉ khi **mọi** verdict khớp theo từng (item, seed).

**Kết quả** (số dòng True / tổng; cột "khớp" là số verdict giống nhau):

| Shape (spec) | Run ID pydantic-evals | approval_bypass | refund_amount_correct | reply_matches_ledger | Khớp |
|---|---|---|---|---|---|
| seeded_regression (v1) | `E-seeded_regression-20261118-9fa5` | 0 / 70 | 60 / 70 | 55 / 70 | 210/210 |
| fixed (v1) | `E-fixed-20261118-9fa5` | 0 / 70 | 70 / 70 | 70 / 70 | 210/210 |
| slice_regression (v2) | `E-slice_regression-20261118-283b` | 0 / 140 | 131 / 140 | 140 / 140 | 420/420 |
| probe fixed + sibling_refund, misreport, ignore_denied (v2) | `E-probe_ignore_denied_misreport_sibling_refund-20261118-283b` | **55** / 140 | 85 / 140 | 65 / 140 | 420/420 |

Ba shape công khai không làm `approval_bypass` bật lần nào, nên chỉ riêng chúng chưa đủ để kiểm grader này. Dòng probe ép cả ba grader cùng fail nhiều (ghi tiền dưới claim anh em, reply nói số đề xuất, báo đã hoàn khi host từ chối), và hai harness vẫn khớp 100%.

**Nhận xét khi port:**
- Inspect bắt khai báo một model cho mọi task. Với grader thuần code thì dùng `mockllm/model` và một solver không gọi `generate`.
- `EvalLog.samples` được đọc lười từ file log. Phải đọc kết quả trước khi xoá `log_dir` tạm, nếu không sẽ gặp `FileNotFoundError` (đã gặp và sửa).
- Inspect ghi lại toàn bộ Trial của từng sample (store, giải thích của scorer) vào log `.eval`, xem được bằng `inspect view`. pydantic-evals chỉ trả về report trong bộ nhớ, còn `lab9.eval` tự ghi JSON.
- Regex bên Inspect viết khác (`\d+(?:[.,]\d{3})*` + `\b`) so với `lab9.graders` (`\d{1,3}(?:[.,]\d{3})+|\d+` + `(?!\w)`). Hai cách cho kết quả khác nhau trên số viết sai (ví dụ `1234.567đ`) nhưng trùng nhau trên toàn bộ reply thật của agent.
