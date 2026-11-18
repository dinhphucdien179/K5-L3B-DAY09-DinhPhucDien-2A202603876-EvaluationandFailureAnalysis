# Báo cáo Lab 9 — Evaluation & Failure Analysis (LogiX-VN refund agent)

Câu hỏi: *làm sao biết bản mới tốt hơn, và chặn được bản tệ trước khi merge?*. Repo này có bộ eval (pydantic-evals, MockLLM, không cần API key), các grader bằng code, bộ thống kê (κ, Rogan-Gladen, paired bootstrap, pass@k / pass^k) và một **gate** quyết định merge (exit 0) hay chặn (exit 1). Gate fail closed: report đáng ngờ thì chặn.

Tài liệu chi tiết: [`docs/failure_taxonomy.md`](docs/failure_taxonomy.md) · [`docs/judge_audit.md`](docs/judge_audit.md) · [`docs/trace_case.md`](docs/trace_case.md) · [`docs/eval_card.md`](docs/eval_card.md) · [`docs/PRD_v1.1.md`](docs/PRD_v1.1.md) · [`docs/bonus_inspect.md`](docs/bonus_inspect.md). Đề bài gốc: [`README.md`](README.md), [`RUBRIC.md`](RUBRIC.md).

---

## 1. Kết quả tóm tắt

| Hạng mục | Yêu cầu | Kết quả đo được | Kiểm bằng (trong `src/`) |
|---|---|---|---|
| M1 Taxonomy + eval set | ≥ 5 FM có bằng chứng trace; `--check` sạch | 9 FM: 8 có trace lỗi thật hoặc probe, FM-09 do host chặn; 14 item có `failure_modes`, 0 problem | `python -m lab9.evalset --check` |
| M2 Calibration | tone dùng được, helpful thì không; audit ≥ 5 ca | tone κ 0.757, P 0.857, R 0.800 → PASS · helpful κ 0.375, R 0.300 → FAIL (bỏ sót 18/18 lỗi "sai tiền") · audit 12 ca | `python -m lab9.judge ...` |
| M3 Trajectory | 2 grader + metric FM-08; phát hiện ≥ 80%, báo nhầm ≤ 10% | **100% / 0%** (có thêm grader `quote_kept`; thiếu nó chỉ đạt 75%) | `python -m lab9.mutation --detect` |
| M4 Bootstrap + gate | CI lệch ≤ 0.01; chặn `seeded_regression`, cho qua `fixed` | `pass_rate` Δ −0.271, CI [−0.500, −0.057], khớp tham chiếu · `fixed` exit 0 · `seeded_regression` exit 1 | `python -m lab9.gate ...` |
| Eval card + PRD v1.1 | số liệu khớp report có run_id; nêu giới hạn | đủ, dẫn run ID `E-*-20261118-*` | `docs/` |
| M5 Eval set v2 + slices | `fm_map`; ≥ 3 item/FM; slice `money_movement` và `adversarial` | 28 item, 0 problem; `slice_regression` bị chặn ở `slice:money_movement` (0.850 < 0.90) | `python -m lab9.evalset --v2` |
| M6 Nhiễu | `pass_at_k` / `pass_hat_k`; sàn ngoài dải A/A | A/A Δ = 0 trên mọi metric; sàn `pass_hat_5` = 0.85 (baseline 0.8929); `flaky_regression` 0.5714 → chặn | `python -m lab9.mutation --aa ...` |
| M7 Chống gian lận eval | integrity + ratchet; mọi trap bị chặn | 4/4 trap → `INTEGRITY`; scorecard 3/3, báo nhầm 0; thêm 14 regression giả lập kiểu "variant ẩn" đều bị chặn, 3 refactor trung thực đều merge | `python -m lab9.mutation ...`, `python -m lab9.traps ...` |
| Bonus | port grader sang Inspect AI / DeepEval | 3 grader trên Inspect AI khớp 100% với pydantic-evals (210/210, 210/210, 420/420, 420/420) | `python -m bonus.inspect_port ...` |
| Test | — | core 28 pass · advanced 33 pass · Lab 8 57 pass · `src/lab8/` không đổi | `python -m pytest ...` |

