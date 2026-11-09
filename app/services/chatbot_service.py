import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.models.edge import Edge
from app.models.user import User
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.schemas.prediction import PredictionRequest
from app.schemas.routing import RouteRequest
from app.services.prediction_service import PredictionService
from app.services.routing_service import RoutingService
from app.services.traffic_service import TrafficService
from app.services.user_data_service import UserDataService

logger = logging.getLogger(__name__)


def get_traffic_forecast(street_name: str, hour_of_day: int = 18, weather: str = "sunny") -> str:
    """Tra cứu dự báo mức độ tắc đường và tốc độ xe chạy trên một tuyến đường theo khung giờ tại Hà Nội."""
    return f"Forecast for {street_name} at {hour_of_day}h"


def find_optimal_route(origin_name: str, destination_name: str, hour_of_day: int = 18) -> str:
    """Tìm lộ trình tối ưu và cảnh báo đoạn đường ùn tắc giữa 2 điểm xuất phát và đích tại Hà Nội."""
    return f"Route from {origin_name} to {destination_name} at {hour_of_day}h"


def get_traffic_hotspots(hour_of_day: int = 18) -> str:
    """Lấy danh sách các tuyến đường đang hoặc dự báo tắc nghẽn nghiêm trọng (mức 3-4) tại Hà Nội."""
    return f"Hotspots at {hour_of_day}h"


def get_user_saved_places() -> str:
    """Lấy danh sách các địa điểm người dùng đã lưu (Nhà riêng, Công ty) để chỉ đường nhanh."""
    return "User saved places"


CHATBOT_TOOLS = [
    get_traffic_forecast,
    find_optimal_route,
    get_traffic_hotspots,
    get_user_saved_places,
]


