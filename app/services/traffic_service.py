import uuid

from fastapi import HTTPException, status
from sqlmodel import Session, col, select

from app.models.edge import Edge
from app.models.node import Node
from app.schemas.traffic import EdgeCreate, EdgeUpdate, NodeCreate, NodeUpdate


class TrafficService:
    @staticmethod
    def create_node(session: Session, payload: NodeCreate) -> Node:
        existing = session.exec(select(Node).where(Node.node_code == payload.node_code)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã nút giao '{payload.node_code}' đã tồn tại.",
            )
        node = Node(**payload.model_dump())
        session.add(node)
        session.commit()
        session.refresh(node)
        return node

    @staticmethod
    def list_nodes(session: Session, district: str | None = None) -> list[Node]:
        stmt = select(Node)
        if district:
            stmt = stmt.where(col(Node.district).ilike(f"%{district}%"))
        return list(session.exec(stmt).all())

    @staticmethod
    def get_node_by_id(session: Session, node_id: uuid.UUID) -> Node:
        node = session.get(Node, node_id)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy nút giao có ID {node_id}.",
            )
        return node

    @staticmethod
    def resolve_node_by_name(session: Session, query: str) -> list[Node]:
        q = f"%{query.strip()}%"
        stmt = select(Node).where(col(Node.node_name).ilike(q) | col(Node.node_code).ilike(q))
        return list(session.exec(stmt).all())

    @staticmethod
    def update_node(session: Session, node_id: uuid.UUID, payload: NodeUpdate) -> Node:
        node = TrafficService.get_node_by_id(session, node_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(node, key, value)
        session.add(node)
        session.commit()
        session.refresh(node)
        return node

    @staticmethod
    def delete_node(session: Session, node_id: uuid.UUID) -> None:
        node = TrafficService.get_node_by_id(session, node_id)
        session.delete(node)
        session.commit()

    @staticmethod
    def create_edge(session: Session, payload: EdgeCreate) -> Edge:
        TrafficService.get_node_by_id(session, payload.from_node_id)
        TrafficService.get_node_by_id(session, payload.to_node_id)

        existing = session.exec(select(Edge).where(Edge.edge_code == payload.edge_code)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã đoạn đường '{payload.edge_code}' đã tồn tại.",
            )
        edge = Edge(**payload.model_dump())
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge

    @staticmethod
    def list_edges(session: Session, street_name: str | None = None) -> list[Edge]:
        stmt = select(Edge)
        if street_name:
            stmt = stmt.where(col(Edge.street_name).ilike(f"%{street_name}%"))
        return list(session.exec(stmt).all())

    @staticmethod
    def get_edge_by_id(session: Session, edge_id: uuid.UUID) -> Edge:
        edge = session.get(Edge, edge_id)
        if not edge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy đoạn đường có ID {edge_id}.",
            )
        return edge

    @staticmethod
    def get_edges_by_street(session: Session, street_name: str) -> list[Edge]:
        stmt = select(Edge).where(col(Edge.street_name).ilike(f"%{street_name.strip()}%"))
        return list(session.exec(stmt).all())

    @staticmethod
    def update_edge(session: Session, edge_id: uuid.UUID, payload: EdgeUpdate) -> Edge:
        edge = TrafficService.get_edge_by_id(session, edge_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(edge, key, value)
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge

    @staticmethod
    def delete_edge(session: Session, edge_id: uuid.UUID) -> None:
        edge = TrafficService.get_edge_by_id(session, edge_id)
        session.delete(edge)
        session.commit()