## 2. Những gì đã làm

| File | Nội dung |
|---|---|
| `src/lab9/stats.py` | confusion / P-R / κ (số nguyên chính xác, raise khi p_e = 1) / Rogan-Gladen (NaN nếu judge không hơn đoán mò) / paired bootstrap (scipy, percentile) / pass@k, pass^k (`math.comb`, từ chối (n, c, k) sai) |
| `src/lab9/graders.py` | `ApprovalBypass`, `RefundAmountCorrect`, **`ReplyMatchesLedger`** (FM-08), **`QuoteKept`** (FM-04/05) |
| `src/lab9/evalset.py` | `failure_modes` cho 14 item (`FAILURE_MODES_V1`); ghi file với `newline="\n"` để SHA giống nhau trên mọi hệ điều hành |
| `src/lab9/gate.py` | `slice_check` (M5) và `integrity_check` (M7): kiểm cấu trúc, dòng trùng, NaN, evaluator failures, summary phải tái tạo được từ dòng, slice tag, ratchet |
| `src/config/metric_spec.yaml` (1.1), `metric_spec_v2.yaml` (2.0), `fm_map.yaml` | ngưỡng chọn từ số đo (xem `docs/eval_card.md`) |
| `src/data/eval/eval_set_v1.jsonl`, `eval_set_v2.jsonl`, `labels_v2.json` | sinh bằng `lab9.evalset`, nhãn tách khỏi item |
| `src/harness_map.yaml` (1.2) | thêm section `eval` |
| `src/tests/test_lab9_own_graders.py`, `test_lab9_trace_case.py`, `test_lab9_advanced_integrity.py` | test của grader mới, regression test của trace case, các vector integrity tự viết |
| `src/bonus/inspect_port.py`, `src/requirements-bonus.txt` | bonus Inspect AI (không chạy trong CI) |
| `.gitattributes` | giữ eval set ở LF trên Windows để SHA không đổi |
| `src/reports/*.json` | report do script sinh: baseline v1/v2, fixed, seeded, slice/flaky/honest v2 |

Ba quyết định chính, chi tiết trong `docs/eval_card.md`:
1. **Thêm `quote_kept`** (số tiền gửi host phải đúng bằng quote của code). Ở trace case `seeded_regression C-013@11`, ledger, status và reply đều khớp nhãn nên grader outcome không thấy lỗi; bước sai là event #5 `proposal 0`.
2. **`reply_matches_ledger` = 1.0**: baseline và A/A đều đúng bằng 1.0. Nếu đặt 0.95 thì một lỗi misreport chỉ xảy ra ở 1/5 seed (0.957) sẽ lọt.
3. **Gate fail closed**: thứ tự kiểm là eval set SHA → integrity → metric → slice. Report không tin được thì không bao giờ đến bước so ngưỡng.

---

## 3. Cài đặt

### 3.1 Yêu cầu
- **Git** và **Python 3.11 – 3.13** (đã kiểm trên 3.12; CI dùng 3.13). Không cần API key hay GPU; chỉ cần Internet khi cài gói.
- **Mọi lệnh Python chạy trong thư mục `src/`** của repo, vì code đọc `data/`, `config/` và `reports/` theo đường dẫn tương đối.
- Các lệnh trong mục 3–5 giống hệt nhau trên Windows, macOS và Linux, trừ phần tạo/kích hoạt môi trường (có ghi riêng). Mỗi lệnh nằm trên một dòng, không dùng `&&`, nên chạy được cả trong PowerShell 5.

### 3.2 Lấy mã nguồn
```bash
git clone <URL-của-repo-này>
cd <thư-mục-repo-vừa-clone>
```

### 3.3 Lựa chọn 1: `venv` (có sẵn trong Python)

**Linux / macOS** (bash, zsh):
```bash
cd src
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-lab9.txt
```

