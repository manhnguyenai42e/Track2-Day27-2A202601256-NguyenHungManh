# AI Agent Decision Log

## Decision 1: Nâng cấp Contract Validator sang Strict Type & Freshness Checking
- **Hypothesis:** Dữ liệu đầu vào có thể bị type drift (chuỗi không ép kiểu được hoặc float lẻ trong trường integer) và độ trễ vượt quá SLA mà các lệnh parse lỏng lẻo không phát hiện được.
- **Prompt / request to agent:** Triển khai type validation nghiêm ngặt và contract-level freshness checking.
- **Agent proposal:** Viết hàm `_validate_type` riêng cho `integer`, `number`, `string`, `datetime`, `boolean` và kiểm tra `max_delay_minutes` theo UTC.
- **Evidence/test:** Bắt được các lỗi timestamp cũ (`stale_kb`) và kiểu dữ liệu sai lệch mà không làm gãy các trường hợp hợp lệ.
- **Accept / reject / revise:** Accept.
- **Why:** Tăng cường tính phòng thủ ngay tại cửa ngõ ingestion.

## Decision 2: Thay thế Z-Score bằng Robust Anomaly Detection (MAD + Context-Aware Seasonality)
- **Hypothesis:** Z-score tính toán trên Mean và Std rất dễ bị lệch khi lịch sử có outlier, đồng thời không nhận biết được chu kỳ ngày trong tuần (cuối tuần volume giảm tự nhiên dẫn đến false positive).
- **Prompt / request to agent:** Cải tiến hàm `detect_anomaly` và chế độ `auto` để xử lý outlier và seasonality.
- **Agent proposal:** Sử dụng Median Absolute Deviation (MAD) kèm cơ chế fallback khi `mad=0`, kết hợp `same_segment_history` và `day_of_week` trong `context`.
- **Evidence/test:** Bắt chính xác `volume_drop` (score > 8.0) trong khi không báo lỗi giả khi lượng đơn ổn định hoặc có sự kiện đã biết.
- **Accept / reject / revise:** Accept.
- **Why:** Giảm thiểu đáng kể Alert Fatigue cho đội ngũ on-call.

## Decision 3: Triển khai Google SRE Multi-Window Multi-Burn-Rate Alerting
- **Hypothesis:** Cảnh báo dựa trên 1 cửa sổ đơn lẻ dễ bị kích hoạt bởi các đợt tăng đột biến ngắn hạn (transient spike) không đe dọa ngân sách lỗi tổng thể.
- **Prompt / request to agent:** Cài đặt hàm `evaluate_multiwindow_burn`.
- **Agent proposal:** Yêu cầu cả 2 cửa sổ short window (1h) và long window (6h) cùng vượt ngưỡng mới kích hoạt Page khẩn cấp; nếu chỉ short window tăng thì hạ severity xuống info/warning.
- **Evidence/test:** Phân biệt chính xác giữa spike ngắn hạn (`page=False`) và sustained fast burn (`page=True, severity=critical`).
- **Accept / reject / revise:** Accept.
- **Why:** Đúng chuẩn thực hành SRE quốc tế, tối ưu hóa độ tin cậy của hệ thống cảnh báo.
