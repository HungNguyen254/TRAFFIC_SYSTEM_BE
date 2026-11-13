"""Script to import historical traffic CSV dataset into database table."""

import argparse
import csv
import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete
from sqlmodel import Session

from app.core.database import engine, init_db
from app.models.traffic_data import TrafficData

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
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
}


def import_traffic_csv(
    csv_path: str | Path,
    session: Session,
    batch_size: int = 1000,
    truncate: bool = False,
) -> int:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Traffic CSV file not found: {path}")

    total_inserted = 0
    batch: list[TrafficData] = []

    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fields
        if missing:
            raise ValueError(f"Missing required columns in CSV: {sorted(missing)}")

        if truncate:
            logger.info("Truncating existing records in traffic_data table...")
            session.exec(delete(TrafficData))
            session.commit()

        for line_num, row in enumerate(reader, start=2):
            try:
                record = TrafficData(
                    edge_code=str(row["edge_code"]).strip(),
                    street_name=str(row["street_name"]).strip(),
                    length_km=float(row["length_km"]),
                    max_speed_limit=int(float(row["max_speed_limit"])),
                    hour_of_day=int(row["hour_of_day"]),
                    day_of_week=int(row["day_of_week"]),
                    is_weekend=int(row["is_weekend"]),
                    is_rush_hour=int(row["is_rush_hour"]),
                    weather_code=float(row["weather_code"]),
                    average_speed=float(row["average_speed"]),
                    congestion_level=int(row["congestion_level"]),
                    risk_factor=float(row["risk_factor"]),
                )
                batch.append(record)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping invalid row at line %d: %s", line_num, exc
                )
                continue

            if len(batch) >= batch_size:
                session.add_all(batch)
                session.commit()
                total_inserted += len(batch)
                batch = []

        if batch:
            session.add_all(batch)
            session.commit()
            total_inserted += len(batch)

    logger.info("Successfully imported %d traffic records into database.", total_inserted)
    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Import traffic CSV data into database table.")
    parser.add_argument(
        "--csv-path",
        type=str,
        default="data/synthetic_traffic_dataset.csv",
        help="Path to the CSV file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database insertion",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Clear existing traffic_data before importing",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    init_db()

    with Session(engine) as session:
        count = import_traffic_csv(
            csv_path=args.csv_path,
            session=session,
            batch_size=args.batch_size,
            truncate=args.truncate,
        )
        print(f"Import completed: {count} records imported into traffic_data.")


if __name__ == "__main__":
    main()