**Windows** (PowerShell):
```powershell
cd src
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-lab9.txt
```
- Không có lệnh `py`: dùng `python -m venv .venv`.
- PowerShell chặn `Activate.ps1`: chạy `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` một lần rồi kích hoạt lại.
- Dùng CMD thay cho PowerShell: kích hoạt bằng `.venv\Scripts\activate.bat`.
- Thoát môi trường: `deactivate`. Thư mục `src/.venv/` đã nằm trong `.gitignore`.

### 3.4 Lựa chọn 2 (khuyến nghị): `conda`
Khuyến nghị vì mỗi env có trình thông dịch Python riêng (không phụ thuộc Python của máy), lệnh giống nhau trên cả ba hệ điều hành, và hỏng thì xoá đi tạo lại được.

**Linux / macOS / Windows** (Terminal; trên Windows dùng *Anaconda Prompt*, hoặc PowerShell sau khi đã chạy `conda init powershell` rồi mở lại cửa sổ):
```bash
conda create -n lab9 python=3.12 -y
conda activate lab9
cd src
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-lab9.txt
```
Tên env `lab9` đặt tuỳ ý. Xoá env: `conda deactivate`, rồi `conda remove -n lab9 --all -y`.

### 3.5 Trên Windows: bật UTF-8 (khuyến nghị, CI cũng bật)
Output có tiếng Việt và ký tự `Δ`. Đặt biến này trong cửa sổ terminal đang dùng:
```powershell
$env:PYTHONUTF8 = "1"        # PowerShell
```
```bat
set PYTHONUTF8=1             :: CMD
```

### 3.6 Bonus (tuỳ chọn, CI không cần)
```bash
python -m pip install -r requirements-bonus.txt
```
Gói này cài `inspect-ai` và khoảng 40 gói phụ thuộc, đồng thời hạ `fsspec` và `python-dateutil` xuống bản mà `inspect-ai` yêu cầu. Nếu env của bạn dùng chung cho việc khác, hãy tạo một env riêng cho bonus.

### 3.7 Kiểm tra cài đặt
```bash
python -m lab9.smoke
```
Kết quả mong đợi: dòng cuối là `M0 PASS`.

---

## 4. Quy trình chạy đầy đủ (trong `src/`, khoảng 2–3 phút)

Các lệnh chạy lại **ghi report vào `reports/local/`**: thư mục này bị git bỏ qua, nên report đã commit (`reports/baseline_v1.json`, `reports/baseline_v2.json`, …) giữ nguyên và vẫn dùng làm baseline. Lần chạy đầu sẽ sinh thêm thư mục `traces/` (cũng bị git bỏ qua).

Xem exit code của lệnh vừa chạy: bash/zsh `echo $?` · PowerShell `echo $LASTEXITCODE` · CMD `echo %ERRORLEVEL%`. Một số bước **phải** trả exit 1, đã đánh dấu bên dưới.

### 4.1 Test
```bash
python -m pytest -q -m student -o addopts= -k "lab9 and not advanced"
python -m pytest -q -m student -o addopts= -k advanced
python -m pytest -q
```
Mong đợi: `28 passed` · `33 passed` · `57 passed` (bộ test mặc định của Lab 8 cùng test eval set).

### 4.2 M1: eval set v1
```bash
python -m lab9.evalset --check
```
Mong đợi: `eval set 9fa58be2f6d3: 0 problem(s)`. Muốn sinh lại thì chạy `python -m lab9.evalset --build` rồi `--check`; file sinh ra giống hệt từng byte, SHA không đổi.

