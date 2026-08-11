# Lý thuyết Observability cho hệ thống AI

Tài liệu ôn cho phần vấn đáp (rubric B1 — 20 điểm). Mỗi thành viên phải giải thích được
phần mình làm và trả lời 8 câu trong [mock-debug-qa.md](mock-debug-qa.md).

---

## 1. Monitoring khác Observability ở đâu

**Monitoring** trả lời câu hỏi bạn đã biết trước: "P95 có vượt 3000ms không?" — bạn phải nghĩ ra
câu hỏi từ lúc dựng hệ thống.

**Observability** là khả năng trả lời câu hỏi bạn **chưa** nghĩ tới: "vì sao traffic `monitoring`
chậm từ 14:20, mà chỉ với người dùng có session dài?" Muốn vậy dữ liệu phải đủ chiều
(`feature`, `session_id`, `model`, `error_type`) và nối được với nhau.

Ba trụ cột kinh điển:

| Trụ cột | Bản chất | Chi phí lưu | Dùng khi |
|---|---|---|---|
| Metrics | số đã tổng hợp theo thời gian | rẻ nhất | phát hiện "có chuyện gì đó" |
| Traces | cây span của một request | trung bình | tìm "chuyện đó ở đâu" |
| Logs | sự kiện rời rạc, chi tiết cao | đắt nhất | chứng minh "vì sao" |

Thứ tự điều tra **Metrics → Traces → Logs** đi từ rẻ và rộng đến đắt và hẹp. Đi ngược lại
(grep log trước) là cách nhanh nhất để lạc trong hàng nghìn dòng.

Hệ AI có thêm trụ cột thứ tư: **evaluation/quality**. Một API AI có thể trả `200 OK`, latency đẹp,
mà câu trả lời sai hoàn toàn. Đó là lý do lab bắt buộc panel `quality_score` — HTTP status
không nói lên chất lượng đầu ra.

---

## 2. Structured logging

Log dạng chuỗi tự do (`"user 123 failed after 4s"`) buộc bạn viết regex mới cho mỗi câu hỏi mới.
Log JSON có cấu trúc biến mỗi dòng thành một bản ghi truy vấn được:

```json
{"ts":"2026-08-11T07:20:31Z","level":"info","service":"api","event":"response_sent",
 "correlation_id":"req-9f2a1c7b","feature":"monitoring","latency_ms":2450,"cost_usd":0.000381}
```

Ba nguyên tắc:

1. **`event` là danh từ ổn định, không phải câu văn.** `response_sent` luôn giống nhau nên
   đếm được; `"Đã trả lời xong cho refund"` thì không.
2. **Số liệu là field riêng, không nhét vào text.** `latency_ms: 2450` tính percentile được;
   `"took 2450ms"` thì phải parse.
3. **Ngữ cảnh gắn ở tầng context, không truyền tay qua từng lời gọi hàm.**

### contextvars và vì sao phải `clear_contextvars()`

`structlog.contextvars` lưu ngữ cảnh theo async task, không theo lời gọi hàm. Bind một lần ở
middleware thì mọi log sau đó trong cùng request tự có `correlation_id` — không phải truyền
tham số xuyên 5 tầng.

Nhưng worker của uvicorn **tái sử dụng** context giữa các request. Không gọi `clear_contextvars()`
ở đầu mỗi request thì `feature` của request trước rò sang request sau — log trông vẫn hợp lệ,
điều tra thì sai người sai việc. Đây là loại bug không có test nào bắt được, chỉ lộ ra khi có tải.

---

## 3. Correlation ID và trace ID

| | Correlation ID | Trace ID |
|---|---|---|
| Ai sinh | app của bạn (`middleware.py`) | SDK tracing (Langfuse) |
| Sống ở | log lines, response header | backend trace |
| Phạm vi | một request logic, xuyên nhiều service | một cây span |
| Ai dùng | kỹ sư grep log, khách hàng báo lỗi | kỹ sư đọc waterfall |

Correlation ID nhận từ **client** nếu có (`x-request-id`) — nhờ vậy khi khách hàng gửi ticket kèm
ID, bạn tìm được đúng request thay vì mò theo giờ. Trả nó lại trong response header là chuyện
bắt buộc, không phải tùy chọn.

