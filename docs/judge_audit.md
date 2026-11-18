# Judge audit

Chạy (trong `src/`): `python -m lab9.judge --csv <file> --audit 5`. Judge chạy ở chế độ replay: verdict đã lưu sẵn trong CSV, không gọi model. FAIL là lớp dương.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (exit 0) | **dùng**, chỉ cho giọng điệu |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không: κ < 0.6, R < 0.7 (exit 1) | **loại** |

| Tiêu chí | Ma trận nhầm lẫn (tp / fp / fn / tn) | Tỉ lệ FAIL quan sát → hiệu chỉnh Rogan-Gladen |
|---|---|---|
| tone_ok | 24 / 4 / 6 / 66 (specificity 0.943) | 0.28 → 0.30 |
| helpful | 9 / 0 / 21 / 70 (specificity 1.000) | 0.09 → 0.30 |

Theo loại lỗi (cột `human_failure`): judge helpful bắt đủ 9/9 lỗi nhìn được từ chính câu chữ ("giọng cụt" 4, "không hỏi lại mã đơn" 3, "trả lời lạc đề" 2), nhưng bỏ sót 18/18 lỗi "sai tiền" và 3/3 lỗi "sai xưng hô".
Với helpful, judge thấy 9% câu trả lời lỗi trong khi thực tế là 30%: nó đếm thiếu 3 lần. P = 1.0 vì không báo nhầm lần nào, nhưng bỏ sót 21/30 lỗi, nên làm gate với judge này nghĩa là cho qua 70% câu trả lời lỗi.

## ≥5 case audit thủ công (10 bất đồng của tone_ok + nhóm lỗi của helpful)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | "em… nha" quá suồng sã với khách khiếu nại. Thêm vào rubric: xưng "LogiX/anh/chị", cấm "em… nha", kèm ví dụ âm. |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…" | PASS | FAIL | Người | Không gọi khách là "bạn"; cùng quy tắc xưng hô như #1. |
| 3 | H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Judge chỉ nhìn phần mở đầu lịch sự. Rubric phải chấm cả câu và liệt kê các cụm mệnh lệnh ("không cần nhắn thêm"). |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…" | FAIL | PASS | Người | Judge phạt vì không có lời xin lỗi. Ghi rõ: đã giải quyết xong thì xin lỗi không bắt buộc. |
| 5 | H-051 "LogiX đã refund 90.000đ…" | FAIL | PASS | Người | CS LogiX cho phép từ "refund". Thêm whitelist thuật ngữ vào rubric. |
| 6 | H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | Người | Lỗi ở đây không phải giọng mà là hứa ngoài kết quả hệ thống, tức lỗi nội dung/tiền. Chuyển sang grader code (reply ↔ ledger), không để trong tone. |
| 7 | H-070 "…ạ 😂😂" | PASS | FAIL | Người | Cấm emoji trong ngữ cảnh khiếu nại. |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện…" | FAIL | PASS | **Judge** | Người gán nhãn đọc nhầm ticket. Sửa nhãn vàng; rubric giữ nguyên. |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ…" | FAIL | PASS | Người | Lặp chữ do gõ nhầm, giọng vẫn lịch sự. Rubric: lỗi gõ nhẹ không tính là FAIL tone. |
| 10 | H-094 "Da, LogiX da hoan 40.000đ…" | PASS | FAIL | Người | Mất dấu tiếng Việt (dịch máy) là thiếu chuyên nghiệp. Thêm vào rubric: không dấu = FAIL. |
| 11 | helpful HL-015, HL-020, HL-087… (18 dòng "sai tiền") | PASS | FAIL | Người | Reply nêu số tiền khác ledger (ví dụ HL-020 nói 90.000đ, ledger 120.000đ). Judge chỉ đọc reply nên **không thể** biết ledger. Phần này chuyển sang code: `ReplyMatchesLedger` (`reply_matches_ledger`, min 1.0). |
| 12 | helpful HL-047, HL-091, HL-097 ("Ok bạn, … xử lý rồi nhé") | PASS | FAIL | Người | Sai xưng hô, đúng ra thuộc tiêu chí tone (đã calibrate). Bỏ khỏi helpful. |

## Kết luận
- **helpful bị loại**: κ 0.375, R 0.300 (bỏ sót 21 trong 30 FAIL; 18 trong số đó là "sai tiền"). Lỗi cấu trúc chứ không phải lỗi prompt: tiêu chí này cần ledger, mà judge chỉ thấy reply. Tiền luôn chấm bằng code, nên phần "sai tiền" là `reply_matches_ledger`, metric blocking trong `metric_spec.yaml` 1.1 và `metric_spec_v2.yaml`.
- **tone_ok dùng được** (κ 0.757, P 0.857, R 0.800), nhưng chỉ cho giọng điệu, không bao giờ cho tiền hay approval, và không đưa vào gate release. Áp các sửa đổi rubric #1–#10 rồi calibrate lại trên nhãn mới.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng mỗi tiêu chí). Cần nhãn người mới làm held-out thật trước khi tin vào κ 0.757. Một judge hằng số (κ không xác định hoặc 0) sẽ FAIL floors: `stats.cohen_kappa` raise khi p_e = 1, còn `rogan_gladen` trả NaN khi sens + spec ≤ 1.
