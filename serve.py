"""Cửa HTTP của agent theo hợp đồng AgentCore Runtime (Day 58).

Runtime không import ask() — nó gửi HTTP vào container:
  GET  /ping         → health check, trả {"status": "Healthy"}
  POST /invocations  → {"question": "...", "customer_id": "C003"} → hợp đồng công khai của ask()
Cổng 8080, host 0.0.0.0, image ARM64 (docs AgentCore: runtime-http-protocol-contract).

customer_id nằm trong payload — VÌ SAO an toàn: Runtime để xác thực IAM (SigV4), khách KHÔNG gọi
thẳng được; chỉ backend có quyền IAM gọi được, và backend điền customer_id từ JWT đã kiểm (API
Gateway + Cognito, Day sau). Không bao giờ mở Runtime cho trình duyệt gọi trực tiếp với kiểu này.

as_of_date KHÔNG nhận từ payload: người gọi đặt được "hôm nay" là sửa được kết quả đổi trả/bảo hành.
Nó đến từ cấu hình triển khai (env AS_OF_DATE; production để trống = ngày thật).

Chạy local:  uvicorn serve:app --port 8080
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agents.graph import ask

# Log của các node (route, latency, token — không nội dung) ra stdout → CloudWatch trên Runtime
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("serve")

app = FastAPI(title="support-agent", docs_url=None, redoc_url=None, openapi_url=None)


class Invocation(BaseModel):
    """Payload hợp lệ. Sai → FastAPI tự trả 422, request không chạm tới graph (không tốn token)."""

    model_config = ConfigDict(extra="forbid")   # trường lạ (vd "as_of_date") → 422, không lặng lẽ bỏ qua
    # strip rồi mới đo: "   " là rỗng. 2000 ký tự: câu hỏi CSKH thật vài chục chữ — chặn prompt
    # dài cố tình đốt token (chi phí Bedrock tính theo token input)
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    customer_id: Annotated[str, Field(pattern=r"^C\d{3,6}$")]   # định dạng của sample-data


@app.get("/ping")
async def ping():
    # async + không làm gì nặng → vẫn trả lời ngay cả khi /invocations đang bận (xem dưới)
    return {"status": "Healthy"}


@app.post("/invocations")
def invocations(req: Invocation):
    # `def` thường, KHÔNG `async def`: ask() chặn (gọi Bedrock/DynamoDB đồng bộ vài giây).
    # FastAPI chạy hàm `def` trong threadpool → event loop rảnh để trả /ping. Viết `async def` mà
    # gọi code chặn bên trong thì cả server đứng → Runtime ping không được → coi container hỏng.
    try:
        return ask(req.question, req.customer_id)
    except Exception:
        # Traceback vào log để mình debug; người gọi chỉ nhận mã lỗi chung — không trả str(e) như
        # ví dụ của AWS docs (lộ tên bảng, ARN, chi tiết nội bộ)
        log.exception("invocation failed")
        return JSONResponse(status_code=500, content={"error": "internal_error"})
