"""Seed script to populate prominent Hanoi intersections (Nodes) and road segments (Edges)."""

import logging
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, select

from app.core.database import engine, init_db
from app.models.edge import Edge
from app.models.node import Node

logger = logging.getLogger(__name__)

HANOI_NODES = [
    {
        "node_code": "NODE_NTS",
        "node_name": "Ngã tư Sở",
        "district": "Đống Đa",
        "latitude": 21.0025,
        "longitude": 105.8198,
    },
    {
        "node_code": "NODE_CG",
        "node_name": "Nút giao Cầu Giấy",
        "district": "Cầu Giấy",
        "latitude": 21.0332,
        "longitude": 105.7985,
    },
    {
        "node_code": "NODE_KDT",
        "node_name": "Ngã tư Khuất Duy Tiến - Nguyễn Trãi",
        "district": "Thanh Xuân",
        "latitude": 20.9942,
        "longitude": 105.8021,
    },
    {
        "node_code": "NODE_TDH",
        "node_name": "Nút giao Trần Duy Hưng - Hoàng Đạo Thúy",
        "district": "Cầu Giấy",
        "latitude": 21.0098,
        "longitude": 105.8012,
    },
    {
        "node_code": "NODE_KM",
        "node_name": "Nút giao Kim Mã - Liễu Giai",
        "district": "Ba Đình",
        "latitude": 21.0315,
        "longitude": 105.8136,
    },
    {
        "node_code": "NODE_XD",
        "node_name": "Ô Chợ Dừa - Xã Đàn",
        "district": "Đống Đa",
        "latitude": 21.0185,
        "longitude": 105.8282,
    },
    {
        "node_code": "NODE_GP",
        "node_name": "Ngã tư Vọng - Giải Phóng",
        "district": "Hai Bà Trưng",
        "latitude": 20.9984,
        "longitude": 105.8415,
    },
    {
        "node_code": "NODE_DCV",
        "node_name": "Ngã tư Đại Cồ Việt - Giải Phóng",
        "district": "Hai Bà Trưng",
        "latitude": 21.0089,
        "longitude": 105.8432,
    },
    {
        "node_code": "NODE_BHK",
        "node_name": "Quảng trường Đông Kinh Nghĩa Thục (Bờ Hồ)",
        "district": "Hoàn Kiếm",
        "latitude": 21.0319,
        "longitude": 105.8524,
    },
    {
        "node_code": "NODE_MD",
        "node_name": "Nút giao Mai Dịch - Hồ Tùng Mậu",
        "district": "Cầu Giấy",
        "latitude": 21.0385,
        "longitude": 105.7768,
    },
    # ==== NODES bổ sung để mở rộng lưới đường ====
    {
        "node_code": "NODE_GIAIPHONG_CN",
        "node_name": "Ngã tư Chùa Nga - Giải Phóng",
        "district": "Thanh Xuân",
        "latitude": 20.9880,
        "longitude": 105.8440,
    },
    {
        "node_code": "NODE_GIAPBAT",
        "node_name": "Bến xe Giáp Bát",
        "district": "Hoàng Mai",
        "latitude": 20.9800,
        "longitude": 105.8470,
    },
    {
        "node_code": "NODE_VVT",
        "node_name": "Nút giao Vũ Tông Phan - Khuất Duy Tiến",
        "district": "Thanh Xuân",
        "latitude": 20.9900,
        "longitude": 105.8080,
    },
    {
        "node_code": "NODE_LINHDAM",
        "node_name": "Nút giao Linh Đàm",
        "district": "Hoàng Mai",
        "latitude": 20.9760,
        "longitude": 105.8210,
    },
    {
        "node_code": "NODE_TTH",
        "node_name": "Nút giao Trần Duy Hưng - The Manor",
        "district": "Cầu Giấy",
        "latitude": 21.0125,
        "longitude": 105.7970,
    },
    {
        "node_code": "NODE_VHC",
        "node_name": "Nút giao Võ Chí Công - Xuân La",
        "district": "Tây Hồ",
        "latitude": 21.0680,
        "longitude": 105.8105,
    },
    {
        "node_code": "NODE_NHATTAN",
        "node_name": "Cầu Nhật Tân (đầu phía Nam)",
        "district": "Tây Hồ",
        "latitude": 21.0620,
        "longitude": 105.8185,
    },
    {
        "node_code": "NODE_HOANGQUOCVIET",
        "node_name": "Ngã tư Hoàng Quốc Việt - Cầu Giấy",
        "district": "Cầu Giấy",
        "latitude": 21.0440,
        "longitude": 105.8055,
    },
    {
        "node_code": "NODE_BUITHIXUAN",
        "node_name": "Ngã tư Bùi Thị Xuân - Thái Hà",
        "district": "Đống Đa",
        "latitude": 21.0120,
        "longitude": 105.8250,
    },
    {
        "node_code": "NODE_MIKE",
        "node_name": "Nút giao Đê La Thành - Kim Mã",
        "district": "Đống Đa",
        "latitude": 21.0260,
        "longitude": 105.8205,
    },
    {
        "node_code": "NODE_MINHKHAI",
        "node_name": "Ngã tư Minh Khai - Vĩnh Tuy",
        "district": "Hai Bà Trưng",
        "latitude": 20.9995,
        "longitude": 105.8510,
    },
    {
        "node_code": "NODE_TAMTRINH",
        "node_name": "Nút giao Tam Trinh - Kim Đồng",
        "district": "Hoàng Mai",
        "latitude": 20.9885,
        "longitude": 105.8560,
    },
    {
        "node_code": "NODE_LACLONGQUAN",
        "node_name": "Lạc Long Quân - Nhật Tân",
        "district": "Tây Hồ",
        "latitude": 21.0580,
        "longitude": 105.8060,
    },
    {
        "node_code": "NODE_THUYKHUE",
        "node_name": "Thụy Khuê - Xuân La",
        "district": "Tây Hồ",
        "latitude": 21.0665,
        "longitude": 105.8245,
    },
]

