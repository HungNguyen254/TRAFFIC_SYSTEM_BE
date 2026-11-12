"""Script to generate realistic synthetic historical traffic data for Hanoi road network."""

import csv
import random
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_hanoi_network import HANOI_EDGES

# "Mức độ kẹt" đặc trưng của từng trục (0.0 = rất thoáng, 1.0 = luôn kẹt).
# Giúp dataset sinh ra đa dạng màu: trục lớn/thoáng -> xanh, trục nội đô/kẹt -> đỏ.
EDGE_CONGESTION_PROFILE = {
    # ---- Trục chính, rộng, thường thông thoáng (xanh) ----
    "EDGE_VCC_NT": 0.05,       # Võ Chí Công - cầu Nhật Tân
    "EDGE_LLQ_TK": 0.10,       # Lạc Long Quân dọc hồ Tây
    "EDGE_XT_OUT": 0.15,       # Xuân Thủy
    "EDGE_XT_IN": 0.18,
    "EDGE_CG_HQV": 0.22,       # Cầu Giấy - Hoàng Quốc Việt
    "EDGE_HQV_VCC": 0.25,
    "EDGE_MK_TT": 0.30,        # Minh Khai - Tam Trinh
    "EDGE_CG_KM": 0.35,        # Cầu Giấy - Kim Mã
    "EDGE_TS_IN": 0.38,        # Tây Sơn
    "EDGE_TS_OUT": 0.40,
    "EDGE_KM_MK": 0.42,        # Đê La Thành
    "EDGE_XD_DCV": 0.45,       # Xã Đàn - Đại Cồ Việt
    "EDGE_DCV_XD": 0.48,
    "EDGE_LANG_UP": 0.50,      # Đường Láng (trung bình)
    "EDGE_LANG_DOWN": 0.52,
    "EDGE_PH_UP": 0.55,        # Phố Huế - Hàng Bài (nội đô đông)
    "EDGE_PH_DOWN": 0.58,      # Bà Triệu
    "EDGE_NT_OUT": 0.62,       # Nguyễn Trãi (hay kẹt)
    "EDGE_NT_IN": 0.65,
    "EDGE_VD3_UP": 0.68,       # Khuất Duy Tiến (nút giao Vành đai 3)
    "EDGE_VD3_DOWN": 0.70,
    "EDGE_TDH_MANOR": 0.72,    # Trần Duy Hưng (kẹt giờ chiều)
    "EDGE_GP_UP": 0.74,        # Giải Phóng (kẹt giờ cao điểm)
    "EDGE_GP_DOWN": 0.76,
    "EDGE_GP_CN": 0.78,
    "EDGE_CN_GB": 0.82,        # Giải Phóng kéo dài - Giáp Bát
    "EDGE_KDT_VTP": 0.85,      # Khuất Duy Tiến - Vũ Tông Phan (kẹt nặng)
    "EDGE_TH_BTX": 0.88,       # Thái Hà (nội đô, kẹt nặng)
    "EDGE_VTP_LD": 0.92,       # Vũ Tông Phan - Linh Đàm (kẹt nặng nhất)
}


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
                # Mỗi trục có "nền kẹt" riêng (profile) -> dataset đa dạng 4 màu
                profile = EDGE_CONGESTION_PROFILE.get(edge["edge_code"], 0.45)
                base_factor = 0.90 - profile * 0.55  # 0.05 .. 0.87
                if is_rush_hour and not is_weekend:
                    base_factor -= random.uniform(0.30, 0.45) * (0.6 + profile)
                elif is_rush_hour and is_weekend:
                    base_factor -= random.uniform(0.10, 0.25)
                elif 0 <= hour <= 5:
                    base_factor = min(0.95, base_factor + random.uniform(0.15, 0.30))
                else:
                    base_factor -= random.uniform(0.05, 0.15)

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
