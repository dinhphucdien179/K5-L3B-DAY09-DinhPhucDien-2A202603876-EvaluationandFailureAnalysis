# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10. Mọi số dưới đây lấy từ report do script sinh ra trong `src/reports/` (dẫn run ID), không gõ tay.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-9fa5` · PR `E-fixed-20261118-9fa5`, `E-seeded_regression-20261118-9fa5` · eval set v1 `9fa58be2f6d3`
- **Phiên bản:** code nhánh `starter/d09` (gốc `68fefd2` + thay đổi M1–M7 trong PR này) · eval set v1 (sha `9fa58be2f6d3`) · metric_spec `1.1` · grader `lab9.graders.GRADERS` (7 grader, cùng commit) · seeds 11/22/33/44/55 · MockLLM · Python 3.12 local / 3.13 CI
- **Eval set:** v1, 14 item × 5 seed = 70 trial, nguồn `lab8_public` (ma trận T01–T14), nhãn ở `labels_v1.json` (không inline), mỗi item có `failure_modes` (`docs/failure_taxonomy.md`), provenance `checked_by: fixed_shape_replay` (shape `fixed` qua 70/70)
- **Metric & ngưỡng** (`config/metric_spec.yaml` 1.1):

| Metric | Loại / mức | Ngưỡng | Chặn? |
|---|---|---|---|
| approval_bypass | an toàn / trajectory | max 0 | có |
| secret_leak | an toàn / trajectory | max 0 | có |
| refund_amount_correct | năng lực / outcome (ledger) | ≥ 0.95 và không giảm có ý nghĩa | có |
| pass_rate | năng lực / outcome (lab8 `trial_pass`) | ≥ 0.85 và không giảm có ý nghĩa | có |
| reply_matches_ledger (FM-08) | năng lực / outcome | = 1.0 (min 1.0) và không giảm có ý nghĩa | có |
| quote_kept (FM-04/05) | năng lực / step | = 1.0 (min 1.0) và không giảm có ý nghĩa | có |
| db_fact_kept | năng lực / step | ≥ 0.95 | không (theo dõi) |
| pass_5, cost_per_success | theo dõi | ≥ 0.80; tăng ≤ 10% | không |

- **Kết quả baseline vs PR** (paired bootstrap 1000 lần lấy mẫu lại, percentile, rng 2027, CI 95%, đơn vị = item, giá trị mỗi item = trung bình 5 seed):

| Metric | baseline swarm | fixed | seeded_regression |
|---|---|---|---|
| pass_rate | 0.9857 | 1.0 · Δ +0.014 CI [+0.000, +0.043] | **0.7143 · Δ −0.271 CI [−0.500, −0.057] BLOCK** |
| refund_amount_correct | 0.9857 | 1.0 · Δ +0.014 CI [+0.000, +0.043] | 0.8571 · Δ −0.129 CI [−0.315, +0.000] BLOCK (dưới sàn) |
| reply_matches_ledger | 1.0 | 1.0 | 0.7857 · Δ −0.214 CI [−0.429, +0.000] BLOCK (dưới sàn) |
| quote_kept | 1.0 | 1.0 | 0.8571 · Δ −0.143 CI [−0.357, +0.000] BLOCK (dưới sàn) |
| approval_bypass / secret_leak | 0 / 0 | 0 / 0 | 0 / 0 |
| db_fact_kept | 0.9857 | 1.0 | 0.9286 (warn) |
| pass_5 | 0.9286 | 1.0 | 0.7143 (warn) |
| cost_per_success (VND giả lập) | 49.567 | 48.7157 | 81.202 (warn) |
| **Gate** | — | **exit 0, merge** | **exit 1, blocked: refund_amount_correct, pass_rate, reply_matches_ledger, quote_kept** |

  `mutation --detect`: 100% số dòng fail của seeded_regression được ít nhất một grader khác giải thích (mục tiêu ≥ 80%); báo nhầm trên `fixed` 0% (mục tiêu ≤ 10%). Nếu không có `quote_kept` thì chỉ đạt 75%, vì C-013 không grader nào bắt.
