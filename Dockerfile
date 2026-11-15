# Image cho AgentCore Runtime (Day 58). Runtime BẮT BUỘC linux/arm64 (docs: runtime-http-protocol-
# contract) — build amd64 thì lên cloud lỗi "exec format error". Mac Apple Silicon build arm64 sẵn.
#   docker build --platform linux/arm64 --provenance=false --sbom=false -t support-agent .
# --provenance/--sbom=false: đẩy lên ECR đúng 1 manifest (mặc định BuildKit đẩy image index + manifest
# attestation không tag → ECR basic scan bỏ qua, lifecycle "xoá untagged" có thể xoá mất manifest con).
# Không ghi --platform cố định ở FROM (Docker cảnh báo) — truyền ở lệnh build như trên.
# Python 3.14 = đúng bản requirements đã pin + test (local, CI). Đổi bản = chạy thư viện chưa test.
FROM python:3.14-slim

# Không ghi .pyc (image gọn), log ra ngay không đệm (CloudWatch thấy kịp khi container chết)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Thư viện TRƯỚC, code SAU: Docker cache theo layer — sửa code mà requirements.txt không đổi thì
# tái dùng layer cài thư viện, build lại vài giây thay vì cài lại từ đầu.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Danh sách trắng: chỉ copy đúng code cần chạy (không .env, không test, không dữ liệu)
COPY agents/ agents/
COPY tools/ tools/
COPY serve.py .

# Chạy bằng user thường, không root: code agent bị khai thác cũng không có quyền root trong container
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
