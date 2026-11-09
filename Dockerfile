# Sử dụng Python 3.12 slim làm base image
FROM python:3.12-slim

# Cài đặt uv từ image chính thức của Astral
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Thiết lập thư mục làm việc
WORKDIR /app

# Cấu hình biến môi trường tối ưu cho uv và runtime Python
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy lockfile và file cấu hình gói trước để cache dependencies
COPY pyproject.toml uv.lock ./

# Cài đặt dependencies (bỏ qua dev dependencies để image nhẹ nhất)
RUN uv sync --frozen --no-install-project --no-dev

# Copy toàn bộ mã nguồn dự án
COPY . .

# Cài đặt chính dự án
RUN uv sync --frozen --no-dev

# Thêm virtual environment vào PATH
ENV PATH="/app/.venv/bin:$PATH"

# Mở cổng dịch vụ FastAPI
EXPOSE 8000

# Lệnh khởi chạy ứng dụng mặc định
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
