from fastapi import FastAPI, Request, status

from app.core.config import settings
from app.core.response import StandardResponse, success_response
from app.middlewares.middleware import setup_middleware

app = FastAPI(title="Traffic System BE", version="1.0.0")

setup_middleware(app)


@app.get(
    "/api/data",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="API root",
    tags=["system"],
)
def root(request: Request):
    return success_response(
        request=request, message="Chào mừng đến với hệ thống dự báo tắc đường"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG
    )
