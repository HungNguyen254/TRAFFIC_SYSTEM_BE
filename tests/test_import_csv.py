import csv
from pathlib import Path
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
