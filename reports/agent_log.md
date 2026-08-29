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

## Decision 4: Fix dbt Native Unit Test dùng key không hợp lệ (`expect_failure`) làm sập toàn bộ `make dbt`
- **Hypothesis:** Unit test `scd_duplicate_customer_inflates_revenue` dùng `expect_failure: true` để "expose" bug fan-out join khi SCD customer dimension có 2 active row/customer_id. Đây không phải property hợp lệ trong schema unit test của dbt 1.12 (dbt parse lỗi ngay từ đầu), khiến `dbt build` dừng lại trước khi chạy bất kỳ model/test nào khác.
- **Prompt / request to agent:** Rà soát lại tại sao `make dbt` báo `Parsing Error` và sửa cho `dbt build` chạy sạch hoàn toàn.
- **Agent proposal:** (1) Sửa `fct_daily_revenue.sql`: dedupe `active_customers` còn đúng 1 dòng/`customer_id` (`ROW_NUMBER() OVER (PARTITION BY customer_id ...) = 1`) trước khi LEFT JOIN, loại bỏ fan-out. (2) Sửa `unit_tests.yml`: bỏ `expect_failure`, đổi `expect.rows` về giá trị đúng theo business logic (1 row / 100.0) — test giờ xác nhận model đã fix bug, không còn dựa vào hành vi sai để pass.
- **Evidence/test:** `dbt build --project-dir dbt_project --profiles-dir dbt_project` → `Done. PASS=20 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=20`. Trước khi sửa: `ERROR` ngay bước parsing, 6/20 node bị SKIP.
- **Accept / reject / revise:** Accept.
- **Why:** Không chỉ viết test phát hiện bug (yêu cầu "Strong challenge" Phase 2) mà còn khắc phục root cause trong model, đồng thời đảm bảo `make dbt` — lệnh chuẩn theo README — chạy được trọn vẹn khi chấm điểm.

## Decision 5: Fix false positive anomaly trên baseline khỏe vào cuối tuần
- **Hypothesis:** `data/baseline/orders.csv` là sample tĩnh cố định 600 dòng bất kể ngày trong tuần, nhưng `data/history/metrics_history.csv` có seasonality thật (thứ 7/CN chỉ ~235–274 dòng/ngày so với ~565–651 ngày thường). `scripts/run_baseline.py` truyền segment cuối tuần (không phải toàn bộ lịch sử) làm tham số `history` cho `detect_anomaly`, khiến seasonal-MAD luôn báo `is_anomaly=True` trên baseline khỏe mỗi khi chạy vào thứ 7/CN — mâu thuẫn với Decision 2 (giảm alert fatigue) và yêu cầu Phase 0 (baseline phải chạy sạch).
- **Prompt / request to agent:** Sửa để anomaly detector không báo động giả trên baseline khỏe, nhưng vẫn phải bắt được `volume_drop` fault thật.
- **Agent proposal:** (1) `scripts/run_baseline.py`: truyền `history` luôn là toàn bộ row-count lịch sử (30 ngày gần nhất), tách biệt với `context.same_segment_history` (chỉ chứa segment theo ngày trong tuần) — đúng thiết kế mô tả trong `docs/STUDENT_API.md`. (2) `observability/anomaly.py` (`detect_anomaly`, method=`auto`): khi seasonal segment báo anomaly nhưng giá trị hiện tại vẫn nằm trong dải bình thường của lịch sử toàn cục (global MAD không coi là anomaly), hạ verdict xuống `False` và ghi rõ lý do (`+global_crosscheck`) thay vì tin tưởng mù quáng một segment hẹp (5-8 điểm).
- **Evidence/test:** Baseline khỏe (`make reset` → `run_baseline.py`) vào thứ 7: trước fix `is_anomaly=True, score=18.75`; sau fix `is_anomaly=False` (`auto:seasonal_mad+global_crosscheck`). `volume_drop` fault (150/600 rows) vẫn `is_anomaly=True, score=5.53` sau fix — không bị che giấu. `duplicate_pk` và `stale_kb` không đổi hành vi (không phụ thuộc row-count anomaly). 18/18 `tests_public` vẫn pass.
- **Accept / reject / revise:** Accept.
- **Why:** Một seasonal baseline chỉ dựa vào 5-8 điểm dữ liệu hẹp dễ tự tin thái quá; đối chiếu với lịch sử toàn cục trước khi kết luận anomaly là thực hành robust-baseline chuẩn, và ngăn "cry wolf" làm giảm độ tin cậy của cảnh báo — đúng tinh thần chống Alert Fatigue đã đặt ra ở Decision 2.
