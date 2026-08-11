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
Quy trình chạy (`OBS-40`): xoá `data/logs.jsonl` → chạy `load_test.py` một lượt lúc **chưa** bật
sự cố để có nhóm đối chiếu → `python scripts/inject_incident.py` → `python scripts/load_test.py
--challenge --concurrency 5`. Toàn bộ chạy với `LLM_PROVIDER=mock`.

**Triệu chứng từ metrics** — percentile tính từ field `latency_ms` của event `response_sent`:

| Traffic | n | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| `qa` (đối chiếu, trước sự cố) | 8 | 151 ms | 152 ms | 152 ms |
| `summary` (đối chiếu) | 2 | 151 ms | 1207 ms | 1207 ms |
| **`monitoring` (challenge)** | 5 | **2652 ms** | **2652 ms** | **2652 ms** |

So với ngưỡng: **2652 ms > 2000 ms** (`latency_threshold_ms` của challenge) → đã vượt. Nhưng
**2652 ms < 3000 ms** (threshold P95 trong `config/dashboard.yaml`) → **panel dashboard vẫn xanh**.
Đây chính là bẫy: nếu chỉ nhìn dashboard sẽ kết luận "không có sự cố". Báo cáo phải nói rõ đang
so với ngưỡng nào.

Một khác biệt nữa cần phân biệt: client (`load_test.py`) đo được **13.280 ms** mỗi request, trong
khi app tự ghi `latency_ms = 2652 ms`. Chênh lệch không phải do đo sai — `retrieve()` dùng
`time.sleep()` chặn trong handler `async`, nên 5 request đồng thời bị **xếp hàng** thay vì chạy
song song (5 × 2,65s ≈ 13,3s). `latency_ms` là thời gian app xử lý một request; con số client
thấy còn cộng thêm thời gian chờ hàng đợi. Người dùng cuối chịu con số 13,3s.

**Trace ID liên quan:** `f1d677bd232273316b3cab208f20b2bd` (session `k4-challenge-s01`,
user `f00ba60b3772`, lúc 16:43:17, cost $0.002781, tags `lab, monitoring, deepseek-v4-pro`) —
ảnh `submission/evidence/09-challenge-trace.png`. Phân rã span:

| Observation | Type | Thời lượng | Tỷ trọng |
|---|---|---:|---:|
| `run` | GENERATION | 2652 ms | 100% |
| **`rag_retrieve`** | SPAN | **2501 ms** | **94%** |
| `llm_generate` | SPAN | 151 ms | 6% |

**Log line / correlation ID liên quan:** `req-719b7dfe` (session `k4-challenge-s01`,
`user_id_hash` `f00ba60b3772`) — trích nguyên văn trong
`submission/evidence/10-challenge-logs.txt`, gồm cặp `request_received` / `response_sent` với
`latency_ms: 2652`, `tokens_in: 57`, `tokens_out: 174`, `cost_usd: 0.002781`, `quality_score: 0.8`.

Ba lớp chỉ về **cùng một request duy nhất**, không phải ba mẫu rời ghép lại: metric p95 2652 ms
= `latency_ms` trong log = thời lượng span `run` trong trace; `session_id` `k4-challenge-s01`,
`user_id_hash` `f00ba60b3772` và `cost_usd 0.002781` trùng khớp giữa log và trace. Đây là điều
kiện để kết luận được tính, theo `RULES.md`.

**Root cause:** tầng **retrieval** chặn ~2,5 giây trước khi trả tài liệu. Trong lab, `rag_slow`
làm `mock_rag.retrieve()` gọi `time.sleep(2.5)` trước khi trả về (`app/mock_rag.py:17`).
Đây **không phải** sự cố cục bộ của feature `monitoring`: `rag_slow` làm chậm mọi feature, chỉ là
5 câu hỏi challenge đều mang `feature=monitoring` nên triệu chứng lộ ra ở đó. Span `llm_generate`
giữ nguyên 151 ms chứng minh LLM vô can.

**Fix action:** tắt kịch bản để khôi phục dịch vụ — `python scripts/inject_incident.py --disable`.
Đã thực hiện và xác nhận (`OBS-45`): `/health` trả
`{"ok": true, "incidents": {"rag_slow": false, "tool_fail": false, "cost_spike": false}}`.
Trong hệ thật, tương đương rollback thay đổi ở tầng retrieval hoặc chuyển sang vector store dự phòng.

**Preventive measure — 3 việc, xếp theo mức độ cấp thiết:**

1. **Hạ ngưỡng alert latency xuống 2000 ms — ĐÃ THỰC HIỆN.** Đây là lỗ hổng nghiêm trọng nhất
   phát hiện được: `config/alert_rules.yaml` đang đặt *"P95 latency > 3000ms trong 5 phút liên
   tục"*, mà sự cố này chỉ đẩy P95 lên **2652 ms** — **alert sẽ không nổ trong chính sự cố vừa
   điều tra**. Hệ cảnh báo mù trước đúng kịch bản nó phải bắt. Đã sửa điều kiện thành
   *"P95 latency > 2000ms trong 5 phút liên tục"* (bám `latency_threshold_ms` của challenge),
   giữ nguyên duration để không báo động giả theo từng spike, và ghi lý do vào
   `docs/alerts.md#alert-1`. SLO `latency_p95_ms` vẫn để **3000 ms**: alert cố tình nổ **trước**
   khi SLO bị phá, để còn thời gian xử lý thay vì báo lúc đã mất error budget.
2. **Timeout cho `retrieve()`** (ví dụ 500 ms): quá hạn thì trả tài liệu rỗng kèm log
   `error_type`. Chậm còn hơn treo, và sự cố hiện thành **lỗi đếm được** trên panel errors thay
   vì latency âm thầm — dịch triệu chứng từ chỗ khó thấy sang chỗ dễ thấy.
3. **Bỏ chặn event loop.** `retrieve()` dùng `time.sleep` đồng bộ trong handler `async`, nên một
   tầng chậm kéo tụt toàn bộ throughput chứ không chỉ request của chính nó (client đo 13.280 ms
   trong khi app ghi 2652 ms). Chuyển sang I/O bất đồng bộ hoặc đẩy xuống threadpool.

Bài học rút ra: **cổng kiểm tra xanh không có nghĩa hệ thống ổn**. Dashboard vẫn xanh, alert vẫn
im, `validate_logs.py` vẫn 100/100 — trong khi mọi request của feature bị ảnh hưởng chậm gấp 17
lần. Thứ phát hiện ra sự cố là so sánh với **nhóm đối chiếu** và với **ngưỡng challenge**, không
phải bản thân cái dashboard.

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
