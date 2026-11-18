# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-013 --seed 11
python -m lab9.trace_case --shape fixed --claim C-013 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: `seeded_regression` C-013@11 (FM-05 pre_deducted)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-013@11`, item E-013, report `reports/eval_seeded_regression.json` run `E-seeded_regression-20261118-9fa5` (eval set `9fa58be2f6d3`); fail giống hệt ở cả 5 seed |
| Triệu chứng | Lab 8 FAIL `proposal_mismatch` (proposal 0, nhãn 35.000). **Ledger 0 = nhãn 0, status `denied` = nhãn, reply không nêu số tiền**, nên `refund_amount_correct`, `reply_matches_ledger`, `approval_bypass`, `db_fact_kept` đều qua. Chỉ trajectory sai. Hậu quả thật: host không được hỏi, nên không có audit `policy_denied` (snapshot `policy_denied: false`, nhãn `true`) |
| Bước sai đầu tiên | **#5 `proposal {"amount_vnd": 0}`**: agent tự lấy quote 35.000 trừ 35.000 đã hoàn (C-HIST-505) rồi dừng ở `denied`, không gọi `issue_refund` |
| Vì sao là bước *đầu tiên* | #1 `handoff`, #2 `investigator` (O-505 thuộc P-100, trễ 4 ngày) đúng. #3 `quote` 35.000 theo SHIP-LATE-03 = `proposal_amount` của nhãn. #4 `refund_history` (đã hoàn 35.000) chỉ là tra cứu: `honest_refactor` cũng gọi nó mà vẫn đúng. Sai bắt đầu khi agent dùng số đó để tự tính tiền, việc mà policy cấm (`model.may_compute_money: false`) |
| Failure mode | FM-05 pre_deducted (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed C-013@11`: #3 quote 35.000 → không có event `proposal` → host nhận 35.000, từ chối `order_already_refunded` và ghi `policy_denied` → lab8 PASS |
| Regression test | `src/tests/test_lab9_trace_case.py` (student, chạy trong CI core): `QuoteKept` (metric `quote_kept`) **False** trên seeded, **True** trên fixed; `RefundAmountCorrect` và `ReplyMatchesLedger` đều True trên seeded (chứng minh grader outcome không thấy lỗi); assert bước sai là #5 `proposal 0` ngay sau #4 `refund_history`. Đã chạy: 3/3 pass. Trên toàn bộ `seeded_regression`, thêm `quote_kept` nâng `mutation --detect` từ 75% lên 100% (báo nhầm 0%) |
| Chưa chắc chắn | Trace không ghi phản hồi của host (variant không log kết quả `issue_refund`); việc host sẽ từ chối được suy ra từ run `fixed` và policy `cap_per_order`, không có trong chính trace này. Với LLM thật, số được trừ có thể khác 100% → proposal ≠ 0 và host bị gọi; khi đó lỗi giống C-014 (ledger 90.000) và `refund_amount_correct` cũng bắt |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
