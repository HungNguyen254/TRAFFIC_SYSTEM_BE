import uuid

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Edge,
    Node,
    Prediction,
    SavedPlace,
    SearchHistory,
    TrafficRecord,
    User,
)


def test_models_metadata_and_crud():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. User
        user = User(
            email="test@example.com",
            password_hash="hashed_pw",
            full_name="Nguyễn Văn A",
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert isinstance(user.user_id, uuid.UUID)

        # 2. Node
        node1 = Node(
            node_code="NODE_NTS",
            node_name="Ngã tư Sở",
            district="Đống Đa",
            latitude=21.002,
            longitude=105.819,
        )
        node2 = Node(
            node_code="NODE_CG",
            node_name="Cầu Giấy",
            district="Cầu Giấy",
            latitude=21.033,
            longitude=105.798,
        )
        session.add_all([node1, node2])
        session.commit()
        session.refresh(node1)
        session.refresh(node2)
        assert isinstance(node1.node_id, uuid.UUID)

        # 3. Edge
        edge = Edge(
            edge_code="EDGE_01",
            street_name="Đường Láng",
            from_node_id=node1.node_id,
            to_node_id=node2.node_id,
            length_km=4.2,
            max_speed_limit=50,
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)
        assert isinstance(edge.edge_id, uuid.UUID)

        # 4. SavedPlace
        saved_place = SavedPlace(
            user_id=user.user_id,
            place_name="Nhà riêng",
            address="123 Nguyễn Trãi",
            latitude=21.001,
            longitude=105.820,
        )
        session.add(saved_place)
        session.commit()
        session.refresh(saved_place)
        assert isinstance(saved_place.saved_place_id, uuid.UUID)

        # 5. SearchHistory
        search = SearchHistory(
            user_id=user.user_id,
            origin_name="Ngã tư Sở",
            origin_lat=21.002,
            origin_lng=105.819,
            destination_name="Cầu Giấy",
            destination_lat=21.033,
            destination_lng=105.798,
        )
        session.add(search)
        session.commit()
        session.refresh(search)
        assert isinstance(search.search_history_id, uuid.UUID)

        # 6. TrafficRecord
        record = TrafficRecord(
            edge_id=edge.edge_id,
            current_speed=18.5,
            congestion_level=3,
            color_code="#f97316",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        assert isinstance(record.traffic_record_id, uuid.UUID)

        # 7. Prediction
        prediction = Prediction(
            edge_id=edge.edge_id,
            hour_of_day=18,
            predicted_speed=15.0,
            risk_factor=0.75,
        )
        session.add(prediction)
        session.commit()
        session.refresh(prediction)
        assert isinstance(prediction.prediction_id, uuid.UUID)

        # Assert query
        stored_user = session.exec(select(User).where(User.email == "test@example.com")).first()
        assert stored_user is not None
        assert stored_user.full_name == "Nguyễn Văn A"
