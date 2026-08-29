# Changelog

Bảng theo dõi các lỗi, nguyên nhân gốc và giải pháp khắc phục trong quá trình vận hành và kiểm thử hệ thống Data Reliability.

| Ngày | Lỗi / Vấn đề | Nguyên nhân gốc | Giải pháp khắc phục |
|---|---|---|---|
| 2026-08-29 | Type drift & String coercion không được phát hiện | Starter `contract_validator.py` dùng `pd.to_numeric(errors='coerce')` làm âm thầm che giấu lỗi định dạng | Bổ sung hàm `_validate_type` kiểm tra kiểu nghiêm ngặt cho `integer`, `number`, `string`, `datetime`, `boolean` |
| 2026-08-29 | Bỏ sót kiểm tra độ trễ dữ liệu (Freshness) | Chưa tích hợp cấu hình `freshness` ở cấp dataset contract | Thêm kiểm tra `freshness` so khớp max timestamp của cột thời gian với thời gian hiện tại theo UTC |
| 2026-08-29 | False Alert khi có Outlier hoặc chu kỳ tuần | `zscore_detector` phụ thuộc vào Mean và Std vốn rất nhạy cảm với outlier và không nhận diện `day_of_week` | Triển khai `mad_detector` (Median Absolute Deviation) xử lý trường hợp `mad=0` và chế độ `auto` nhận diện context (seasonality, known_event) |
| 2026-08-29 | Column Lineage chỉ trả về direct children | `get_column_downstream` thiếu duyệt đệ quy/hàng đợi | Nâng cấp thuật toán duyệt BFS kèm tập hợp `seen` để lấy toàn bộ transitive downstream columns |
| 2026-08-29 | Alert Fatigue do transient spike trong SLO | Chưa áp dụng Multi-window Multi-burn-rate policy theo chuẩn Google SRE | Cài đặt `evaluate_multiwindow_burn` kết hợp cả 2 cửa sổ short (1h) và long (6h) để phân biệt spike tức thời và sustained burn |
| 2026-08-29 | Phình doanh thu trong dbt model do join duplicate active customer | Bảng `stg_customers` có thể có nhiều hơn 1 bản ghi active cho cùng 1 customer | Thêm singular test `assert_no_duplicate_active_customers.sql` và dbt unit test kiểm thử logic gom nhóm |