HANOI_EDGES = [
    # Ngã tư Sở <-> Cầu Giấy qua Đường Láng
    {
        "edge_code": "EDGE_LANG_UP",
        "street_name": "Đường Láng",
        "from_code": "NODE_NTS",
        "to_code": "NODE_CG",
        "length_km": 4.1,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_LANG_DOWN",
        "street_name": "Đường Láng",
        "from_code": "NODE_CG",
        "to_code": "NODE_NTS",
        "length_km": 4.1,
        "max_speed_limit": 50,
    },
    # Ngã tư Sở <-> Khuất Duy Tiến qua Nguyễn Trãi
    {
        "edge_code": "EDGE_NT_OUT",
        "street_name": "Đường Nguyễn Trãi",
        "from_code": "NODE_NTS",
        "to_code": "NODE_KDT",
        "length_km": 2.2,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_NT_IN",
        "street_name": "Đường Nguyễn Trãi",
        "from_code": "NODE_KDT",
        "to_code": "NODE_NTS",
        "length_km": 2.2,
        "max_speed_limit": 60,
    },
    # Khuất Duy Tiến <-> Trần Duy Hưng qua Vành đai 3
    {
        "edge_code": "EDGE_VD3_UP",
        "street_name": "Đường Khuất Duy Tiến",
        "from_code": "NODE_KDT",
        "to_code": "NODE_TDH",
        "length_km": 1.8,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_VD3_DOWN",
        "street_name": "Đường Khuất Duy Tiến",
        "from_code": "NODE_TDH",
        "to_code": "NODE_KDT",
        "length_km": 1.8,
        "max_speed_limit": 60,
    },
    # Cầu Giấy <-> Mai Dịch qua Xuân Thủy
    {
        "edge_code": "EDGE_XT_OUT",
        "street_name": "Đường Xuân Thủy",
        "from_code": "NODE_CG",
        "to_code": "NODE_MD",
        "length_km": 2.5,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_XT_IN",
        "street_name": "Đường Xuân Thủy",
        "from_code": "NODE_MD",
        "to_code": "NODE_CG",
        "length_km": 2.5,
        "max_speed_limit": 50,
    },
    # Cầu Giấy <-> Kim Mã
    {
        "edge_code": "EDGE_CG_KM",
        "street_name": "Đường Cầu Giấy - Kim Mã",
        "from_code": "NODE_CG",
        "to_code": "NODE_KM",
        "length_km": 2.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_KM_CG",
        "street_name": "Đường Kim Mã - Cầu Giấy",
        "from_code": "NODE_KM",
        "to_code": "NODE_CG",
        "length_km": 2.0,
        "max_speed_limit": 50,
    },
    # Ngã tư Sở <-> Ô Chợ Dừa qua Tây Sơn
    {
        "edge_code": "EDGE_TS_IN",
        "street_name": "Đường Tây Sơn",
        "from_code": "NODE_NTS",
        "to_code": "NODE_XD",
        "length_km": 2.1,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_TS_OUT",
        "street_name": "Đường Tây Sơn",
        "from_code": "NODE_XD",
        "to_code": "NODE_NTS",
        "length_km": 2.1,
        "max_speed_limit": 50,
    },
    # Ô Chợ Dừa <-> Giải Phóng qua Xã Đàn - Đại Cồ Việt
    {
        "edge_code": "EDGE_XD_DCV",
        "street_name": "Đường Xã Đàn",
        "from_code": "NODE_XD",
        "to_code": "NODE_DCV",
        "length_km": 1.9,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_DCV_XD",
        "street_name": "Đường Xã Đàn",
        "from_code": "NODE_DCV",
        "to_code": "NODE_XD",
        "length_km": 1.9,
        "max_speed_limit": 50,
    },
    # Ngã tư Vọng <-> Đại Cồ Việt qua Giải Phóng
    {
        "edge_code": "EDGE_GP_UP",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_GP",
        "to_code": "NODE_DCV",
        "length_km": 1.5,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_GP_DOWN",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_DCV",
        "to_code": "NODE_GP",
        "length_km": 1.5,
        "max_speed_limit": 50,
    },
    # Đại Cồ Việt <-> Bờ Hồ qua Phố Huế - Hàng Bài
    {
        "edge_code": "EDGE_PH_UP",
        "street_name": "Đường Phố Huế - Hàng Bài",
        "from_code": "NODE_DCV",
        "to_code": "NODE_BHK",
        "length_km": 2.8,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_PH_DOWN",
        "street_name": "Đường Bà Triệu",
        "from_code": "NODE_BHK",
        "to_code": "NODE_DCV",
        "length_km": 2.8,
        "max_speed_limit": 40,
    },
    # ==== EDGES bổ sung - các trục mới để đa dạng dữ liệu màu ====
    # Giải Phóng kéo dài (thường kẹt nặng giờ cao điểm)
    {
        "edge_code": "EDGE_GP_CN",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_GP",
        "to_code": "NODE_GIAIPHONG_CN",
        "length_km": 1.6,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_CN_GB",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_GIAIPHONG_CN",
        "to_code": "NODE_GIAPBAT",
        "length_km": 1.2,
        "max_speed_limit": 60,
    },
    # Vành Đai 3 phía Nam qua Khuất Duy Tiến - Vũ Tông Phan (kẹt nặng)
    {
        "edge_code": "EDGE_KDT_VTP",
        "street_name": "Đường Khuất Duy Tiến",
        "from_code": "NODE_KDT",
        "to_code": "NODE_VVT",
        "length_km": 1.4,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_VTP_LD",
        "street_name": "Đường Vũ Tông Phan",
        "from_code": "NODE_VVT",
        "to_code": "NODE_LINHDAM",
        "length_km": 2.3,
        "max_speed_limit": 50,
    },
    # Trần Duy Hưng kéo dài (kẹt nặng giờ chiều)
    {
        "edge_code": "EDGE_TDH_MANOR",
        "street_name": "Đường Trần Duy Hưng",
        "from_code": "NODE_TDH",
        "to_code": "NODE_TTH",
        "length_km": 0.8,
        "max_speed_limit": 50,
    },
    # Võ Chí Công - cầu Nhật Tân (rộng, thoáng)
    {
        "edge_code": "EDGE_VCC_NT",
        "street_name": "Đường Võ Chí Công",
        "from_code": "NODE_VHC",
        "to_code": "NODE_NHATTAN",
        "length_km": 1.1,
        "max_speed_limit": 80,
    },
    # Cầu Giấy kéo dài - Hoàng Quốc Việt
    {
        "edge_code": "EDGE_CG_HQV",
        "street_name": "Đường Cầu Giấy",
        "from_code": "NODE_CG",
        "to_code": "NODE_HOANGQUOCVIET",
        "length_km": 1.5,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_HQV_VCC",
        "street_name": "Đường Hoàng Quốc Việt",
        "from_code": "NODE_HOANGQUOCVIET",
        "to_code": "NODE_VHC",
        "length_km": 2.7,
        "max_speed_limit": 50,
    },
    # Thai Hà - Chùa Bộc (kẹt do đông dân cư)
    {
        "edge_code": "EDGE_TH_BTX",
        "street_name": "Đường Thái Hà",
        "from_code": "NODE_THUYKHUE",
        "to_code": "NODE_BUITHIXUAN",
        "length_km": 1.3,
        "max_speed_limit": 40,
    },
    # Đê La Thành (vành đai nội đô)
    {
        "edge_code": "EDGE_KM_MK",
        "street_name": "Đường Đê La Thành",
        "from_code": "NODE_KM",
        "to_code": "NODE_MIKE",
        "length_km": 1.4,
        "max_speed_limit": 50,
    },
    # Minh Khai - Tam Trinh (Nam Hà Nội)
    {
        "edge_code": "EDGE_MK_TT",
        "street_name": "Đường Minh Khai",
        "from_code": "NODE_MINHKHAI",
        "to_code": "NODE_TAMTRINH",
        "length_km": 1.7,
        "max_speed_limit": 50,
    },
    # Lạc Long Quân dọc hồ Tây (thoáng)
    {
        "edge_code": "EDGE_LLQ_TK",
        "street_name": "Đường Lạc Long Quân",
        "from_code": "NODE_LACLONGQUAN",
        "to_code": "NODE_THUYKHUE",
        "length_km": 2.0,
        "max_speed_limit": 50,
    },
]


