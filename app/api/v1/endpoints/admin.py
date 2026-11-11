import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_admin
from app.models.user import User
from app.services.prediction_service import PredictionService
from scripts.train_prediction_model import train_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _run_retraining() -> None:
    try:
        train_model()
        PredictionService.reload_model()
        logger.info("Background model retraining completed successfully.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Background model retraining failed: %s", exc)


@router.post(
    "/retrain-model",
    response_model=StandardResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Kích hoạt huấn luyện lại mô hình AI dự báo trong background (Admin)",
)
@limiter.limit("2/minute")
def trigger_retrain(
    request: Request,
    background_tasks: BackgroundTasks,
    _admin: Annotated[User, Depends(get_current_admin)],
):
    background_tasks.add_task(_run_retraining)
    return success_response(
        request=request,
        message="Đã tiếp nhận yêu cầu huấn luyện lại mô hình trong tiến trình ngầm",
        data={"status": "processing", "message": "Model training running in background"},
    )