Trong lab này hai lớp nối nhau qua `session_id` + mốc thời gian: mở trace chậm trên Langfuse →
lấy `session_id` và `ts` → lọc `data/logs.jsonl` → ra `correlation_id` → đọc toàn bộ log của
request đó.

---

## 4. Percentile — vì sao average nói dối

Giả sử 100 request: 95 request 200ms, 5 request 8000ms.

- Average = 590ms — trông ổn, không alert nào nổ.
- P50 = 200ms — "một nửa người dùng thấy nhanh".
- P95 = 8000ms — **5 người dùng trong 100 đang chờ 8 giây**.

Average trộn lẫn cái nhanh với cái chậm rồi giấu cả hai. Percentile trả lời đúng câu bạn cần:
"trải nghiệm tệ nhất mà X% người dùng gặp phải là bao nhiêu."

- **P50** — trải nghiệm điển hình.
- **P95** — mục tiêu SLO thông thường; đủ nghiêm để bắt vấn đề thật, đủ lỏng để không nổ vì một spike.
- **P99** — long tail; thường lộ ra cache miss, retry, cold start.

Percentile **không cộng được**. P95 của tuần không phải trung bình P95 các ngày — phải tính lại
từ dữ liệu thô. Đây là lỗi hay gặp khi ghép nhiều dashboard.

Với LLM, đuôi phân phối còn dày hơn API thường vì độ dài output biến thiên lớn, nên P99 đáng
theo dõi hơn hẳn hệ CRUD.

---

## 5. PII và thứ tự redaction

Log là nơi PII rò rỉ nhiều nhất, vì nó được ghi tự động, giữ lâu, và ai cũng đọc được.

Nguyên tắc: **scrub trước khi render, render trước khi ghi.** Trong pipeline structlog của lab,
`JsonlFileProcessor` tự render JSON và ghi file ngay tại vị trí của nó — mọi processor đứng sau
nó không còn tác dụng lên file. Đặt `scrub_event` sai chỗ thì code trông "có scrub" mà
`data/logs.jsonl` vẫn đầy email.

Redact chứ đừng xóa trắng: `[REDACTED_EMAIL]` giữ lại thông tin "chỗ này từng có email" —
vẫn điều tra được cấu trúc request mà không lộ dữ liệu.

Với `user_id`, hash thay vì redact: `hash_user_id()` cho ra 12 hex ổn định, nên bạn vẫn nhóm được
request theo người dùng, so sánh hành vi, mà không lưu danh tính. Đây là **pseudonymization** —
đánh đổi giữa hữu dụng và riêng tư, khác với ẩn danh hoàn toàn.

Hệ AI có ba chỗ rò riêng mà hệ thường không có: prompt gửi lên provider, output model sinh ra
(có thể lặp lại PII trong input), và trace payload trên nền tảng bên thứ ba.

---

## 6. SLI, SLO và error budget

- **SLI** — con số đo được: `latency_p95_ms`, `error_rate_pct`.
- **SLO** — mục tiêu đặt trên SLI: "P95 ≤ 3000ms trong 99.5% thời gian, cửa sổ 28 ngày".
- **Error budget** — phần được phép hỏng: 99.5% nghĩa là budget 0.5%, tức ~3.4 giờ trong 28 ngày.

Error budget biến tranh cãi "có nên deploy không" thành phép trừ. Còn budget thì cứ ship;
hết budget thì dừng tính năng mới, đi sửa độ tin cậy. Nó cũng nói rằng **100% là mục tiêu sai** —
đắt vô hạn và không ai cần.

SLO phải xuất phát từ **trải nghiệm người dùng**, không từ năng lực hệ thống. "P95 ≤ 3000ms"
vì quá 3 giây người dùng bỏ đi, chứ không phải vì hệ thống đang chạy 3 giây.

Hệ AI cần thêm SLO chất lượng và chi phí — hai thứ hệ truyền thống không có:
`quality_score_avg ≥ 0.75` và `daily_cost_usd ≤ 2.5`.

---

## 7. Alert tốt

