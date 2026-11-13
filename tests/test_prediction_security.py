import uuid
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from app.models.edge import Edge
from app.schemas.prediction import PredictionRequest
from app.services.prediction_service import PredictionService


def test_prediction_request_max_length_minutes_ahead():
    # Length 24 is allowed
    req = PredictionRequest(minutes_ahead=list(range(1, 25)))
    assert len(req.minutes_ahead) == 24

    # Length 25 must raise ValidationError
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=list(range(1, 26)))


def test_get_forecast_does_not_commit_or_save(monkeypatch):
    mock_session = MagicMock()
    edge_id = uuid.uuid4()
    mock_edge = Edge(
        edge_id=edge_id,
        edge_code="EDGE_01",
        max_speed_limit=50,
        street_name="Pho Hue",
        length_km=1.0,
        from_node_id=uuid.uuid4(),
        to_node_id=uuid.uuid4(),
    )
    mock_session.get.return_value = mock_edge

    mock_save = MagicMock()
    monkeypatch.setattr(PredictionService, "_save_or_update_prediction", mock_save)

    req = PredictionRequest(edge_id=edge_id, minutes_ahead=[30, 60])
    res = PredictionService.get_forecast(mock_session, req)

    assert res.edge_id == edge_id
    # Critical security assertion: get_forecast must be read-only and NOT mutate shared DB state
    mock_save.assert_not_called()
    mock_session.commit.assert_not_called()


def test_forecast_endpoint_rate_limiter_configured():
    from app.main import app
    from app.api.v1.endpoints.predictions import get_traffic_forecast

    # Verify route exists in openapi schema
    assert "/api/v1/predictions/forecast" in app.openapi()["paths"]
    # Verify limiter wrapper is applied
    assert hasattr(get_traffic_forecast, "__wrapped__")


