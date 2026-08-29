# KỊCH BẢN THUYẾT TRÌNH: DATA RELIABILITY COMMAND CENTER
**Thời lượng đề xuất**: 3 – 5 phút  
**Tác giả**: Nguyễn Hùng Mạnh  
**Mục tiêu**: Trình bày mạch lạc, tự tin, kết hợp thao tác trực tiếp trên Dashboard để đạt điểm tối đa và bảo vệ trọn vẹn +30 điểm Bonus.

---

## CHUẨN BỊ TRƯỚC KHI BẮT ĐẦU (10 giây)
1. Mở sẵn trình duyệt tại màn hình Dashboard: `http://localhost:8000`.
2. Bấm nút **Reset Lab** trên Quick Action Bar để đưa hệ thống về trạng thái `HEALTHY` sạch sẽ nhất.
3. Đứng thẳng, giọng nói dõng dạc, tự tin.

---

## NỘI DUNG THUYẾT TRÌNH (TỪNG PHÚT TỪNG CÂU)

### ⏱️ PHẦN 1: MỞ ĐẦU & ĐẶT VẤN ĐỀ (0:00 – 0:45)

> *"Kính thưa thầy/cô và ban giám khảo,*
> 
> *Trong các hệ thống dữ liệu hiện đại, nguy cơ lớn nhất không phải là code bị lỗi làm sập pipeline — vì loại lỗi này rất dễ phát hiện. Nguy cơ nguy hiểm nhất là **Lỗi dữ liệu thầm lặng (Silent Data Corruption)**: Pipeline vẫn chạy thành công, không hề báo lỗi, nhưng số liệu nạp vào Data Warehouse bị sai lệch, dẫn tới các quyết định kinh doanh sai lầm của ban giám đốc.*
> 
> *Đến với bài thi hôm nay, em đã xây dựng **Hệ thống phòng thủ dữ liệu 6 lớp (6-Layer Defense-in-Depth Architecture)** kết hợp với **Data Reliability Command Center** để phát hiện, cách ly và cảnh báo sự cố dữ liệu theo thời gian thực chuẩn Google SRE."*

---

### ⏱️ PHẦN 2: DEMO TRỰC TIẾP TRÊN DASHBOARD (0:45 – 2:45)

*(Anh nhìn vào màn hình Dashboard và bắt đầu thao tác theo từng bước)*

#### 1. Tổng quan hệ thống (Tab Overview)
> *"Đầu tiên, trên màn hình **Overview**, Dashboard hiển thị 6 chỉ số cốt lõi: Số lượng đơn hàng, độ trễ Freshness đạt chuẩn SLA dưới 60 phút, và **Ngân sách lỗi (Error Budget) đang đạt 100%** với mục tiêu cam kết chất lượng **SLO = 99.90%** (tức là chỉ cho phép tỷ lệ lỗi tối đa là 0.100%). Trạng thái toàn hệ thống hiện tại là **HEALTHY**."*

#### 2. Thử nghiệm Lớp 1 — Data Contracts (Bấm nút `Duplicate PK`)
*(Anh bấm nút `Duplicate PK` trên thanh Quick Action Bar)*
> *"Bây giờ, em giả lập một sự cố: Hacker hoặc hệ thống upstream gửi một batch đơn hàng bị **trùng lặp khóa chính (Duplicate Primary Key)**.*
> 
> *Ngay lập tức, tầng **Data Contract** tại cửa khẩu Ingestion Gate đã chặn đứng batch dữ liệu này. Status chuyển sang **CRITICAL**, kích hoạt chính sách **BLOCK** pipeline và gửi cảnh báo vi phạm tính duy nhất. Toàn bộ Data Warehouse được bảo vệ an toàn."*
*(Anh bấm nút `Reset Lab` để trở về trạng thái sạch)*

#### 3. Thử nghiệm Lớp 4 — Statistical Anomaly (Bấm nút `Volume Drop` $\rightarrow$ Chuyển sang Tab `Anomaly`)
*(Anh bấm nút `Volume Drop` rồi click vào Tab `Anomaly`)*
> *"Tiếp theo là kịch bản nguy hiểm nhất: **Sụt giảm 75% dữ liệu (Volume Drop từ 600 xuống 150 đơn)** mà không hề có lỗi cú pháp.*
> 
> *Trên biểu đồ 42 ngày, dữ liệu của chúng ta có tính chu kỳ: ngày thường 600 đơn, cuối tuần 200 đơn. Nếu dùng thuật toán Z-Score thông thường sẽ bị báo động giả vào cuối tuần. 
> Hệ thống của em đã giải quyết triệt để bằng cách kết hợp **Seasonality Baseline theo thứ trong tuần** và thuật toán thống kê bền vững **MAD (Median Absolute Deviation)**. Khi volume rớt đột ngột, điểm dị thường nhảy lên 5.53 (> 3.5), hệ thống ngay lập tức gắn cờ **ANOMALY**."*