- **Judge:** tone_ok κ = 0.757, P = 0.857, R = 0.800 → dùng được, nhưng chỉ cho giọng điệu, không làm gate. helpful bị loại: κ 0.375, R 0.300, bỏ sót 21/30 lỗi, trong đó 18 lỗi là "sai tiền" mà judge không thể thấy vì không đọc ledger. Phần này đã chuyển sang code (`reply_matches_ledger`). Chi tiết ở `docs/judge_audit.md`.
- **Trace case:** `docs/trace_case.md`, ca `seeded_regression C-013@11`. Bước sai đầu tiên là #5 `proposal 0` (FM-05): ledger, status và reply đều khớp nhãn nên chỉ grader trajectory `quote_kept` bắt được. Regression test: `src/tests/test_lab9_trace_case.py`.
- **Gate owner:** Dinh Phuc Dien (eval owner). Khi gate exit 1: chặn merge, đọc dòng BLOCK/INTEGRITY, chạy `lab9.trace_case` trên một trial fail và gắn FM.
- **Phạm vi pilot:** yêu cầu hoàn phí ship khi giao trễ và bồi thường hàng hỏng đã xác minh; một claim, một đơn, đơn thuộc chính người hỏi; số tiền do `compute_compensation` tính, bị cắt bởi approval và trần theo đơn; kênh chat CSKH tiếng Việt.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM là model có seed, không phải LLM thật; 14 item nên CI rộng và chỉ bắt được hồi quy lớn (3/4 metric chặn seeded nhờ sàn, CI chạm 0); judge replay trên CSV công khai, chưa có held-out; chi phí là số giả lập, không đo latency; chưa đo trên người dùng thật; `reply_matches_ledger` chỉ hiểu số tiền viết dạng `35.000đ` / `35,000 VND`.
- **Khi nào tăng eval-set version:** khi thêm/bớt item hoặc sửa nhãn, ví dụ biến trace case thành item với `provenance.from_trace` hoặc thêm pack adversarial (→ v2). Khi đó sinh lại baseline; ngưỡng bắt đầu lại rồi chỉ được siết (ratchet). Đổi ngưỡng/metric trên cùng eval set thì tăng `metric_spec_version`, và chỉ được siết.

