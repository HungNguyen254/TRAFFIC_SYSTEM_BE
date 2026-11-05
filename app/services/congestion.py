THRESHOLD_FREE = 0.75
THRESHOLD_BUSY = 0.50
THRESHOLD_HEAVY = 0.25

CONGESTION_FREE = "free"
CONGESTION_BUSY = "busy"
CONGESTION_HEAVY = "heavy"
CONGESTION_JAM = "jam"


def calculate_congestion_level(speed_kmh: float, free_flow_speed_kmh: float) -> str:
    """
    Calculate congestion level from speed / free_flow_speed_kmh:
      >= 0.75: 'free'
      >= 0.50: 'busy'
      >= 0.25: 'heavy'
      otherwise: 'jam'
    """
    if free_flow_speed_kmh <= 0:
        return CONGESTION_JAM
    ratio = speed_kmh / free_flow_speed_kmh
    if ratio >= THRESHOLD_FREE:
        return CONGESTION_FREE
    elif ratio >= THRESHOLD_BUSY:
        return CONGESTION_BUSY
    elif ratio >= THRESHOLD_HEAVY:
        return CONGESTION_HEAVY
    return CONGESTION_JAM
