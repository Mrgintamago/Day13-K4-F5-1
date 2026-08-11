# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

---

## Alert 1: High Latency - API responses taking too long

- **Tên:** High Latency - API responses taking too long
- **Severity:** warning
- **SLI/SLO liên quan:** latency_p95_ms (objective: 3000ms, target: 99.5%)
- **Điều kiện và thời gian duy trì:** P95 latency > 3000ms trong 5 phút liên tục
- **Ảnh hưởng tới người dùng:** Người dùng phải chờ lâu hơn bình thường, có thể bỏ cuộc hoặc thử lại nhiều lần
- **Ba bước kiểm tra đầu tiên:**
  1. **Metrics:** Mở dashboard panel Latency, kiểm tra P95 hiện tại và so với baseline
  2. **Traces:** Mở Langfuse, lọc traces có duration cao, xác định span nào chiếm nhiều thời gian nhất
  3. **Logs:** Lọc logs theo correlation_id từ trace chậm, xem có pattern bất thường nào không
- **Mitigation tạm thời:** Kiểm tra xem có incident nào đang bật không (`/health`), xem xét disable incident nếu không cần thiết
- **Owner:** Platform Team

---

## Alert 2: High Error Rate - Requests failing

- **Tên:** High Error Rate - Requests failing
- **Severity:** critical
- **SLI/SLO liên quan:** error_rate_pct (objective: 2%, target: 99.0%)
- **Điều kiện và thời gian duy trì:** Error rate > 2% trong 5 phút liên tục
- **Ảnh hưởng tới người dùng:** Người dùng nhận được lỗi thay vì câu trả lời, trải nghiệm bị gián đoạn hoàn toàn
- **Ba bước kiểm tra đầu tiên:**
  1. **Metrics:** Mở dashboard panel Errors, kiểm tra error rate hiện tại và breakdown theo error_type
  2. **Traces:** Mở Langfuse, lọc traces có status = failed, kiểm tra error message
  3. **Logs:** Lọc logs có event = "request_failed", đọc error_type và stack trace nếu có
- **Mitigation tạm thời:** Restart API nếu cần thiết, kiểm tra LLM provider và network connectivity
- **Owner:** Platform Team

---

## Alert 3: Low Quality Score - Answers below threshold

- **Tên:** Low Quality Score - Answers below threshold
- **Severity:** warning
- **SLI/SLO liên quan:** quality_score_avg (objective: 0.75, target: 95.0%)
- **Điều kiện và thời gian duy trì:** Mean quality score < 0.75 trong 10 phút liên tục
- **Ảnh hưởng tới người dùng:** Người dùng nhận được câu trả lời kém chất lượng, có thể không đáp ứng được nhu cầu
- **Ba bước kiểm tra đầu tiên:**
  1. **Metrics:** Mở dashboard panel Quality, kiểm tra trend của quality score theo thời gian
  2. **Traces:** Mở Langfuse, kiểm tra prompt version hiện tại và xem có thay đổi gần đây không
  3. **Logs:** Lọc logs có quality_score thấp, kiểm tra các request liên quan để tìm pattern
- **Mitigation tạm thời:** Rollback prompt về version ổn định, kiểm tra retrieval (RAG) có trả về docs đúng không
- **Owner:** AI Team