### 4.3 M2: calibrate judge
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```
Mong đợi: tone in `n=100 P=0.857 R=0.8 kappa=0.757` rồi `PASS floors` (exit 0). Helpful in `n=100 P=1.0 R=0.3 kappa=0.375` rồi `FAIL floors` (**exit 1 là đúng**: judge này bị loại).

### 4.4 M3: grader phát hiện lỗi
```bash
python -m lab9.mutation --detect
```
Mong đợi: `detection 100.00% (target >=80%) · false alarms 0.00% (target <=10%)` (exit 0).

### 4.5 M4: eval + gate (so với baseline v1 đã commit)
```bash
python -m lab9.eval --shape swarm --out reports/local/eval_pr.json
python -m lab9.gate --pr reports/local/eval_pr.json --baseline reports/baseline_v1.json
python -m lab9.ci_check --pr reports/local/eval_pr.json --baseline reports/baseline_v1.json --spec config/metric_spec.yaml
python -m lab9.eval --shape fixed --out reports/local/eval_fixed.json
python -m lab9.gate --pr reports/local/eval_fixed.json --baseline reports/baseline_v1.json
python -m lab9.eval --shape seeded_regression --out reports/local/eval_seeded_regression.json
python -m lab9.gate --pr reports/local/eval_seeded_regression.json --baseline reports/baseline_v1.json
```
Mong đợi:
- `eval` in run ID dạng `E-<shape>-<ngày chạy>-9fa5` cùng các metric. `swarm`: `pass_rate 0.9857`, `reply_matches_ledger 1.0`, `quote_kept 1.0`.
- Gate swarm: `exit 0 — merge`. `ci_check`: `exit 0 — baseline and spec look sound` (baseline đã commit trùng khớp với lần chạy lại).
- Gate fixed: `exit 0 — merge`.
- Gate seeded_regression (**exit 1 là đúng**): dòng `pass_rate … Δ -0.271 CI [-0.500, -0.057] BLOCK` và dòng cuối `exit 1 — blocked: refund_amount_correct, pass_rate, reply_matches_ledger, quote_kept`.

### 4.6 Trace case
```bash
python -m lab9.trace_case --shape seeded_regression --claim C-013 --seed 11
python -m lab9.trace_case --shape fixed --claim C-013 --seed 11
```
Mong đợi: bản seeded báo `lab8 grader: FAIL (proposal_mismatch)` và event `5 proposal {"amount_vnd": 0}`; bản fixed báo `PASS (ok)` và không có event `proposal`.

### 4.7 M5: eval set v2 + slice (so với baseline v2 đã commit)
```bash
python -m lab9.evalset --v2
python -m lab9.eval --shape fixed --spec config/metric_spec_v2.yaml --out reports/local/eval_fixed_v2.json
python -m lab9.gate --pr reports/local/eval_fixed_v2.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
python -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/local/eval_slice_regression.json
python -m lab9.gate --pr reports/local/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
```
Mong đợi:
- `eval set v2 283b33954134: 0 problem(s)`.
- Gate fixed v2: `exit 0 — merge`.
- Gate slice_regression (**exit 1 là đúng**): `pass_rate 0.9357` vẫn trên sàn và CI chạm 0, nhưng `slice:money_movement/pass_rate 0.8500 … BLOCK`. Dòng cuối `exit 1 — blocked: quote_kept, slice:money_movement/pass_rate`.

### 4.8 M6: nhiễu A/A
```bash
python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
```
Mong đợi: cột `delta` bằng `+0.0000` ở mọi metric (`pass_hat_5 0.8929` ở cả hai bộ seed).

### 4.9 M7: scorecard + trap
```bash
python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
python -m lab9.traps --pr reports/local/eval_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml --out reports/local/traps
python -m lab9.gate --pr reports/local/traps/dropped_failing_rows.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
python -m lab9.gate --pr reports/baseline_v2.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml --base-spec config/metric_spec_v2.yaml
```
Mong đợi:
- Scorecard (khoảng 25 s): `fixed` và `honest_refactor` → merge; 3 regression → block; dòng cuối `mutation score 3/3 · false alarms 0` (exit 0).
- Traps: 4 dòng `blocked`, dòng cuối `exit 0 — the gate blocked every public trap`.
- Gate trên một trap (**exit 1 là đúng**): các dòng `INTEGRITY …` rồi `exit 1 — blocked: integrity`.
- Baseline so với chính nó: `exit 0 — merge`.

### 4.10 Bonus: Inspect AI (cần mục 3.6)
```bash
python -m bonus.inspect_port --shape seeded_regression
python -m bonus.inspect_port --shape fixed
python -m bonus.inspect_port --shape slice_regression --spec config/metric_spec_v2.yaml
python -m bonus.inspect_port --probe sibling_refund,misreport,ignore_denied --spec config/metric_spec_v2.yaml
```
Mong đợi: mỗi lệnh in bảng 3 metric với cột `agree` đầy đủ (vd `70/70`), dòng cuối `exit 0 — every verdict agrees`.

---

## 5. Sinh lại report để commit (chỉ chủ repo)
Report trong `src/reports/` do script sinh, **không sửa tay**. `.gitignore` bỏ qua thư mục này nên phải thêm bằng `-f`. Run ID chứa ngày chạy: nếu sinh lại thì phải cập nhật run ID trong `docs/`.
```bash
python -m lab9.eval --shape swarm --out reports/baseline_v1.json
python -m lab9.eval --shape fixed
python -m lab9.eval --shape seeded_regression
python -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
python -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_slice_regression.json
cd ..
git add -A
git add -f src/reports/*.json
```
Quy trình nộp (PR trong bản fork, CI xanh rồi merge) nằm ở [`SUBMISSION.md`](SUBMISSION.md).

## 6. Xử lý sự cố

| Triệu chứng | Nguyên nhân / cách sửa |
|---|---|
| `M0 FAIL (run from src/)`, `ModuleNotFoundError: No module named 'lab8'`, `FileNotFoundError: data/...` | Chưa đứng trong `src/`. Chạy `cd src` rồi chạy lại. |
| Gate báo `EVAL SET differs from the baseline's` | Eval set bị đổi byte, thường do bị chuyển xuống dòng thành CRLF trên Windows hoặc bị sửa tay. `.gitattributes` đã giữ LF cho file mới clone; với bản clone cũ, chạy `git checkout -- src/data/eval` (đứng ở thư mục gốc repo) hoặc `python -m lab9.evalset --build`. |
| PowerShell báo không chạy được script `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, rồi kích hoạt lại. |
| `conda activate` không chạy, hoặc `conda: command not found` | Chạy `conda init bash`, `conda init zsh` hoặc `conda init powershell` (tuỳ shell), đóng rồi mở lại terminal. |
| Nạp nhầm gói hoặc nhầm phiên bản từ env khác | Biến `PYTHONPATH` đang trỏ sang env khác. Bỏ nó đi: bash/zsh `unset PYTHONPATH` · PowerShell `Remove-Item Env:PYTHONPATH` · CMD `set PYTHONPATH=`. |
| Lỗi mã hoá ký tự, chữ Việt bị vỡ trên Windows | Đặt `PYTHONUTF8=1` (mục 3.5). |
| `python` gọi nhầm Python 2 hoặc Python hệ thống | Kích hoạt env trước (`source .venv/bin/activate` / `conda activate lab9`), sau đó mới dùng `python`. |
| Python 3.10 trở xuống | Không hỗ trợ. Dùng 3.11 – 3.13. |
| Helpful judge, gate `seeded_regression`, gate `slice_regression` hoặc gate trên trap trả exit 1 | **Đúng như thiết kế**: đó là các bước kiểm chứng gate *chặn*. |
| `ModuleNotFoundError: No module named 'inspect_ai'` | Chỉ ảnh hưởng bonus. Cài theo mục 3.6. |

## 7. Giới hạn
Đo trên MockLLM (có seed), chưa phải LLM thật hay người dùng thật. 14/28 item nên CI rộng. Judge chạy replay trên CSV công khai. Bug chỉ xảy ra ở 1/5 seed trên vài item, đúng bằng cỡ điểm yếu `seed % 5` của baseline, thì không phân biệt được. Integrity không phát hiện được một report "nhất quán giả" (dòng và summary bị sửa khớp với nhau); cách phòng thật là CI tự chạy eval, đúng như job `eval-gate` đang làm. Chi tiết ở `docs/eval_card.md` và `docs/PRD_v1.1.md`.
