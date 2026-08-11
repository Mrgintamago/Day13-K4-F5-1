# Technical Spec — Day 13 Observability

> Soạn trên repo mẫu K3, **đã đối chiếu với repo K4 này ngày 2026-08-11**: số dòng TODO,
> contract dashboard, log schema và thang điểm validator đều khớp. Giá trị riêng của cohort
> nằm ở [§8 Challenge](#8-challenge) và đã điền theo `config/challenge.json` bản release.

Spec triển khai cho [PLAN.md](PLAN.md). Nguồn chuẩn vẫn là `config/*` và `RUBRIC.md`;
file này chỉ diễn giải thành yêu cầu cụ thể ở mức code.

---

## 1. Kiến trúc và luồng một request

```
POST /chat
  │
  ├─ CorrelationIdMiddleware (app/middleware.py)
  │     clear_contextvars → lấy/sinh correlation_id → bind_contextvars
  │
  ├─ /chat handler (app/main.py)
  │     bind context enrichment → log "request_received"
  │
  ├─ LabAgent.run (app/agent.py)  ── @observe(as_type="generation")
  │     ├─ mock_rag.retrieve(message)          → span RAG
  │     ├─ prompt_management.resolve_prompt()  → Langfuse managed prompt / local fallback
  │     ├─ mock_llm.generate(prompt.text)      → span LLM
  │     ├─ update_current_trace / update_current_generation  → metadata prompt
  │     └─ metrics.record_request(...)
  │
  ├─ log "response_sent" (latency, tokens, cost, quality)  |  lỗi → "request_failed"
  │
  └─ response + header x-request-id, x-response-time-ms
```

Ba lớp quan sát và vai trò từng lớp:

| Lớp | Nơi lưu | Dùng để | Khóa nối |
|---|---|---|---|
| Metrics | `GET /metrics` + `data/logs.jsonl` | phát hiện triệu chứng, xác định khung giờ | `ts` |
| Traces | Langfuse | khoanh vùng span chậm/lỗi | `session_id`, `user_id` (hash) |
| Logs | `data/logs.jsonl` | chứng minh root cause | `correlation_id` |

Ba lớp phải nối được với nhau, nếu không kết luận incident sẽ không được tính (RULES.md).

---

## 2. Log schema

Contract máy đọc: `config/logging_schema.json`. Kiểm bằng `scripts/validate_logs.py`.

### Trường bắt buộc — mọi record

| Field | Kiểu | Nguồn |
|---|---|---|
| `ts` | string ISO-8601 UTC | `TimeStamper` (có sẵn) |
| `level` | string | `add_log_level` (có sẵn) |
| `event` | string | tên event |
| `service` | string | `api` / `control` |

### Trường bắt buộc — record có `service == "api"`

| Field | Kiểu | Sinh ở đâu |
|---|---|---|
| `correlation_id` | `req-<8 hex>` | `OBS-10`, middleware |
| `user_id_hash` | 12 hex | `OBS-11`, `hash_user_id(body.user_id)` |
| `session_id` | string | `OBS-11`, `body.session_id` |
| `feature` | string | `OBS-11`, `body.feature` |
| `model` | string | `OBS-11`, `agent.model` |
| `env` | string | `OBS-11`, `os.getenv("APP_ENV", "dev")` — **không** nằm trong `ENRICHMENT_FIELDS` của validator, vẫn bind vì dashboard/alert cần phân biệt môi trường |

> `validate_logs.py:47` reject giá trị literal `"MISSING"` — giá trị placeholder hiện có trong `middleware.py:18`.
> Bộ field validator thực sự kiểm (`scripts/validate_logs.py:8`): `user_id_hash`, `session_id`, `feature`, `model`.

### Event chuẩn

| Event | Level | Trường số liệu bắt buộc |
|---|---|---|
| `app_started` | info | — |
| `request_received` | info | — (đơn vị đếm traffic) |
| `response_sent` | info | `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score` |
| `request_failed` | error | `error_type` |
| `incident_enabled` / `incident_disabled` | warning | — |

Nội dung tự do (câu hỏi, câu trả lời) chỉ được đặt trong `payload` và **phải đi qua** `summarize_text()`.

### Thang điểm `validate_logs.py`

| Hạng mục | Trừ nếu fail | Ticket |
|---|---:|---|
| Basic JSON schema (`ts`, `level`, `event`) | −30 | có sẵn |
| Correlation ID (≥2 ID duy nhất) | −20 | `OBS-10` |
| Log enrichment | −20 | `OBS-11` |
| PII scrubbing (0 leak) | −30 | `OBS-12`, `OBS-13` |

CP1 yêu cầu ≥ 80/100; mục tiêu nhóm là 100/100. Điểm này **không phải** điểm rubric.

---

## 3. Correlation ID

- **Định dạng:** `req-` + 8 ký tự hex, ví dụ `req-9f2a1c7b`.
- **Nguồn:** ưu tiên header `x-request-id` của client; không có thì sinh mới bằng `uuid.uuid4().hex[:8]`.
- **Vòng đời:** `clear_contextvars()` **trước** khi bind — bỏ bước này thì contextvars của request trước rò sang request sau (structlog dùng contextvars theo task, không tự reset).
- **Phát ra:** `request.state.correlation_id` (cho response body) + header `x-request-id` + `x-response-time-ms` (làm tròn ms từ `time.perf_counter()`).
- **Khác trace ID:** correlation ID do app sinh, gắn vào **log**; trace ID do Langfuse sinh, gắn vào **trace**. Nối hai lớp qua `session_id` và mốc thời gian.

---

## 4. PII redaction

Vị trí processor trong `app/logging_config.py` — thứ tự quyết định đúng/sai:

```python
processors=[
    merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
    scrub_event,                       # OBS-12: PHẢI đứng trước 2 dòng dưới
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    JsonlFileProcessor(),              # ghi xuống file
    structlog.processors.JSONRenderer(),
]
```

`JsonlFileProcessor` tự render JSON và ghi file ngay tại chỗ, nên bất kỳ processor nào đặt **sau** nó đều không ảnh hưởng tới nội dung `data/logs.jsonl`.

Pattern hiện có trong `app/pii.py`: `email`, `phone_vn`, `cccd`, `credit_card`.
`OBS-13` bổ sung passport và từ khóa địa chỉ. Yêu cầu:

- Thay bằng `[REDACTED_<TYPE>]`, không xóa trắng (mất dấu vết để điều tra).
- Không làm regex mới nuốt chuỗi hợp lệ khác — chạy `tests/test_pii.py` sau mỗi thay đổi.
- `validate_logs.py` dò PII **độc lập** với `pii.py`, nên không thể lách bằng cách sửa pattern.

---

## 5. Dashboard contract

Nguồn dữ liệu chuẩn là **`data/logs.jsonl`**, không phải Langfuse. Contract: `config/dashboard.yaml`.
Trường `query` là pseudocode — chuyển sang cú pháp công cụ nhóm chọn, giữ nguyên phép tính.

| Panel | Event | Field | Aggregation | Đơn vị | Threshold |
|---|---|---|---|---|---|
| `latency` | `response_sent` | `latency_ms` | p50, p95, p99 | ms | p95 ≤ 3000 |
| `traffic` | `request_received` | `event` | count, rate/phút | req/phút | rate ≥ 1 |
| `errors` | `request_received`, `request_failed` | `error_type` | error_rate_pct, count_by_value | percent | ≤ 2 |
| `cost` | `response_sent` | `cost_usd` | sum theo phút, total | usd | total ≤ 2.5 |
| `tokens` | `response_sent` | `tokens_in`, `tokens_out` | sum theo từng field | tokens | ≤ 50000 |
| `quality` | `response_sent` | `quality_score` | mean | score 0–1 | ≥ 0.75 |

Trình bày bắt buộc: time range mặc định 60 phút · refresh 30 giây · vẽ threshold/SLO line · ghi rõ đơn vị · chỉ giữ 6–8 panel ở lớp chính.

`python scripts/validate_dashboard.py` chỉ kiểm cấu trúc contract (`HỢP LỆ: 6/6 panel`) — nó **không** chứng minh biểu đồ dùng đúng dữ liệu, nên ảnh runtime vẫn bắt buộc.

---

## 6. Trace và prompt versioning

### Metadata trace mà `app/agent.py` đã gửi

- Trace: `user_id` (đã hash), `session_id`, `tags=[lab, feature, model]`, metadata `prompt_name` / `prompt_label` / `prompt_version` / `prompt_source`.
- Generation: `model`, `doc_count`, `query_preview` (đã scrub), usage tokens, cost, `prompt=managed_prompt`.

Code phía trace **không có TODO** — chỉ cần `.env` đúng thì metadata tự đầy đủ.

### Ý nghĩa `prompt_source` (dùng để chẩn đoán)

| Giá trị | Nghĩa | Xử lý |
|---|---|---|
| `langfuse` | Lấy được managed prompt — trạng thái đúng | — |
| `local` | Chưa bật tracing (thiếu public/secret key) | điền `.env`, restart API |
| `local-fallback` | Đã bật nhưng fetch lỗi hoặc sai name/label | kiểm `LANGFUSE_HOST`, prompt name, label tồn tại trên project |

`version` khi fallback là `local-v1`. **Không sửa code để ghi version giả** — vi phạm RULES.md.

### Prompt contract

Prompt `day13-chat` phải giữ đúng 3 biến, khớp `DEFAULT_PROMPT_TEMPLATE`:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

Thiếu biến nào thì `managed_prompt.compile()` ném lỗi → rơi về `local-fallback`.

### Ma trận version/label cần tạo

| Version | Label | Dùng cho |
|---|---|---|
| v1 | `baseline`, `production` | trace baseline, đích rollback |
| v2 | `candidate` | trace candidate |
| v2 | `production` (tạm) | chứng minh promote |
| v1 | `production` (cuối) | chứng minh rollback |

Đổi `LANGFUSE_PROMPT_LABEL` trong `.env` xong **phải restart API** (prompt cache TTL 60s + `.env` chỉ đọc lúc khởi động).

Rubric không chấm prompt nào hay hơn — chỉ chấm khả năng truy xuất version, đổi label và rollback có bằng chứng.

---

## 7. SLO và alert

Baseline trong `config/slo.yaml`, cửa sổ 28 ngày:

| SLI | Objective | Target |
|---|---:|---:|
| `latency_p95_ms` | 3000 | 99.5% |
| `error_rate_pct` | 2 | 99.0% |
| `daily_cost_usd` | 2.5 | 100% |
| `quality_score_avg` | 0.75 | 95% |

`OBS-32` thay bằng mục tiêu nhóm kèm lý do. Mỗi alert trong `config/alert_rules.yaml` + `docs/alerts.md` phải có:

1. Tên mô tả **triệu chứng người dùng**, không phải tên hàm/biến nội bộ.
2. Severity và SLI/SLO liên quan.
3. Condition **kèm duration** (`P95 > 3000ms trong 5 phút liên tục`) — thiếu duration sẽ báo động giả theo từng spike.
4. Ảnh hưởng tới người dùng.
5. Ba bước kiểm tra đầu tiên, theo đúng thứ tự Metrics → Traces → Logs.
6. Mitigation tạm thời và owner.

---

## 8. Challenge

`config/challenge.json` — **đã release trong repo này** (commit `5ba6472`), **read-only**,
sửa là vi phạm RULES.md. `git diff config/challenge.json` phải rỗng khi nộp.

| Field | Giá trị K4 (repo này) | Repo mẫu K3 (tham chiếu) |
|---|---|---|
| `cohort` | `K4` | K3 |
| `challenge_id` | `day13-k4-observability-v1` | `day13-k3-observability-v1` |
| `incident` | `rag_slow` | `rag_slow` |
| `seed` | 1304 | 1303 |
| `affected_feature` | `monitoring` | `refund` |
| `latency_threshold_ms` | 2000 | 2000 |
| queries | 5 câu observability, `k4-u01`…`k4-u05`, session `k4-challenge-s01`…`s05` | 5 câu refund policy, `k3-u01`…`k3-u05` |

Năm câu hỏi chính thức (đều `feature: "monitoring"`):

| user_id | session_id | message |
|---|---|---|
| `k4-u01` | `k4-challenge-s01` | Explain why metrics traces and logs work together. |
| `k4-u02` | `k4-challenge-s02` | How should an engineer investigate tail latency? |
| `k4-u03` | `k4-challenge-s03` | Summarize the observability workflow for an AI API. |
| `k4-u04` | `k4-challenge-s04` | Which signal should be checked after latency increases? |
| `k4-u05` | `k4-challenge-s05` | Describe how to prove a slow span is the root cause. |

`seed=1304` chỉ dùng để **xáo thứ tự** 5 query (`app/challenge.py:100 ordered_queries`) — nó không
đổi nội dung, nên thứ tự request trong log của mỗi nhóm sẽ giống nhau và tái lập được.

Ba field quyết định hướng điều tra:

- `incident: rag_slow` — cơ chế nằm ở `app/mock_rag.py:17`: khi bật, `retrieve()` `time.sleep(2.5)`
  **trước** khi trả doc. Vậy latency dồn vào span RAG, không phải span LLM — đó là thứ phải chỉ ra
  ở `OBS-42`.
- `affected_feature: monitoring` — bộ lọc để tìm traffic challenge trong `data/logs.jsonl` và Langfuse.
  **Lưu ý quan trọng, khác bản K3 của tài liệu này:** `rag_slow` làm chậm **mọi** feature chứ không
  riêng `monitoring` (xem code trên). Không được viết trong REPORT rằng "sự cố cục bộ ở feature
  `monitoring`" — kết luận đúng là "sự cố ở tầng retrieval, biểu hiện trên traffic `monitoring` mà
  challenge gửi vào".
- `latency_threshold_ms: 2000` — ngưỡng khẳng định "đã vượt". Ngưỡng challenge (2000ms) **chặt hơn**
  threshold P95 trong `config/dashboard.yaml` (3000ms); báo cáo phải nói rõ đang so với ngưỡng nào.
  Với `sleep(2.5s)`, latency mỗi request challenge sẽ ~2500ms+: vượt 2000ms nhưng có thể **chưa**
  vượt 3000ms — đây chính là chỗ dễ kết luận sai.

Practice scenario của K4 trùng đúng incident chính thức (`rag_slow`), nên `OBS-34` là bài tập chạy
thật cho `OBS-41`. Dù vậy **evidence nộp phải lấy từ lần chạy `--challenge`**, không dùng lại ảnh practice.

Quy trình điều tra bắt buộc:

```bash
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```

1. **Metrics** — panel latency: P95 vượt `latency_threshold_ms` từ thời điểm nào, so với baseline bao nhiêu.
2. **Traces** — mở 1 trace chậm của `affected_feature`, so thời gian các span, chỉ ra span chiếm phần lớn latency.
3. **Logs** — lọc `data/logs.jsonl` theo `correlation_id` tương ứng, trích log line nguyên văn.
4. **Kết luận** — chỉ chốt khi cả 3 lớp khớp nhau.
5. **Fix + preventive** — 1 hành động khắc phục và 1 biện pháp phòng ngừa (ví dụ: alert theo P95 kèm duration, timeout cho retrieval).

Kết thúc: `python scripts/inject_incident.py --scenario rag_slow --disable`, xác nhận `/health` trả
`incidents: {"rag_slow": false, "tool_fail": false, "cost_spike": false}`.

---

## 9. Quy ước evidence

Đặt trong `submission/evidence/`, dẫn lại bằng đường dẫn tương đối trong `submission/REPORT.md`.

| File | Nội dung | Ticket |
|---|---|---|
| `00-baseline-validate-logs.txt` | Output validator trước khi sửa TODO | `OBS-02` |
| `01-validate-logs.txt` | Output validator cuối (≥80) | `OBS-14` |
| `02-log-correlation-id.txt` | Vài dòng log JSON có `correlation_id` + metadata | `OBS-14` |
| `02b-log-pii-redacted.txt` | Log chứng minh PII đã thành `[REDACTED_*]` | `OBS-14` |
| `03-prompt-versions.png` | Danh sách 2 prompt version | `OBS-21` |
| `03b-trace-prompt-versions.png` | 2 trace hiện đúng name/label/version | `OBS-22` |
| `04-prompt-rollback.png` | Trước/sau khi đổi label `production` | `OBS-23` |
| `04b-traces-list.png` | Danh sách ≥10 trace | `OBS-24` |
| `04c-trace-waterfall.png` | 1 trace waterfall đầy đủ | `OBS-24` |
| `05-validate-dashboard.txt` | `HỢP LỆ: 6/6 panel` | `OBS-31` |
| `06-dashboard.png` | Dashboard đủ 6 panel | `OBS-30` |
| `07-dashboard-rag-slow.png` | Before/after incident practice | `OBS-34` |
| `08-challenge-metrics.png` | Triệu chứng từ metrics | `OBS-41` |
| `09-challenge-trace.png` | Trace + span bất thường | `OBS-42` |
| `10-challenge-logs.txt` | Log line theo `correlation_id` | `OBS-43` |

Ảnh phải nhìn rõ tên panel, time range, đơn vị, threshold. Evidence không kiểm chứng được sẽ không được tính.

---

## 10. Definition of Done toàn bài

```bash
python -m pytest -q                    # 22 test trong 10 file, tất cả xanh
python scripts/validate_logs.py        # >= 80/100, 0 PII leak
python scripts/validate_dashboard.py   # HỢP LỆ: 6/6 panel
git status --short                     # sạch, không có .env / .venv / log PII
```

- `submission/REPORT.md` điền đủ 7 mục, mọi đường dẫn evidence mở được.
- `git log` khớp bảng đóng góp mục 7 — commit theo `OBS-<id>: <mô tả>`.
- Không còn chữ `TODO` trong `app/` và `config/alert_rules.yaml`.
- `config/challenge.json` không đổi so với bản release (`git diff` rỗng cho file này).
- Push xong, nộp **URL repository + commit SHA cuối** trên Codelabs.
