import csv
from pathlib import Path
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.traffic_data import TrafficData
from scripts.import_traffic_csv_to_db import import_traffic_csv


def test_import_traffic_csv_success(tmp_path: Path):
    csv_file = tmp_path / "traffic_sample.csv"
    fieldnames = [
        "edge_code",
        "street_name",
        "length_km",
        "max_speed_limit",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "is_rush_hour",
        "weather_code",
        "average_speed",
        "congestion_level",
        "risk_factor",
    ]
    rows = [
        {
            "edge_code": f"EDGE_{i}",
            "street_name": "Nguyen Trai",
            "length_km": "2.5",
            "max_speed_limit": "50",
            "hour_of_day": "8",
            "day_of_week": "2",
            "is_weekend": "0",
            "is_rush_hour": "1",
            "weather_code": "0",
            "average_speed": "25.0",
            "congestion_level": "2",
            "risk_factor": "0.5",
        }
        for i in range(5)
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        count = import_traffic_csv(csv_path=csv_file, session=session, batch_size=2)
        assert count == 5
        records = session.exec(select(TrafficData)).all()
        assert len(records) == 5

        # Test truncate option
        count2 = import_traffic_csv(csv_path=csv_file, session=session, batch_size=2, truncate=True)
        assert count2 == 5
        records2 = session.exec(select(TrafficData)).all()
        assert len(records2) == 5


def test_import_traffic_csv_missing_columns_raises_value_error(tmp_path: Path):
    csv_file = tmp_path / "incomplete.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        f.write("edge_code,street_name\nEDGE_1,Street 1\n")

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        with pytest.raises(ValueError, match="Missing required columns"):
            import_traffic_csv(csv_path=csv_file, session=session)


def test_import_traffic_csv_skips_invalid_rows(tmp_path: Path):
    csv_file = tmp_path / "corrupted_rows.csv"
    fieldnames = [
        "edge_code",
        "street_name",
        "length_km",
        "max_speed_limit",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "is_rush_hour",
        "weather_code",
        "average_speed",
        "congestion_level",
        "risk_factor",
    ]
    rows = [
        # Valid row 1
        {
            "edge_code": "EDGE_1",
            "street_name": "Valid 1",
            "length_km": "2.5",
            "max_speed_limit": "50",
            "hour_of_day": "8",
            "day_of_week": "2",
            "is_weekend": "0",
            "is_rush_hour": "1",
            "weather_code": "0",
            "average_speed": "25.0",
            "congestion_level": "2",
            "risk_factor": "0.5",
        },
        # Invalid row (non-numeric hour)
        {
            "edge_code": "EDGE_2",
            "street_name": "Invalid Row",
            "length_km": "abc",
            "max_speed_limit": "50",
            "hour_of_day": "invalid",
            "day_of_week": "2",
            "is_weekend": "0",
            "is_rush_hour": "1",
            "weather_code": "0",
            "average_speed": "25.0",
            "congestion_level": "2",
            "risk_factor": "0.5",
        },
        # Valid row 2
        {
            "edge_code": "EDGE_3",
            "street_name": "Valid 2",
            "length_km": "1.8",
            "max_speed_limit": "40",
            "hour_of_day": "9",
            "day_of_week": "2",
            "is_weekend": "0",
            "is_rush_hour": "1",
            "weather_code": "0",
            "average_speed": "30.0",
            "congestion_level": "1",
            "risk_factor": "0.25",
        },
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Invalid row should be skipped, 2 valid rows should be imported
        count = import_traffic_csv(csv_path=csv_file, session=session)
        assert count == 2
        records = session.exec(select(TrafficData)).all()
        assert len(records) == 2
        assert {r.edge_code for r in records} == {"EDGE_1", "EDGE_3"}