def seed_network(db_session: Session | None = None) -> None:
    if db_session is not None:
        import app.models  # noqa: F401

        SQLModel.metadata.create_all(db_session.get_bind())
        session = db_session
    else:
        init_db()
        session = Session(engine)
    try:
        # 1. Seed Nodes
        code_to_node = {}
        for n_data in HANOI_NODES:
            existing = session.exec(
                select(Node).where(Node.node_code == n_data["node_code"])
            ).first()
            if not existing:
                node = Node(**n_data)
                session.add(node)
                session.commit()
                session.refresh(node)
                code_to_node[node.node_code] = node
            else:
                code_to_node[existing.node_code] = existing

        # 2. Seed Edges
        for e_data in HANOI_EDGES:
            existing_edge = session.exec(
                select(Edge).where(Edge.edge_code == e_data["edge_code"])
            ).first()
            if not existing_edge:
                edge = Edge(
                    edge_code=e_data["edge_code"],
                    street_name=e_data["street_name"],
                    from_node_id=code_to_node[e_data["from_code"]].node_id,
                    to_node_id=code_to_node[e_data["to_code"]].node_id,
                    length_km=e_data["length_km"],
                    max_speed_limit=e_data["max_speed_limit"],
                )
                session.add(edge)
        session.commit()
        print(f"Successfully seeded {len(HANOI_NODES)} nodes and {len(HANOI_EDGES)} edges.")
    finally:
        if db_session is None:
            session.close()


if __name__ == "__main__":
    seed_network()