Một alert đáng tồn tại khi trả lời được: **có người phải làm gì đó ngay bây giờ không?**
Nếu không, nó là dashboard, không phải alert.

| Thành phần | Thiếu thì sao |
|---|---|
| Condition dựa trên triệu chứng người dùng | alert theo tên hàm nội bộ → đổi code là alert vô nghĩa |
| Duration (`trong 5 phút liên tục`) | nổ theo từng spike, gây alert fatigue |
| Severity | mọi thứ đều "critical" thì không gì là critical |
| Impact | người trực không biết có nên dậy lúc 3 giờ sáng |
| 3 bước kiểm tra đầu | mỗi ca trực điều tra lại từ đầu |
| Owner | không ai chịu trách nhiệm thì không ai sửa |

**Symptom-based** hơn **cause-based**: alert "P95 vượt SLO" bắt được mọi nguyên nhân, kể cả
nguyên nhân bạn chưa nghĩ tới. Alert "retrieval latency cao" chỉ bắt đúng một nguyên nhân và
sẽ chết lặng lẽ khi bạn đổi implementation.

**Alert fatigue** là chế độ hỏng nguy hiểm nhất: alert nổ quá nhiều → người ta tắt thông báo →
sự cố thật bị bỏ qua. Ít alert mà đúng luôn tốt hơn nhiều alert mà ồn.

---

## 8. Cost và token

LLM là thành phần hiếm hoi mà **mỗi request tốn tiền tỉ lệ theo dữ liệu**, nên cost là một
tín hiệu vận hành chứ không chỉ là việc của kế toán.

Công thức trong `app/agent.py`:

```
cost = tokens_in/1_000_000 × $3  +  tokens_out/1_000_000 × $15
```

Output đắt gấp 5 lần input — đó là lý do tách `tokens_in` và `tokens_out` thành hai field riêng
thay vì gộp `total_tokens`.

**Chẩn đoán khi cost tăng:**

| Triệu chứng | Nghi ngờ | Field cần kiểm |
|---|---|---|
| Cost ↑, traffic ↑ tương ứng | tăng trưởng bình thường | không phải sự cố |
| Cost ↑, traffic phẳng | prompt phình hoặc output dài ra | `tokens_in`, `tokens_out` theo phút |
| `tokens_in` ↑ đột ngột | retrieval trả quá nhiều doc, prompt version mới | `doc_count`, `prompt_version` |
| `tokens_out` ↑ | prompt mới bỏ giới hạn độ dài | `prompt_label` |
| Cost ↑ kèm error ↑ | retry bão | `error_type` |

Đây chính là lý do `prompt_version` phải nằm trong trace metadata: khi cost nhảy vọt, câu hỏi
đầu tiên luôn là "có ai vừa đổi prompt không?"

---

## 9. Prompt versioning

Prompt là code — nó quyết định hành vi production và cần được quản lý như code: có version,
có label môi trường, rollback được, và mỗi request phải truy ra được nó dùng version nào.

**Version** là bất biến (v1, v2, v3 — không sửa sau khi tạo).
**Label** là con trỏ di động (`production`, `baseline`, `candidate`) trỏ vào một version.

Rollback vì thế chỉ là trỏ lại con trỏ, không cần deploy — đây là lợi ích chính của mô hình này.

Mọi trace ghi lại **cả ba**: `prompt_name`, `prompt_label`, `prompt_version`. Chỉ ghi label là
chưa đủ, vì `production` hôm nay trỏ v2, hôm qua trỏ v1 — trace cũ sẽ không giải thích được nữa.

**Fallback phải trung thực.** Khi Langfuse không với tới được, `resolve_prompt()` trả về
`prompt_source = "local-fallback"` và `version = "local-v1"` thay vì giả vờ đã lấy được prompt
managed. Một hệ observability nói dối về trạng thái của chính nó còn tệ hơn không có gì.

---

## 10. Quy trình điều tra sự cố

```
Triệu chứng  →  Khoanh vùng  →  Chứng minh  →  Kết luận  →  Fix  →  Phòng ngừa
 (Metrics)      (Traces)        (Logs)
```

