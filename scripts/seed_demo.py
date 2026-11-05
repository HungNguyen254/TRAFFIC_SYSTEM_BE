import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import hash_password
from app.models.segment import Segment
from app.models.observation import TrafficObservation
from app.models.user import User, UserRole

SEED_SEGMENTS = [
    {
        "name": "Đường Nguyễn Trãi",
        "start_lat": 20.9984,
        "start_lng": 105.8130,
        "end_lat": 20.9856,
        "end_lng": 105.7958,
        "length_m": 4200.0,
        "road_type": "primary",
        "free_flow_speed_kmh": 60.0,
    },
    {
        "name": "Đường Giải Phóng",
        "start_lat": 20.9950,
        "start_lng": 105.8420,
        "end_lat": 20.9670,
        "end_lng": 105.8450,
        "length_m": 3500.0,
        "road_type": "primary",
        "free_flow_speed_kmh": 60.0,
    },
    {
        "name": "Đường Cầu Giấy",
        "start_lat": 21.0330,
        "start_lng": 105.7980,
        "end_lat": 21.0360,
        "end_lng": 105.7820,
        "length_m": 2800.0,
        "road_type": "secondary",
        "free_flow_speed_kmh": 50.0,
    },
    {
        "name": "Đường Kim Mã",
        "start_lat": 21.0315,
        "start_lng": 105.8235,
        "end_lat": 21.0325,
        "end_lng": 105.8070,
        "length_m": 2400.0,
        "road_type": "secondary",
        "free_flow_speed_kmh": 50.0,
    },
    {
        "name": "Đại lộ Thăng Long",
        "start_lat": 21.0040,
        "start_lng": 105.7890,
        "end_lat": 21.0010,
        "end_lng": 105.7050,
        "length_m": 8000.0,
        "road_type": "motorway",
        "free_flow_speed_kmh": 100.0,
    },
]


def seed_data() -> None:
    random.seed(42)

    with Session(engine) as session:
        # 0. Seed default Admin and User if not exist
        admin_user = session.exec(select(User).where(User.username == "admin")).first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@traffic.local",
                hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            print("Seeded default Admin: admin / admin123")

        regular_user = session.exec(select(User).where(User.username == "user")).first()
        if not regular_user:
            regular_user = User(
                username="user",
                email="user@traffic.local",
                hashed_password=hash_password("user123"),
                role=UserRole.USER,
                is_active=True,
            )
            session.add(regular_user)
            print("Seeded default User: user / user123")

        session.commit()

        # 1. Insert or fetch segments
        segments: list[Segment] = []
        for seg_data in SEED_SEGMENTS:
            existing = session.exec(
                select(Segment).where(Segment.name == seg_data["name"])
            ).first()
            if not existing:
                new_seg = Segment(**seg_data)
                session.add(new_seg)
                session.commit()
                session.refresh(new_seg)
                segments.append(new_seg)
            else:
                segments.append(existing)

        print(f"Loaded/Created {len(segments)} segments.")

        # 2. Generate 14 days of observations (every 15 minutes)
        # End time fixed to 2026-11-05 12:00:00 naive UTC
        end_time = datetime(2026, 11, 5, 12, 0, 0)
        start_time = end_time - timedelta(days=14)

        current_time = start_time
        timestamps: list[datetime] = []
        while current_time <= end_time:
            timestamps.append(current_time)
            current_time += timedelta(minutes=15)

        total_obs = 0
        for seg in segments:
            # Check existing observations for this segment
            existing_ts = set(
                session.exec(
                    select(TrafficObservation.timestamp).where(
                        TrafficObservation.segment_id == seg.id
                    )
                ).all()
            )

            new_observations: list[TrafficObservation] = []
            for ts in timestamps:
                if ts in existing_ts:
                    continue

                hour = ts.hour
                free_speed = seg.free_flow_speed_kmh

                # Determine speed multiplier based on rush hour patterns
                if 7 <= hour < 9:
                    # Morning rush hour
                    speed_ratio = random.uniform(0.25, 0.45)
                    vehicles = random.randint(180, 320)
                elif 17 <= hour < 19:
                    # Evening rush hour
                    speed_ratio = random.uniform(0.20, 0.40)
                    vehicles = random.randint(200, 350)
                elif 22 <= hour or hour < 6:
                    # Night quiet hours
                    speed_ratio = random.uniform(0.85, 1.00)
                    vehicles = random.randint(15, 60)
                else:
                    # Normal daytime hours
                    speed_ratio = random.uniform(0.55, 0.80)
                    vehicles = random.randint(80, 160)

                speed = round(free_speed * speed_ratio, 1)

                new_observations.append(
                    TrafficObservation(
                        segment_id=seg.id,  # type: ignore[arg-type]
                        timestamp=ts,
                        avg_speed_kmh=speed,
                        vehicle_count=vehicles,
                    )
                )

            if new_observations:
                # Insert in chunks of 1000
                chunk_size = 1000
                for i in range(0, len(new_observations), chunk_size):
                    session.add_all(new_observations[i : i + chunk_size])
                    session.commit()
                total_obs += len(new_observations)

        print(f"Inserted {total_obs} new observations across {len(segments)} segments.")


if __name__ == "__main__":
    seed_data()
