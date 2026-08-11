# Danh sách evidence cần thu thập

Cột **Trạng thái** cập nhật theo tiến độ thật. Ảnh phải đặt trong `submission/evidence/` và được
dẫn lại bằng đường dẫn tương đối trong `submission/REPORT.md`.

## Bắt buộc

| # | Evidence | File | Ticket | Trạng thái |
|---|---|---|---|---|
| 1 | Kết quả cuối của `validate_logs.py` | `01-validate-logs.txt` | OBS-14 | ✅ 100/100, 4/4 PASSED |
| 2 | Danh sách có tối thiểu 10 traces | `04b-traces-list.png` | OBS-24 | ✅ ~144 bản ghi, 3 model |
| 3 | Một trace waterfall đầy đủ | `04c-trace-waterfall.png` | OBS-24 | ✅ kèm panel metadata |
| 4 | Hai prompt version và trace hiển thị đúng name/label/version | `03-prompt-versions.png`, `03b-trace-prompt-versions.png` | OBS-21, OBS-22 | ⏳ **THIẾU — tạm bỏ qua.** Đã có 2 trace ID trong REPORT mục 4, chưa có 2 ảnh UI |
| 5 | Một bằng chứng đổi label hoặc rollback prompt | `04-prompt-rollback-v1-production.png`, `04-prompt-rollback-v2-production.png` | OBS-23 | ✅ promote `production`→v2 và rollback `production`→v1 |
| 6 | Log JSON có correlation ID và metadata | `02-log-correlation-id.txt` | OBS-14 | ✅ |
| 7 | Log chứng minh PII đã được redact | `02b-log-pii-redacted.txt` | OBS-14 | ✅ 6 loại PII, 0 leak |
| 8 | Kết quả `validate_dashboard.py` hợp lệ | `05-validate-dashboard.txt` | OBS-31 | ✅ `HỢP LỆ: 6/6 panel có trong dashboard contract.` |
| 9 | Dashboard đủ 6 nhóm chỉ số | `06-dashboard.png` | OBS-30 | ✅ kèm 06a/06b/06c |
| 10 | Alert rules và runbook đã hoàn thiện | `config/alert_rules.yaml`, `docs/alerts.md` | OBS-33 | ✅ 3 rules + runbook đầy đủ |
| 11 | Evidence điều tra challenge: metric, trace ID và log line | `08-challenge-metrics.png`, `09-challenge-trace.png`, `10-challenge-logs.txt` | OBS-41…43 | ✅ |

Ngoài danh sách bắt buộc, đã có thêm `00-baseline-validate-logs.txt` (baseline 30/100) để đối
chiếu trước/sau — chính là con số chứng minh phần Logging & PII có tác dụng thật.

## Không bắt buộc

| Evidence | Trạng thái |
|---|---|
| So sánh trước/sau khi tối ưu chi phí | ❌ chưa làm |
| Audit log tách riêng | ❌ chưa làm |
| Custom metric hoặc automation do nhóm tự xây | ✅ **đã có** — bổ sung span `rag_retrieve` và `llm_generate` trong `app/agent.py`; xem REPORT mục 3 |

## Ghi chú khi thu thập

- Ảnh phải nhìn rõ **tên panel, time range, đơn vị, threshold**; ảnh Langfuse phải thấy metadata
  (`prompt_name` / `prompt_label` / `prompt_version` / `prompt_source`).
- Đừng để bộ lọc trên UI loại mất chính traffic vừa chạy — evidence lọc sai coi như không chứng
  minh được gì.
- Evidence của challenge phải lấy từ lần chạy `load_test.py --challenge`, không dùng lại ảnh
  practice.
- Trước khi chạy challenge, đặt `LLM_PROVIDER=mock`: với provider thật latency đo được là
  5.000–17.600ms, vượt sẵn cả ngưỡng 2000ms lẫn threshold 3000ms nên không chứng minh được
  `rag_slow` gây ra điều gì.
