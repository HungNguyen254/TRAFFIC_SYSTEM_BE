"""Script to generate realistic synthetic historical traffic data for Hanoi road network."""

import csv
import random
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_hanoi_network import HANOI_EDGES


def generate_dataset(
    output_path: str = "data/synthetic_traffic_dataset.csv", num_days: int = 30
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "edge_code",
        "street_name",
        "length_km",
        "max_speed_limit",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "is_rush_hour",
        "weather_code",  # 0: Sunny, 1: Rain, 2: Heavy Rain
        "average_speed",
        "congestion_level",
        "risk_factor",
    ]

    random.seed(42)
    rows = []

    for day in range(num_days):
        day_of_week = day % 7
        is_weekend = 1 if day_of_week in (5, 6) else 0

        for edge in HANOI_EDGES:
            max_speed = float(edge["max_speed_limit"])

            for hour in range(24):
                is_rush_hour = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0

                # Weather probability
                weather_prob = random.random()
                if weather_prob < 0.70:
                    weather_code = 0  # Sunny
                elif weather_prob < 0.90:
                    weather_code = 1  # Light rain
                else:
                    weather_code = 2  # Heavy rain

                # Calculate base speed factor
                base_factor = 0.85
                if is_rush_hour and not is_weekend:
                    base_factor -= random.uniform(0.35, 0.55)
                elif is_rush_hour and is_weekend:
                    base_factor -= random.uniform(0.15, 0.30)
                elif 0 <= hour <= 5:
                    base_factor = random.uniform(0.90, 0.98)
                else:
                    base_factor -= random.uniform(0.05, 0.20)

                # Weather impact
                if weather_code == 1:
                    base_factor -= random.uniform(0.08, 0.15)
                elif weather_code == 2:
                    base_factor -= random.uniform(0.20, 0.35)

                # Clamp factor
                factor = max(0.15, min(0.98, base_factor))
                avg_speed = round(max_speed * factor, 1)

                if avg_speed >= 35.0:
                    level = 1
                elif avg_speed >= 25.0:
                    level = 2
                elif avg_speed >= 15.0:
                    level = 3
                else:
                    level = 4

                risk_factor = round(max(0.0, min(1.0, 1.0 - factor)), 2)

                rows.append(
                    {
                        "edge_code": edge["edge_code"],
                        "street_name": edge["street_name"],
                        "length_km": edge["length_km"],
                        "max_speed_limit": edge["max_speed_limit"],
                        "hour_of_day": hour,
                        "day_of_week": day_of_week,
                        "is_weekend": is_weekend,
                        "is_rush_hour": is_rush_hour,
                        "weather_code": weather_code,
                        "average_speed": avg_speed,
                        "congestion_level": level,
                        "risk_factor": risk_factor,
                    }
                )

    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} traffic records saved to {output_path}")


if __name__ == "__main__":
    generate_dataset()
