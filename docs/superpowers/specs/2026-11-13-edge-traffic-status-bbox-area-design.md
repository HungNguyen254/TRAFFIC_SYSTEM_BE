# Thiết kế API: Truy vấn tình trạng mới nhất của các đoạn đường theo Bounding Box hoặc Khu Vực

## 1. Mục đích (Intent & Why)
Người dùng/Frontend cần xem tình trạng giao thông mới nhất của các đoạn đường (edges) theo góc nhìn bản đồ (khung hiển thị hiện tại - Bounding Box) hoặc theo địa giới hành chính (Quận/Khu vực), kèm theo thời điểm dữ liệu được cập nhật (`updated_at`).

## 2. Mục tiêu (Goals & Non-goals)
### Mục tiêu (Goals)
- Cung cấp endpoint chuyên biệt `GET /api/v1/edges/status` trả về tình trạng các đoạn đường:
  - Lọc theo Bounding Box: hỗ trợ truyền 4 tọa độ riêng lẻ `min_lat`, `min_lng`, `max_lat`, `max_lng` hoặc chuỗi `bbox=min_lng,min_lat,max_lng,max_lat` (hoặc `min_lat,min_lng,max_lat,max_lng`).
  - Lọc theo Khu vực: tham số `district` hoặc `area` (hỗ trợ tìm kiếm tiếng Việt không dấu, không phân biệt hoa thường).
  - Trả về thời điểm cập nhật (`updated_at`) ở cả cấp phản hồi chung và từng đoạn đường.
  - Tình trạng bao gồm: tốc độ (`speed`), mức độ ùn tắc (`congestion_level` từ 1-4), nhãn trạng thái (`congestion_text`), giới hạn tốc độ, thông tin điểm đầu/cuối (`from_node`, `to_node`).
- Mở rộng hỗ trợ bộ lọc tương thích ngược trên `GET /api/v1/edges` để các client cũ vẫn có thể truyền bbox/district và nhận trường `updated_at`.
- Đảm bảo kiểm thử tự động (unit/integration test) kiểm tra đầy đủ các kịch bản lọc và trường dữ liệu.
- Tạo Pull Request lên GitHub repo và cung cấp link PR.

### Phi mục tiêu (Non-goals)
- Không can thiệp sửa đổi cấu trúc bảng cơ sở dữ liệu (`edges`, `nodes`) vì cấu trúc hiện tại đã có đủ tọa độ `lat`, `lng` và `district`.

## 3. Các phương án kiến trúc (Approaches)
- **Phương án 1 (Được chọn)**: Xây dựng endpoint chuẩn hóa `GET /api/v1/edges/status` với Schema Pydantic rõ ràng, đồng thời nâng cấp `GET /api/v1/edges` hiện có để hỗ trợ thêm các bộ lọc tương tự.
  - *Ưu điểm*: Tách bạch rõ API phục vụ cập nhật trạng thái (status polling/streaming view) với API nạp toàn bộ đồ thị mạng lưới; schema rõ ràng; hoàn toàn tương thích ngược.
- **Phương án 2**: Chỉ thêm tham số lọc vào `GET /api/v1/edges`.
  - *Nhược điểm*: `GET /api/v1/edges` trả về cấu trúc gồm cả danh sách `nodes` và `edges` lớn, cồng kềnh khi client chỉ cần lấy trạng thái các đoạn đường đang hiển thị trên bản đồ.

## 4. Chi tiết kỹ thuật (Technical Specifications)

### 4.1. Schemas (`app/schemas/edge_status.py`)
- `NodeBrief`:
  - `node_code`: str
  - `node_name`: str
  - `district`: str | None
  - `lat`: float
  - `lng`: float
- `EdgeStatusItem`:
  - `edge_id`: UUID
  - `edge_code`: str
  - `street_name`: str
  - `length_km`: float
  - `max_speed_limit`: int
  - `from_node`: NodeBrief | None
  - `to_node`: NodeBrief | None
  - `speed`: float
  - `congestion_level`: int
  - `congestion_text`: str (e.g., "Thông thoáng", "Di chuyển chậm", "Ùn tắc nghiêm trọng", "Kẹt xe hoàn toàn")
  - `updated_at`: datetime
- `EdgeStatusResponse`:
  - `total`: int
  - `updated_at`: datetime
  - `filters`: dict (bbox, district, hour, day_of_week)
  - `edges`: list[EdgeStatusItem]

### 4.2. Logic lọc trong `TrafficService` (`app/services/traffic_service.py`)
- Hàm `get_edges_status(...)`:
  - Lấy danh sách nodes và edges từ DB.
  - Lọc theo Bounding Box: Một đoạn đường (edge) được coi là nằm trong bounding box nếu điểm đầu `from_node` hoặc điểm cuối `to_node` nằm trong phạm vi tọa độ `[min_lat, max_lat]` và `[min_lng, max_lng]`.
  - Lọc theo Khu vực: Một đoạn đường được coi là thuộc khu vực nếu `from_node.district` hoặc `to_node.district` khớp với chuỗi tìm kiếm (sử dụng hàm `strip_accents` để so sánh không phân biệt dấu/hoa thường).
  - Tình trạng giao thông: Sử dụng snapshot `get_edge_traffic_snapshot` tính từ dataset/dự báo theo giờ hiện tại (hoặc giờ truyền vào).
  - Thời điểm cập nhật: Trả về timestamp hiện tại (UTC/Local) theo chuẩn ISO-8601.

### 4.3. API Endpoint (`app/api/v1/endpoints/edges.py`)
- Thêm `GET /api/v1/edges/status`:
  - Query parameters:
    - `min_lat`: float | None
    - `min_lng`: float | None
    - `max_lat`: float | None
    - `max_lng`: float | None
    - `bbox`: str | None (hỗ trợ `min_lng,min_lat,max_lng,max_lat` hoặc `min_lat,min_lng,max_lat,max_lng`)
    - `district`: str | None
    - `area`: str | None (alias cho district)
    - `hour`: int | None (mặc định giờ hiện tại)
    - `day_of_week`: int | None (mặc định ngày hiện tại)
  - Validation: kiểm tra `min_lat <= max_lat`, `min_lng <= max_lng`.
- Nâng cấp `GET /api/v1/edges`:
  - Tiếp nhận thêm các query parameters trên, lọc nodes và edges theo tiêu chí, và bổ sung `updated_at` trong data payload.

## 5. Kế hoạch kiểm thử (Testing Plan)
- Viết test trong `tests/test_edges_status.py`:
  - Test lấy toàn bộ trạng thái không có filter: kiểm tra cấu trúc phản hồi có `updated_at`, `speed`, `congestion_level`.
  - Test lọc theo Bounding Box: kiểm tra chỉ trả về các đoạn đường có tọa độ nằm trong khung.
  - Test lọc theo Khu vực / District: kiểm tra lọc theo quận (có dấu và không dấu).
  - Test xử lý lỗi tọa độ không hợp lệ (`min_lat > max_lat`).