#### 4. Thử nghiệm Lớp 5 — Interactive Lineage & Blast Radius (Chuyển sang Tab `Lineage`)
*(Anh click vào Tab `Lineage` và click vào node `stg_orders`)*
> *"Tại Tab **Lineage**, hệ thống mô hình hóa toàn bộ đồ thị quan hệ dữ liệu. Khi em click vào node `stg_orders`, thuật toán **BFS (Breadth-First Search)** tự động truy vết và vẽ đường nét đứt màu đỏ/cam thể hiện **Bán kính ảnh hưởng (Blast Radius)**: Cho Data Engineer biết sự cố tại `stg_orders` sẽ làm sai lệch bảng doanh thu `fct_daily_revenue` và dashboard báo cáo `ceo_revenue_dashboard` của Giám đốc."*

#### 5. Thử nghiệm Lớp 6 — Multi-Window SLO Alerting (Chuyển sang Tab `SLO`)
*(Anh click vào Tab `SLO` và bấm thử 2 nút preset)*
> *"Tại Tab **SLO**, hệ thống áp dụng thuật toán **Multi-Window Multi-Burn-Rate** chuẩn Google SRE:
> * Khi bấm `Transient Spike` (Lỗi bộc phát 1-2 giây rồi tắt): Short window cao nhưng Long window thấp $\rightarrow$ Hệ thống tự động **Suppress (chặn báo động)** để kỹ sư không bị mệt mỏi vì tin nhắn rác (chống Alert Fatigue).
> * Khi bấm `Sustained Fast Burn` (Lỗi kéo dài liên tục $14.4\times$): Hệ thống lập tức kích hoạt **PAGE ON-CALL (CRITICAL)** để gọi kỹ sư trực ca xử lý ngay lập tức."*

---

### ⏱️ PHẦN 3: KẾT QUẢ VÀ ĐIỂM KỸ THUẬT NỔI BẬT (2:45 – 3:30)

> *"Về mặt kiểm thử và chất lượng code:
> 1. Toàn bộ **21/21 bài kiểm thử tự động (Public Tests)** đều Passed 100%.
> 2. Tích hợp chuẩn **Great Expectations 1.21** với Fluent API, BatchDefinition và Checkpoints.
> 3. Tầng dbt được trang bị **dbt Native Unit Tests** nạp mock data để vạch trần lỗi **Fan-out Join của SCD Type 2 dimension** làm nhân đôi doanh thu.
> 4. Mở rộng giám sát chất lượng **GenAI & RAG Observability**: Tự động bắt lỗi trôi dạt độ dài văn bản (Token Length Collapse) và độ trôi vector embedding ($\ell_2$-norm mean drift).
> 5. Hoàn thành trọn vẹn **+30 điểm Bonus kỹ thuật**."*

---

### ⏱️ PHẦN 4: KẾT LUẬN & SẴN SÀNG VẤN ĐÁP (3:30 – 4:00)

> *"Tóm lại, hệ thống của em đã giải quyết trọn vẹn bài toán Data Reliability từ khâu tiền định (Data Contracts), kiểm chuẩn chất lượng (Great Expectations, dbt), phát hiện dị thường thống kê (MAD, KS-Test), truy vết ảnh hưởng (Lineage BFS), cho đến quản trị độ tin cậy chuẩn SRE.
> 
> Em xin chân thành cảm ơn thầy/cô và ban giám khảo đã lắng nghe. Em rất sẵn lòng trả lời các câu hỏi vấn đáp ạ!"*

---

## PHẦN 3: CHEAT-SHEET TRẢ LỜI CÂU HỎI VẤN ĐÁP (DEFEND Q&A)

### Q1: "Tại sao em lại dùng thuật toán MAD thay vì Z-Score truyền thống?"
* **Trả lời**: *"Z-Score phụ thuộc vào Mean (trung bình) và Standard Deviation (độ lệch chuẩn). Khi trong lịch sử có 1 đợt lỗi cực lớn (outlier), Mean và Std sẽ bị kéo dãn ra làm mất độ nhạy. Thuật toán MAD sử dụng Median (trung vị), nên hoàn toàn miễn nhiễm với các điểm ngoại lai trong quá khứ, giúp phát hiện dị thường chính xác hơn rất nhiều."*

### Q2: "Sự khác nhau cơ bản giữa Great Expectations và dbt tests là gì?"
* **Trả lời**: *"dbt tests tập trung kiểm tra dữ liệu sau khi chuyển đổi trong Data Warehouse (In-Warehouse Transformations). Trong khi Great Expectations đóng vai trò là Quality Checkpoint toàn diện hơn, hỗ trợ kiểm tra dữ liệu từ lúc Ingestion (Pandas/Spark/SQL), tự động xuất Data Docs báo cáo và tích hợp chặt chẽ vào CI/CD pipeline."*

### Q3: "Tại sao cần cơ chế Multi-Window Alerting thay vì chỉ đặt 1 ngưỡng cảnh báo đơn giản?"
* **Trả lời**: *"Nếu chỉ dùng 1 cửa sổ ngắn (1h), một lỗi chập chờn thoáng qua (Transient Spike) sẽ liên tục đánh thức kỹ sư trực đêm, gây ra hội chứng Alert Fatigue (kiệt sức vì báo động giả). Ngược lại, nếu chỉ dùng 1 cửa sổ dài (24h) thì khi hệ thống bị sập nặng, phải mất cả ngày mới nhận được thông báo. Google SRE Multi-Window kết hợp cả 1h và 6h: vừa phát hiện nhanh sự cố lớn, vừa triệt tiêu được báo động giả."*