1. **Metrics** — chỉ số nào lệch, lệch từ lúc nào, lệch bao nhiêu so với baseline.
   Ghi lại mốc thời gian; nó thu hẹp mọi bước sau.
2. **Traces** — mở một request bất thường **trong đúng khung giờ đó**. So thời gian các span:
   span nào chiếm phần lớn latency? Đừng đọc trace "trung bình" — đọc trace tệ.
3. **Logs** — lọc theo `correlation_id` của chính request đó. Đây là bước duy nhất cho bạn
   chi tiết đủ để chứng minh, và cũng là bước đắt nhất nên phải vào sau cùng.
4. **Kết luận** — chỉ chốt khi cả ba lớp khớp nhau. Một span chậm **chưa** phải root cause;
   nó là chỗ triệu chứng biểu hiện. Root cause là thứ giải thích **vì sao** span đó chậm.
5. **Fix** — khôi phục dịch vụ. Có thể tạm thời (rollback, tắt feature).
6. **Preventive** — làm sao lần sau phát hiện sớm hơn hoặc không tái diễn (alert mới, timeout,
   test hồi quy). Không có bước này thì tuần sau bạn điều tra lại đúng sự cố đó.

**Tương quan không phải nhân quả.** Hai đường cùng dốc lên không chứng minh cái này gây ra cái kia.
Bằng chứng đủ mạnh là: cùng correlation ID, cùng khung thời gian, và có cơ chế giải thích được.

### Áp vào challenge K4 (`rag_slow` / `monitoring` / 2000ms)

| Bước | Cái phải chỉ ra | Nhầm lẫn thường gặp |
|---|---|---|
| Metrics | P95 nhảy từ ~200ms lên ~2500ms, vượt ngưỡng 2000ms | Báo "chưa vượt SLO" vì nhìn threshold 3000ms của dashboard |
| Traces | Span **RAG** chiếm ~2.5s, span LLM vẫn ~0.15s | Kết luận "LLM chậm" vì nó là span cuối cùng |
| Logs | Log của đúng `correlation_id` đó, `feature=monitoring` | Grep cả file rồi trích một dòng bất kỳ |
| Kết luận | Retrieval chậm ở tầng vector store | "Feature `monitoring` bị lỗi" — sai, incident chậm mọi feature |

Root cause là **retrieval chèn 2.5s trước khi trả doc**, không phải "span RAG chậm" (đó mới là triệu chứng).
Fix: tắt incident / rollback thay đổi ở tầng retrieval. Preventive: timeout cho `retrieve()` + alert P95
kèm duration, để lần sau phát hiện trong 5 phút thay vì chờ ai đó mở dashboard.

---

## 11. Vì sao `validate_logs.py` 100 điểm vẫn có thể trượt lab

Validator kiểm được **hình thức**: field có mặt không, regex PII có khớp không, có ≥2 correlation ID không.

Nó không kiểm được **ý nghĩa**:

- Correlation ID có thật sự bám theo từng request không, hay bị rò giữa các request.
- Dashboard trong ảnh có vẽ từ đúng dữ liệu không.
- Root cause có được chứng minh không, hay chỉ là phỏng đoán hợp lý.
- Người viết có hiểu code mình nộp không.

Rubric dành 20/100 cho demo và 20/100 cho vấn đáp cá nhân chính là để đo phần validator không
với tới. Đây cũng là bài học vận hành thật: **một cổng kiểm tra tự động xanh không có nghĩa hệ
thống đúng — nó chỉ có nghĩa những thứ bạn nghĩ ra cách kiểm đã đúng.**

---

## Tự kiểm tra nhanh

| Câu hỏi trong `mock-debug-qa.md` | Mục |
|---|---|
| 1. Vì sao average latency bỏ sót vấn đề | §4 |
| 2. Correlation ID khác trace ID | §3 |
| 3. Error rate tăng: mở metric, trace hay log trước | §1, §10 |
| 4. PII scrub trước hay sau khi render JSON | §5 |
| 5. Alert tốt cần gì | §7 |
| 6. Cost tăng nhưng traffic không tăng | §8 |
| 7. Evidence nào đủ kết luận root cause | §10 |
| 8. Vì sao validator 100 chưa là lab 100 | §11 |
