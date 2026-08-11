# Báo cáo Day 13 Observability

> Điền dần theo tiến độ. Chỗ nào còn `_(chờ OBS-xx)_` là chưa có dữ liệu thật, **không điền số phỏng đoán**.

## 1. Thông tin nhóm

- Tên nhóm: K4-F5-1
- Repository URL: https://github.com/Mrgintamago/Day13-K4-F5-1
- Commit SHA cuối: _(chờ OBS-54 — chốt SHA ngay trước khi nộp)_
- Thành viên và vai trò:

| Thành viên | MSSV | Vai trò |
|---|---|---|
| Nguyễn Xuân Quang | 2A202601776 | Logging & PII + Tech lead |
| Trần Quang Sáng | 2A202601446 | Tracing & Prompt Version |
| Lưu Nguyễn Ngọc Hân | 2A202601386 | Dashboard, SLO & Alert |
| Cao Các Tường | 2A202601236 | Incident Report, Evidence & Demo |

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: baseline **30/100** → hiện tại **100/100** (4/4 mục PASSED).
  Baseline: `submission/evidence/00-baseline-validate-logs.txt` · Sau khi sửa: `submission/evidence/01-validate-logs.txt`
- Tổng số traces: **66** trên Langfuse (yêu cầu tối thiểu 10), sinh bằng 2 lượt
  `python scripts/load_test.py --concurrency 5`
- Số PII leak còn lại: **0** — `Potential PII leaks detected: 0`
- Link/đường dẫn dashboard: _(chờ OBS-30)_

Chi tiết baseline → hiện tại:

| Hạng mục | Baseline | Hiện tại |
|---|---:|---:|
| Records thiếu required field | 60 | 0 |
| Records thiếu enrichment | 60 | 0 |
| Correlation ID duy nhất | 0 | 11 |
| PII leak | 0 | 0 |
| **Điểm** | **30/100** | **100/100** |

## 3. Logging và tracing

- Evidence correlation ID: `submission/evidence/02-log-correlation-id.txt` — mỗi record `service=api`
  có `correlation_id` dạng `req-<8 hex>`, kèm `user_id_hash`, `session_id`, `feature`, `model`, `env`.
  Response trả về header `x-request-id` và `x-response-time-ms`; nếu client tự gửi `x-request-id`
  thì server giữ nguyên ID đó để khách hàng báo lỗi kèm ID là tra ra được request.
- Evidence PII redaction: `submission/evidence/02b-log-pii-redacted.txt`. Đã kiểm chủ động bằng một
  request chứa email, số điện thoại VN, CCCD, số thẻ, passport và địa chỉ — log chỉ còn
  `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`,
  `[REDACTED_PASSPORT]`, `[REDACTED_ADDRESS_VN]`, không còn chuỗi nguyên văn nào.
- Evidence trace waterfall: `submission/evidence/04c-trace-waterfall.png` (một trace đầy đủ) và
  `submission/evidence/04b-traces-list.png` (danh sách, lọc theo tag `deepseek-v4-pro`:
  44 observation type GENERATION + 44 type SPAN).
- Giải thích một span đáng chú ý: trace `b90d099f068854c7f281456af859d499` (session `s10`,
  user `105a9cef3903` — đã hash) có **2 observation**: một root SPAN `run` (0.15s) và một
  GENERATION `run` (0.15s) lồng bên trong, cost $0.002565, 211 token. Hai observation này
  **trùng khít thời lượng** vì cùng bọc một lời gọi `LabAgent.run()`.

  **Hạn chế cần lưu ý cho mục 6:** `app/agent.py` chỉ đặt `@observe` ở `LabAgent.run()`, còn
  `mock_rag.retrieve()` và `llm.generate()` không được instrument riêng. Vì vậy **không có span
  RAG tách biệt** — khi `rag_slow` được bật, 2.5s sẽ nằm chìm bên trong span `run` chứ không
  hiện thành một thanh riêng trên waterfall. `OBS-42` phải lập luận bằng chênh lệch `latency_ms`
  giữa traffic bình thường và traffic sự cố, hoặc bổ sung span cho `retrieve()` trước khi chạy
  challenge.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: _(chờ OBS-20/OBS-21 xác nhận label `baseline`)_
- Version/label candidate: _(chờ OBS-21)_
- Trace ID của mỗi version: _(chờ OBS-22)_
- Bằng chứng đổi label hoặc rollback: _(chờ OBS-23)_

Đã xác nhận qua Langfuse API: trace hiện tại ghi `prompt_source: langfuse` (không phải
`local` hay `local-fallback`), `prompt_name: day13-chat`, `prompt_label: production`,
`prompt_version: 1` — tức là prompt managed đã được lấy đúng, không phải fallback cục bộ.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **`HỢP LỆ: 6/6 panel có trong dashboard contract.`**
  _(evidence `05-validate-dashboard.txt` chờ OBS-31)_
- Evidence dashboard: _(chờ OBS-30)_
- SLO đã chọn và lý do: _(chờ OBS-32)_
- Alert rules và runbook: _(chờ OBS-33)_

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1` (cohort K4, incident `rag_slow`, seed 1304,
  affected feature `monitoring`, ngưỡng `latency_threshold_ms = 2000`)
- Triệu chứng từ metrics: _(chờ OBS-41)_
- Trace ID liên quan: _(chờ OBS-42)_
- Log line/correlation ID liên quan: _(chờ OBS-43)_
- Root cause: _(chờ OBS-44)_
- Fix action: _(chờ OBS-44)_
- Preventive measure: _(chờ OBS-44)_

> Lưu ý khi chạy challenge: đặt `LLM_PROVIDER=mock`. Với provider thật (`aibox`) latency đo được
> là 5.000–17.600ms ngay cả khi chưa bật incident, vượt sẵn cả ngưỡng 2000ms lẫn threshold P95
> 3000ms nên không chứng minh được `rag_slow` gây ra điều gì.

## 7. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Nguyễn Xuân Quang | OBS-10 correlation ID middleware, OBS-11 enrich log context, OBS-14 đạt 100/100 + evidence, OBS-24 sinh trace | `OBS-10: correlation ID middleware`, `OBS-11: enrich /chat log context`, `OBS-14: validate_logs 100/100 with evidence`, `OBS-24: generate traces` (nhánh `feat/correlation-context`) | `clear_contextvars()` phải chạy đầu mỗi request, nếu không context request trước rò sang request sau và không test nào bắt được |
| Trần Quang Sáng | OBS-03 Langfuse key, OBS-12 đăng ký PII processor | `OBS-03`, `OBS-12: register PII scrubber processor` (PR #2, #4) | `scrub_event` phải đứng trước `JsonlFileProcessor`, vì processor này tự render và ghi file ngay tại chỗ |
| Cao Các Tường | OBS-02 baseline, OBS-13 bổ sung PII pattern | `OBS-13: add passport and address PII patterns` (PR #1, #3) | Baseline phải chụp trước khi sửa TODO, không dựng lại được sau |
| Lưu Nguyễn Ngọc Hân | _(chờ OBS-30…33)_ | _(chờ)_ | _(chờ)_ |
