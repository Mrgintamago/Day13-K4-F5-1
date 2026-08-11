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
- Tổng số traces: **77** trên Langfuse tại thời điểm ghi (yêu cầu tối thiểu 10), sinh bằng nhiều
  lượt `python scripts/load_test.py --concurrency 5`. Con số này còn tăng khi chạy challenge.
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
  `submission/evidence/04b-traces-list.png` (danh sách Tracing, không lọc — tổng ≈ 144 bản ghi
  trên 3 model: `deepseek-v4-pro` 46, `claude-opus-5` 15, `claude-sonnet-4-5` 10; nhìn thấy cả
  span `rag_retrieve` và `llm_generate` mới bổ sung).
- Giải thích một span đáng chú ý: trace `b90d099f068854c7f281456af859d499` (session `s10`,
  user `105a9cef3903` — đã hash) có **2 observation**: một root SPAN `run` (0.15s) và một
  GENERATION `run` (0.15s) lồng bên trong, cost $0.002565, 211 token. Hai observation này
  **trùng khít thời lượng** vì cùng bọc một lời gọi `LabAgent.run()`.

  **Bổ sung instrumentation (nhóm tự làm thêm):** ban đầu `app/agent.py` chỉ đặt `@observe` ở
  `LabAgent.run()`, nên khi `rag_slow` bật thì 2.5s chìm bên trong span `run` và waterfall không
  chỉ ra được thủ phạm. Nhóm đã thêm hai span con `rag_retrieve` và `llm_generate` bọc quanh
  `retrieve()` và `llm.generate()`.

  Kiểm chứng bằng một request chạy khi `rag_slow` đang bật — trace
  `210b60fac874b783da51684a86f49bfb` (session `span-verify`, correlation `req-f1a45c0e`):

  | Observation | Type | Thời lượng |
  |---|---|---:|
  | `run` | GENERATION | 3649 ms |
  | **`rag_retrieve`** | SPAN | **2501 ms** |
  | `llm_generate` | SPAN | 151 ms |

  Retrieval chiếm ~69% tổng latency còn LLM chỉ 151 ms → waterfall khoanh vùng được ngay tầng
  retrieval mà không cần đoán. Đây là dữ liệu dùng cho mục 6.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: **v1**, labels `baseline` + `production`
- Version/label candidate: **v2**, label `candidate`
- Trace ID của mỗi version — chạy **cùng một input** với hai label khác nhau (`OBS-22`):

| Label | Prompt version | Trace ID | `prompt_source` |
|---|---:|---|---|
| `baseline` | 1 | `782b66eb07556950c78b79b01fd6619c` | `langfuse` |
| `candidate` | 2 | `a1f393cdc263280cdad1f2ecc17daed3` | `langfuse` |

- Bằng chứng đổi label hoặc rollback (`OBS-23`):
  `submission/evidence/04-prompt-rollback-v2-production.png` (promote `production` → v2) và
  `submission/evidence/04-prompt-rollback-v1-production.png` (rollback `production` → v1).
  Rollback chỉ là trỏ lại con trỏ label, không cần deploy lại code — đó là lợi ích chính của
  mô hình version bất biến + label di động.

Một lượt chạy độc lập thứ hai (input `"So sanh hai prompt version"`, session `cmp-baseline` /
`cmp-candidate`) cho kết quả trùng khớp: trace `0103043eb54840a173dff8d04241a4bf` → version 1,
trace `3f27bd32300c6486594a98bab3f14590` → version 2.

Tất cả trace trên đều ghi `prompt_source: langfuse` (không phải `local` hay `local-fallback`), nên
version trong trace là version thật lấy từ Langfuse chứ không phải fallback cục bộ.

**Sự cố đã gặp và cách xử lý (đáng ghi lại):** có một khoảng thời gian label `production` bị mất
khỏi prompt trong khi `.env` vẫn trỏ `LANGFUSE_PROMPT_LABEL=production`. Hệ quả là mọi trace sinh
ra trong khoảng đó ghi `prompt_source: local-fallback` và `prompt_version: local-v1` — tức app
vẫn trả lời bình thường nhưng **không còn truy được prompt version thật**. Phát hiện bằng cách
gọi Langfuse API kiểm từng label (`production` → `NotFound`) rồi bắn thử một request và đọc
metadata trace. Khắc phục bằng cách gán lại label `production` cho v1 trên Langfuse — **không sửa
code để ghi version giả** (RULES.md). Đây đúng là bài học của mục "fallback phải trung thực":
một hệ observability nói dối về trạng thái của chính nó còn tệ hơn không có gì.

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
