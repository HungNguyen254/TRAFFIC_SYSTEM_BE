"""Seed script to populate prominent Hanoi intersections (Nodes) and road segments (Edges)."""

import json
import logging
import random
import sys
from pathlib import Path

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, select

from app.core.database import engine, init_db
from app.models.edge import Edge
from app.models.node import Node
from app.models.traffic_data import TrafficData

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
        "latitude": 21.01063,
        "longitude": 105.79960,
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
        "latitude": 21.007822,
        "longitude": 105.841468,
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
    {
        "node_code": "NODE_PVD",
        "node_name": "Nút giao Phạm Văn Đồng - Hoàng Quốc Việt",
        "district": "Bắc Từ Liêm",
        "latitude": 21.0461,
        "longitude": 105.7825,
    },
    {
        "node_code": "NODE_HQV",
        "node_name": "Nút giao Hoàng Quốc Việt - Nguyễn Văn Huyên",
        "district": "Cầu Giấy",
        "latitude": 21.0452,
        "longitude": 105.7981,
    },
    {
        "node_code": "NODE_NVH",
        "node_name": "Nút giao Nguyễn Văn Huyên - Nguyễn Khánh Toàn",
        "district": "Cầu Giấy",
        "latitude": 21.0417,
        "longitude": 105.8001,
    },
    {
        "node_code": "NODE_NKH",
        "node_name": "Nút giao Nguyễn Khánh Toàn - Cầu Giấy",
        "district": "Cầu Giấy",
        "latitude": 21.0392,
        "longitude": 105.8002,
    },
    {
        "node_code": "NODE_MTX",
        "node_name": "Nút giao Mễ Trì - Phạm Hùng",
        "district": "Nam Từ Liêm",
        "latitude": 21.0065,
        "longitude": 105.7818,
    },
    {
        "node_code": "NODE_LH",
        "node_name": "Nút giao Láng Hạ - Thái Hà",
        "district": "Đống Đa",
        "latitude": 21.0132,
        "longitude": 105.8172,
    },
    {
        "node_code": "NODE_LY",
        "node_name": "Nút giao Láng - Yên Lãng",
        "district": "Đống Đa",
        "latitude": 21.0146,
        "longitude": 105.8153,
    },
    {
        "node_code": "NODE_TH",
        "node_name": "Nút giao Thái Hà - Chùa Bộc",
        "district": "Đống Đa",
        "latitude": 21.0086,
        "longitude": 105.8265,
    },
    {
        "node_code": "NODE_TT",
        "node_name": "Nút giao Trường Chinh - Tôn Thất Tùng",
        "district": "Đống Đa",
        "latitude": 21.0018,
        "longitude": 105.8280,
    },
    {
        "node_code": "NODE_BM",
        "node_name": "Nút giao Bạch Mai - Đại La",
        "district": "Hai Bà Trưng",
        "latitude": 20.9970,
        "longitude": 105.8490,
    },
    {
        "node_code": "NODE_TKC",
        "node_name": "Nút giao Trần Khát Chân - Bạch Mai",
        "district": "Hai Bà Trưng",
        "latitude": 21.008583,
        "longitude": 105.851410,
    },
    {
        "node_code": "NODE_GV",
        "node_name": "Nút giao Giảng Võ - Cát Linh",
        "district": "Ba Đình",
        "latitude": 21.0270,
        "longitude": 105.8260,
    },
    {
        "node_code": "NODE_TDT",
        "node_name": "Nút giao Tôn Đức Thắng - Xã Đàn",
        "district": "Đống Đa",
        "latitude": 21.0240,
        "longitude": 105.8290,
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
    # Mai Dịch <-> Hoàng Quốc Việt qua Phạm Văn Đồng
    {
        "edge_code": "EDGE_MD_PVD",
        "street_name": "Đường Phạm Văn Đồng",
        "from_code": "NODE_MD",
        "to_code": "NODE_PVD",
        "length_km": 1.2,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_PVD_MD",
        "street_name": "Đường Phạm Văn Đồng",
        "from_code": "NODE_PVD",
        "to_code": "NODE_MD",
        "length_km": 1.2,
        "max_speed_limit": 60,
    },
    # Phạm Văn Đồng <-> Nguyễn Văn Huyên qua Hoàng Quốc Việt
    {
        "edge_code": "EDGE_PVD_HQV",
        "street_name": "Đường Hoàng Quốc Việt",
        "from_code": "NODE_PVD",
        "to_code": "NODE_HQV",
        "length_km": 1.7,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_HQV_PVD",
        "street_name": "Đường Hoàng Quốc Việt",
        "from_code": "NODE_HQV",
        "to_code": "NODE_PVD",
        "length_km": 1.7,
        "max_speed_limit": 50,
    },
    # Hoàng Quốc Việt <-> Cầu Giấy qua Nguyễn Văn Huyên - Nguyễn Khánh Toàn
    {
        "edge_code": "EDGE_HQV_NVH",
        "street_name": "Đường Nguyễn Văn Huyên",
        "from_code": "NODE_HQV",
        "to_code": "NODE_NVH",
        "length_km": 0.6,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_NVH_HQV",
        "street_name": "Đường Nguyễn Văn Huyên",
        "from_code": "NODE_NVH",
        "to_code": "NODE_HQV",
        "length_km": 0.6,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_NVH_NKH",
        "street_name": "Đường Nguyễn Khánh Toàn",
        "from_code": "NODE_NVH",
        "to_code": "NODE_NKH",
        "length_km": 0.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_NKH_NVH",
        "street_name": "Đường Nguyễn Khánh Toàn",
        "from_code": "NODE_NKH",
        "to_code": "NODE_NVH",
        "length_km": 0.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_NKH_CG",
        "street_name": "Đường Nguyễn Khánh Toàn",
        "from_code": "NODE_NKH",
        "to_code": "NODE_CG",
        "length_km": 0.7,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_CG_NKH",
        "street_name": "Đường Nguyễn Khánh Toàn",
        "from_code": "NODE_CG",
        "to_code": "NODE_NKH",
        "length_km": 0.7,
        "max_speed_limit": 40,
    },
    # Cầu Giấy <-> Trần Duy Hưng
    {
        "edge_code": "EDGE_CG_TDH",
        "street_name": "Đường Trần Duy Hưng",
        "from_code": "NODE_CG",
        "to_code": "NODE_TDH",
        "length_km": 2.7,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_TDH_CG",
        "street_name": "Đường Trần Duy Hưng",
        "from_code": "NODE_TDH",
        "to_code": "NODE_CG",
        "length_km": 2.7,
        "max_speed_limit": 50,
    },
    # Trần Duy Hưng <-> Mễ Trì qua Phạm Hùng
    {
        "edge_code": "EDGE_TDH_MTX",
        "street_name": "Đường Phạm Hùng",
        "from_code": "NODE_TDH",
        "to_code": "NODE_MTX",
        "length_km": 1.8,
        "max_speed_limit": 60,
    },
    {
        "edge_code": "EDGE_MTX_TDH",
        "street_name": "Đường Phạm Hùng",
        "from_code": "NODE_MTX",
        "to_code": "NODE_TDH",
        "length_km": 1.8,
        "max_speed_limit": 60,
    },
    # Trần Duy Hưng <-> Láng Hạ
    {
        "edge_code": "EDGE_TDH_LH",
        "street_name": "Đường Láng Hạ",
        "from_code": "NODE_TDH",
        "to_code": "NODE_LH",
        "length_km": 1.8,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_LH_TDH",
        "street_name": "Đường Láng Hạ",
        "from_code": "NODE_LH",
        "to_code": "NODE_TDH",
        "length_km": 1.8,
        "max_speed_limit": 50,
    },
    # Láng Hạ <-> Ngã tư Sở qua Láng - Yên Lãng
    {
        "edge_code": "EDGE_LH_LY",
        "street_name": "Đường Láng Hạ",
        "from_code": "NODE_LH",
        "to_code": "NODE_LY",
        "length_km": 0.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_LY_LH",
        "street_name": "Đường Láng Hạ",
        "from_code": "NODE_LY",
        "to_code": "NODE_LH",
        "length_km": 0.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_LY_NTS",
        "street_name": "Đường Láng",
        "from_code": "NODE_LY",
        "to_code": "NODE_NTS",
        "length_km": 1.4,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_NTS_LY",
        "street_name": "Đường Láng",
        "from_code": "NODE_NTS",
        "to_code": "NODE_LY",
        "length_km": 1.4,
        "max_speed_limit": 50,
    },
    # Láng Hạ <-> Xã Đàn qua Thái Hà - Chùa Bộc
    {
        "edge_code": "EDGE_LH_TH",
        "street_name": "Đường Thái Hà",
        "from_code": "NODE_LH",
        "to_code": "NODE_TH",
        "length_km": 1.1,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TH_LH",
        "street_name": "Đường Thái Hà",
        "from_code": "NODE_TH",
        "to_code": "NODE_LH",
        "length_km": 1.1,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TH_XD",
        "street_name": "Đường Tây Sơn",
        "from_code": "NODE_TH",
        "to_code": "NODE_XD",
        "length_km": 1.2,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_XD_TH",
        "street_name": "Đường Tây Sơn",
        "from_code": "NODE_XD",
        "to_code": "NODE_TH",
        "length_km": 1.2,
        "max_speed_limit": 40,
    },
    # Thái Hà <-> Trường Chinh
    {
        "edge_code": "EDGE_TH_TT",
        "street_name": "Đường Chùa Bộc - Trường Chinh",
        "from_code": "NODE_TH",
        "to_code": "NODE_TT",
        "length_km": 1.2,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TT_TH",
        "street_name": "Đường Trường Chinh - Chùa Bộc",
        "from_code": "NODE_TT",
        "to_code": "NODE_TH",
        "length_km": 1.2,
        "max_speed_limit": 40,
    },
    # Trường Chinh <-> Bạch Mai qua Giải Phóng
    {
        "edge_code": "EDGE_TT_GP",
        "street_name": "Đường Trường Chinh",
        "from_code": "NODE_TT",
        "to_code": "NODE_GP",
        "length_km": 2.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_GP_TT",
        "street_name": "Đường Trường Chinh",
        "from_code": "NODE_GP",
        "to_code": "NODE_TT",
        "length_km": 2.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_GP_BM",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_GP",
        "to_code": "NODE_BM",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_BM_GP",
        "street_name": "Đường Giải Phóng",
        "from_code": "NODE_BM",
        "to_code": "NODE_GP",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    # Bạch Mai <-> Đại Cồ Việt qua Trần Khát Chân
    {
        "edge_code": "EDGE_BM_TKC",
        "street_name": "Đường Bạch Mai",
        "from_code": "NODE_BM",
        "to_code": "NODE_TKC",
        "length_km": 0.6,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TKC_BM",
        "street_name": "Đường Bạch Mai",
        "from_code": "NODE_TKC",
        "to_code": "NODE_BM",
        "length_km": 0.6,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TKC_DCV",
        "street_name": "Đường Trần Khát Chân - Đại Cồ Việt",
        "from_code": "NODE_TKC",
        "to_code": "NODE_DCV",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_DCV_TKC",
        "street_name": "Đường Đại Cồ Việt - Trần Khát Chân",
        "from_code": "NODE_DCV",
        "to_code": "NODE_TKC",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    # Giảng Võ <-> Xã Đàn
    {
        "edge_code": "EDGE_GV_XD",
        "street_name": "Đường Tôn Đức Thắng",
        "from_code": "NODE_GV",
        "to_code": "NODE_TDT",
        "length_km": 1.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_XD_GV",
        "street_name": "Đường Tôn Đức Thắng",
        "from_code": "NODE_TDT",
        "to_code": "NODE_GV",
        "length_km": 1.4,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_TDT_XD",
        "street_name": "Đường Xã Đàn",
        "from_code": "NODE_TDT",
        "to_code": "NODE_XD",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    {
        "edge_code": "EDGE_XD_TDT",
        "street_name": "Đường Xã Đàn",
        "from_code": "NODE_XD",
        "to_code": "NODE_TDT",
        "length_km": 1.0,
        "max_speed_limit": 50,
    },
    # Giảng Võ <-> Kim Mã
    {
        "edge_code": "EDGE_GV_KM",
        "street_name": "Đường Giảng Võ",
        "from_code": "NODE_GV",
        "to_code": "NODE_KM",
        "length_km": 1.3,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_KM_GV",
        "street_name": "Đường Giảng Võ",
        "from_code": "NODE_KM",
        "to_code": "NODE_GV",
        "length_km": 1.3,
        "max_speed_limit": 40,
    },
    # Kim Mã <-> Bờ Hồ
    {
        "edge_code": "EDGE_KM_BHK",
        "street_name": "Đường Kim Mã - Nguyễn Thái Học",
        "from_code": "NODE_KM",
        "to_code": "NODE_BHK",
        "length_km": 2.5,
        "max_speed_limit": 40,
    },
    {
        "edge_code": "EDGE_BHK_KM",
        "street_name": "Đường Nguyễn Thái Học - Kim Mã",
        "from_code": "NODE_BHK",
        "to_code": "NODE_KM",
        "length_km": 2.5,
        "max_speed_limit": 40,
    },
]


NODE_SYNC_FIELDS = ("node_name", "district", "latitude", "longitude")


def _sync_node(node: Node, n_data: dict[str, str | float]) -> bool:
    """Cập nhật node đã có theo dữ liệu seed. Trả về True nếu có thay đổi."""
    changed = False
    for field in NODE_SYNC_FIELDS:
        if getattr(node, field) != n_data[field]:
            setattr(node, field, n_data[field])
            changed = True
    return changed


def _is_straight_line_geom(geom: str | None) -> bool:
    if not geom:
        return False
    try:
        coordinates = json.loads(geom).get("coordinates")
    except (TypeError, ValueError, AttributeError):
        return False
    return isinstance(coordinates, list) and len(coordinates) <= 2


def _build_traffic_profile(
    edge_data: dict[str, str | float | int], hour: int, day_of_week: int
) -> TrafficData:
    edge_code = str(edge_data["edge_code"])
    max_speed = int(edge_data["max_speed_limit"])
    is_weekend = int(day_of_week in (5, 6))
    is_rush_hour = int(7 <= hour <= 9 or 17 <= hour <= 19)
    rng = random.Random(f"{edge_code}:{day_of_week}:{hour}")

    weather_roll = rng.random()
    if weather_roll < 0.70:
        weather_code = 0
    elif weather_roll < 0.90:
        weather_code = 1
    else:
        weather_code = 2

    factor = 0.85
    if is_rush_hour and not is_weekend:
        factor -= rng.uniform(0.35, 0.55)
    elif is_rush_hour:
        factor -= rng.uniform(0.15, 0.30)
    elif hour <= 5:
        factor = rng.uniform(0.90, 0.98)
    else:
        factor -= rng.uniform(0.05, 0.20)

    if weather_code == 1:
        factor -= rng.uniform(0.08, 0.15)
    elif weather_code == 2:
        factor -= rng.uniform(0.20, 0.35)

    factor = max(0.15, min(0.98, factor))
    average_speed = round(max_speed * factor, 1)
    if average_speed >= 35:
        congestion_level = 1
    elif average_speed >= 25:
        congestion_level = 2
    elif average_speed >= 15:
        congestion_level = 3
    else:
        congestion_level = 4

    return TrafficData(
        edge_code=edge_code,
        street_name=str(edge_data["street_name"]),
        length_km=float(edge_data["length_km"]),
        max_speed_limit=max_speed,
        hour_of_day=hour,
        day_of_week=day_of_week,
        is_weekend=is_weekend,
        is_rush_hour=is_rush_hour,
        weather_code=float(weather_code),
        average_speed=average_speed,
        congestion_level=congestion_level,
        risk_factor=round(1.0 - factor, 2),
    )


def _seed_traffic_profiles(session: Session) -> int:
    edge_codes = [str(edge["edge_code"]) for edge in HANOI_EDGES]
    existing_profiles = set(
        session.exec(
            select(
                TrafficData.edge_code,
                TrafficData.hour_of_day,
                TrafficData.day_of_week,
            ).where(TrafficData.edge_code.in_(edge_codes))
        ).all()
    )

    batch: list[TrafficData] = []
    inserted = 0
    for edge_data in HANOI_EDGES:
        edge_code = str(edge_data["edge_code"])
        for day_of_week in range(7):
            for hour in range(24):
                profile_key = (edge_code, hour, day_of_week)
                if profile_key in existing_profiles:
                    continue
                batch.append(_build_traffic_profile(edge_data, hour, day_of_week))
                existing_profiles.add(profile_key)

                if len(batch) >= 1000:
                    session.add_all(batch)
                    session.commit()
                    inserted += len(batch)
                    batch.clear()

    if batch:
        session.add_all(batch)
        session.commit()
        inserted += len(batch)

    return inserted


def seed_network(db_session: Session | None = None) -> None:
    if db_session is not None:
        import app.models  # noqa: F401

        SQLModel.metadata.create_all(db_session.get_bind())
        session = db_session
    else:
        init_db()
        session = Session(engine)
    try:
        # 1. Seed Nodes (tạo mới hoặc đồng bộ tọa độ/tên theo dữ liệu seed)
        code_to_node = {}
        nodes_updated = 0
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
                if _sync_node(existing, n_data):
                    session.add(existing)
                    nodes_updated += 1
                code_to_node[existing.node_code] = existing
        session.commit()

        # 2. Seed Edges
        straight_geoms_cleared = 0
        for e_data in HANOI_EDGES:
            existing_edge = session.exec(
                select(Edge).where(Edge.edge_code == e_data["edge_code"])
            ).first()
            if existing_edge and _is_straight_line_geom(existing_edge.geom):
                # Geometry 2 điểm chỉ là đường thẳng nối 2 nút: xóa để frontend
                # căn lại theo đường thực tế (OSRM) từ tọa độ nút.
                existing_edge.geom = None
                session.add(existing_edge)
                straight_geoms_cleared += 1
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
        traffic_profiles_added = _seed_traffic_profiles(session)
        print(
            f"Successfully seeded {len(HANOI_NODES)} nodes, "
            f"{len(HANOI_EDGES)} edges, and "
            f"{traffic_profiles_added} traffic profiles. "
            f"Updated {nodes_updated} node(s), "
            f"cleared {straight_geoms_cleared} straight-line edge geometry(ies)."
        )
    finally:
        if db_session is None:
            session.close()


if __name__ == "__main__":
    engine.echo = False
    seed_network()