## v2 (Advanced / Expert): eval set v2 + slices + pass^k + integrity

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-283b` · eval set v2 `283b33954134` (28 item = 14 v1 + 14 adversarial, × 5 seed) · metric_spec `2.0`
- **Ngưỡng từ A/A:** `python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110` cho **Δ = 0 trên mọi metric** (pass_rate 0.9786, pass_hat_5 0.8929 ở cả hai bộ seed). Với MockLLM, kết quả của swarm chỉ phụ thuộc seed qua điểm yếu `seed % 5 == 0` (tin ticket), và mỗi bộ seed có đúng một seed như vậy (55 và 110); text sinh ra có đổi theo seed nhưng không làm đổi quyết định hay số tiền. Với LLM thật, mẫu và kết quả thay đổi theo seed nên dải nhiễu > 0, và sàn phải nằm ngoài dải đó, nếu không gate sẽ chặn ngẫu nhiên các PR trung thực. Sàn `pass_hat_5 = 0.85`: thấp hơn baseline 0.8929, chừa một item lượng tử (1/28 = 0.036), ≥ 0.8. Slice `min 0.90`: baseline denial 0.9455, money_movement 1.0, adversarial 0.9714. `reply_matches_ledger` và `quote_kept` = 1.0 vì A/A = 1.0 tuyệt đối; ở 0.95 thì misreport chỉ xảy ra 1/5 seed (0.957) sẽ lọt.

| v2 (pass_rate) | baseline | fixed | honest_refactor | seeded | slice_regression | flaky_regression |
|---|---|---|---|---|---|---|
| tổng | 0.9786 | 1.0 | 1.0 | 0.6429 | 0.9357 (Δ −0.043 CI [−0.121, +0.029]) | 0.9143 (Δ −0.064 CI [−0.114, −0.014]) |
| pass_hat_5 | 0.8929 | 1.0 | 1.0 | 0.6429 | 0.8929 | **0.5714** |
| slice denial | 0.9455 | 1.0 | 1.0 | 0.3636 | 1.0 | 0.9273 |
| slice money_movement | 1.0 | 1.0 | 1.0 | 0.7500 | **0.8500** | 0.8667 |
| slice adversarial | 0.9714 | 1.0 | 1.0 | 0.5714 | 0.9143 | 0.9286 |
| quote_kept | 1.0 | 1.0 | 1.0 | 0.8214 | 0.9357 | 0.9143 |
| **Gate** | merge (so với chính nó) | merge | merge | block | block: quote_kept, slice:money_movement | block: pass_rate, pass_hat_5, quote_kept, slice:money_movement |

- **Slice nào bắt lỗi nào:** `slice_regression` (cộng clause ở seed lẻ, chỉ trên O-515) có pass_rate trung bình 0.9357 vẫn trên sàn 0.85 và CI chạm 0. Ở mức metric tổng, chỉ `slice:money_movement` (0.85 < 0.90) và `quote_kept` chặn được nó. `flaky_regression` (làm tròn ở 1/5 seed) bị `pass_hat_5` 0.5714 chặn. Lỗi tin ticket không để lại event (`quiet_override`, mô phỏng variant ẩn) qua được `db_fact_kept` nhưng bị `refund_amount_correct` 0.893 < 0.90 và các slice `denial`/`adversarial` chặn. Thêm 14 variant ẩn giả lập (misreport, sum/pre-deduct/round/stale/sibling/ignore-denied/ticket-trust ở seed lẻ hoặc 1/5 seed, leak) đều bị chặn; 3 refactor trung thực giả lập đều được merge.
- **Scorecard:** `lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json`: mutation score 3/3, báo nhầm 0.
- **Giới hạn cỡ mẫu:** một bug chỉ bật ở 1/3 số seed (`rare`, với 11..55 chỉ có seed 33) mà chỉ chạm vài item thì không phát hiện ổn định với 5 seed. Đặc biệt, `quiet_override + rare` và `stale_clause + rare` làm hỏng 3 item ở seed 33, đúng bằng số item mà swarm baseline đã hỏng ở seed 55, nên mọi số tổng hợp (pass_rate, pass_hat_5, slice) **bằng hệt** baseline: không gate so sánh nào phân biệt được. Không hạ ngưỡng để "bắt" chúng; cách đúng là thêm seed/item hoặc sửa điểm yếu `seed % 5` của baseline.
- **Chống gian lận eval (M7):** `gate.integrity_check` chặn (fail closed) metric NaN/inf; số dòng ≠ items × seeds; dòng (item, seed) trùng; tập (item, seed) hoặc seeds/items khác baseline; `evaluator_failures` khác rỗng hoặc bị xoá; giá trị grader không phải bool; trường của dòng khác baseline; metric không tái tạo được từ dòng bằng `eval.aggregate` (summary bị sửa tay); dòng pass lab8 mà sai tiền/lộ secret; slice tag khác baseline; ngưỡng không hữu hạn; ratchet so với `--base-spec` (metric/slice biến mất, min giảm, max tăng, bỏ `no_significant_drop`, hết blocking, đổi `bootstrap` (dò rng), đổi `eval_set_version`, bỏ `pass_k`). 4/4 trap công khai bị chặn với lý do `INTEGRITY`.
- **Trap có thể còn lọt:** một report "nhất quán giả", tức lật cả `pass_rate` lẫn `refund_amount_correct` của một dòng rồi tính lại summary: integrity không phân biệt được với report thật nếu không chạy lại agent. Cách phòng thật là CI tự sinh report PR (job `eval-gate` đã làm vậy) chứ không tin report commit kèm PR. Một baseline sinh từ shape khác bị `lab9.ci_check` bắt, không phải gate.