class ChatbotService:
    @staticmethod
    def _get_client():
        from google import genai

        return genai.Client(api_key=settings.GEMINI_API_KEY)

    @staticmethod
    def _execute_tool(
        session: Session, name: str, args: dict, current_user: User | None = None
    ) -> dict:
        try:
            if name == "get_traffic_forecast":
                street_name = args.get("street_name", "")
                hour = int(args.get("hour_of_day", 18))
                weather = args.get("weather", "sunny")
                req = PredictionRequest(street_name=street_name, hour_of_day=hour, weather=weather)
                forecast = PredictionService.get_forecast(session, req)
                return forecast.model_dump(mode="json")

            elif name == "find_optimal_route":
                origin = args.get("origin_name", "")
                destination = args.get("destination_name", "")
                hour = int(args.get("hour_of_day", 18))
                req = RouteRequest(
                    origin_name=origin, destination_name=destination, hour_of_day=hour
                )
                route = RoutingService.calculate_optimal_route(session, req, current_user)
                return route.model_dump(mode="json")

            elif name == "get_traffic_hotspots":
                hour = int(args.get("hour_of_day", 18))
                edges = session.exec(select(Edge)).all()
                hotspots = []
                for e in edges:
                    p = PredictionService.predict_for_edge(session, e, hour_of_day=hour)
                    if p.congestion_level >= 3:
                        hotspots.append(
                            {
                                "street_name": e.street_name,
                                "congestion_level": p.congestion_level,
                                "predicted_speed": p.predicted_speed,
                                "description": p.description,
                            }
                        )
                return {"hour_of_day": hour, "hotspots": hotspots}

            elif name == "get_user_saved_places":
                if not current_user:
                    return {"message": "Người dùng chưa đăng nhập, không có địa điểm lưu."}
                places = UserDataService.list_saved_places(session, current_user.user_id)
                return {
                    "saved_places": [
                        {"place_name": p.place_name, "address": p.address} for p in places
                    ]
                }

        except Exception as exc:  # noqa: BLE001
            logger.warning("Tool execution error for %s: %s", name, exc)
            edges = session.exec(select(Edge.street_name)).all()
            unique_streets = sorted(set(edges))[:8]
            return {
                "error": str(exc),
                "suggestion": f"Các tuyến đường trọng điểm khả dụng: {', '.join(unique_streets)}",
            }

        return {"error": f"Tool '{name}' không tồn tại."}

    @classmethod
    def _heuristic_fallback(
        cls, session: Session, message: str, hour_of_day: int | None
    ) -> ChatResponse:
        hour = hour_of_day if hour_of_day is not None else 18
        msg_lower = message.lower()

        # Check if looking for route directions
        if "từ" in msg_lower and ("đến" in msg_lower or "sang" in msg_lower or "về" in msg_lower):
            nodes = TrafficService.list_nodes(session)
            matched_nodes = [n for n in nodes if n.node_name.lower() in msg_lower]
            if len(matched_nodes) >= 2:
                req = RouteRequest(
                    origin_id=matched_nodes[0].node_id,
                    destination_id=matched_nodes[1].node_id,
                    hour_of_day=hour,
                )
                try:
                    res = RoutingService.calculate_optimal_route(session, req)
                    reply = (
                        f"Lộ trình tối ưu từ {res.origin.node_name} đến {res.destination.node_name} "
                        f"(khung giờ {hour}h): tổng quãng đường khoảng {res.total_distance_km} km, "
                        f"thời gian di chuyển ước tính {res.estimated_time_minutes} phút."
                    )
                    if res.congestion_warning:
                        reply += f" {res.congestion_warning}"
                    return ChatResponse(reply=reply, suggested_routes=res.model_dump(mode="json"))
                except Exception as e:  # noqa: BLE001
                    logger.debug("Routing fallback error: %s", e)

        # Check if asking about specific street
        edges = session.exec(select(Edge)).all()
        for e in edges:
            if e.street_name.lower() in msg_lower:
                p = PredictionService.predict_for_edge(session, e, hour_of_day=hour)
                reply = (
                    f"Dự báo tình trạng trên tuyến {e.street_name} lúc {hour}h: "
                    f"Tốc độ ước tính đạt {p.predicted_speed} km/h (Mức {p.congestion_level}/4). "
                    f"{p.description}."
                )
                return ChatResponse(reply=reply)

        # General greeting / guide
        reply = (
            "Xin chào! Tôi là Trợ lý AI Giao thông Hà Nội. "
            "Bạn có thể hỏi tôi tình trạng tắc đường (ví dụ: 'Đường Láng lúc 18h có tắc không?') "
            "hoặc chỉ đường (ví dụ: 'Tìm đường từ Ngã tư Sở sang Cầu Giấy tránh kẹt xe')."
        )
        return ChatResponse(reply=reply)

    @classmethod
    def process_chat(
        cls, session: Session, payload: ChatRequest, current_user: User | None = None
    ) -> ChatResponse:
        if not settings.GEMINI_API_KEY:
            return cls._heuristic_fallback(session, payload.message, payload.hour_of_day)

        try:
            client = cls._get_client()

            system_instruction = (
                "Bạn là Trợ lý AI Giao thông Hà Nội thông minh, lịch sự, hỗ trợ người tham gia giao thông. "
                "Bạn có các tools tra cứu dự báo giao thông, tìm lộ trình tối ưu và danh sách điểm nghẽn. "
                "Hãy gọi tool phù hợp khi người dùng hỏi về tuyến đường hoặc chỉ đường, sau đó trả lời súc tích bằng tiếng Việt."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=payload.message,
                config={
                    "system_instruction": system_instruction,
                    "tools": CHATBOT_TOOLS,
                },
            )

            executed_tools = []
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        tool_result = cls._execute_tool(session, fc.name, fc.args, current_user)
                        executed_tools.append({"tool": fc.name, "result": tool_result})

                        # Feed back to model for final natural summary
                        summary_res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=f"Kết quả tra cứu dữ liệu cho câu hỏi '{payload.message}': {tool_result}. Hãy tóm tắt tự nhiên cho người đi đường.",
                        )
                        if summary_res.candidates and summary_res.candidates[0].content.parts:
                            final_text = summary_res.candidates[0].content.parts[0].text
                            return ChatResponse(
                                reply=final_text or "Đã tra cứu dữ liệu thành công.",
                                tool_calls=executed_tools,
                            )

                # Direct text reply without tools
                first_part = response.candidates[0].content.parts[0]
                if getattr(first_part, "text", None):
                    return ChatResponse(reply=first_part.text)

        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini generation failed (%s), switching to heuristic fallback.", exc)

        return cls._heuristic_fallback(session, payload.message, payload.hour_of_day)
