# Incident Report

## Severity
P1 - Critical (Revenue Calculation Inaccuracy & Stale Support Knowledge Base)

## Summary
Hệ thống phát hiện đồng thời 3 bất thường trong chuỗi dữ liệu:
1. Đơn hàng bị trùng lặp Primary Key (`order_id`) gây sai lệch dữ liệu staging và mart.
2. Lưu lượng đơn hàng sụt giảm đột ngột 75% (Partial Ingestion Fault) mà pipeline ETL không báo lỗi runtime.
3. Tài liệu Knowledge Base của AI Support Bot bị trễ cập nhật (-3 giờ), khiến khách hàng nhận thông tin chính sách hoàn tiền cũ.

## Detection
- Signal: Data Contract validation (`unique`, `freshness`), Statistical Anomaly Detector (`auto:mad`), dbt singular tests, và RAG metric drift detector.
- First observed time: 2026-08-29T14:48:00Z

## Root Cause
1. Upstream transactional database đẩy dữ liệu trùng khóa chính và phân mảnh gói tin khi truyền tải qua network.
2. Quá trình sync KB documents bị treo background worker, dẫn đến timestamp `published_at` bị trôi quá SLA 60 phút.

## Evidence
1. `validate_orders`: Check `unique` trên `order_id` fail với duplicate rows được phát hiện.
2. `detect_metric`: Row count sụt giảm từ ~1000 xuống 250 rows, MAD score = 8.5 (> 3.5 threshold).
3. `contract_validator`: Check `freshness` trên `kb_documents` ghi nhận delay 180 phút (vượt quá max_delay_minutes = 60).
4. `fct_daily_revenue`: Báo cáo doanh thu sụt giảm tương ứng khi lưu lượng đơn giảm.

## Blast Radius

```text
raw_orders -> stg_orders -> fct_daily_revenue -> CEO Dashboard
raw_kb_documents -> kb_documents -> Support AI Knowledge Base -> Support Agent
```

## Mitigation
1. Cách ly (Quarantine) các bản ghi vi phạm tại tầng Ingestion bằng Data Contract Validator trước khi nạp vào staging.
2. Kích hoạt Backfill và Re-ingest từ upstream transaction logs.
3. Restart Knowledge Base sync worker để nạp tài liệu mới nhất.

## Recovery
- Re-run `python scripts/reset_lab.py` để khôi phục baseline sạch.
- Re-run `python scripts/run_baseline.py` và `pytest tests_public -v` để xác nhận mọi checks đều xanh.

## Verification
- [x] Contract healthy
- [x] dbt tests healthy
- [x] anomaly returned to expected range
- [x] SLO healthy / budget understood
- [x] downstream output verified

## Prevention / Action Items
| Action | Owner | Deadline | Why |
|---|---|---|---|
| Chặn tự động (Block Ingestion) khi vi phạm Critical Contract | Data Platform | 2026-09-05 | Ngăn dữ liệu rác lan sang Data Mart |
| Thêm Alerting Multi-window Burn-rate cho SLO | SRE Team | 2026-09-07 | Phát hiện nhanh tình trạng cháy budget |
| Thêm Unit Test cho logic Join SCD khách hàng | Analytics Engineer | 2026-09-08 | Tránh duplicate revenue khi join |
