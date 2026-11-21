import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


class AdminRoadCoordinate(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class AdminRoadPayload(BaseModel):
    edge_code: str = Field(min_length=1, max_length=20)
    street_name: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=50)
    max_speed_limit: int = Field(gt=0, le=200)
    coordinates: list[AdminRoadCoordinate] = Field(min_length=2, max_length=2000)

    @field_validator("edge_code", "street_name", "district")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Trường này không được để trống.")
        return value

    @model_validator(mode="after")
    def endpoints_must_be_distinct(self) -> "AdminRoadPayload":
        first = self.coordinates[0]
        last = self.coordinates[-1]
        if first.lat == last.lat and first.lng == last.lng:
            raise ValueError("Điểm đầu và điểm cuối của đoạn đường phải khác nhau.")
        return self


class AdminRoadResponse(BaseModel):
    edge_id: uuid.UUID
    edge_code: str
    street_name: str
    district: str
    max_speed_limit: int
    length_km: float
    coordinates: list[AdminRoadCoordinate]


class AdminRoadListResponse(BaseModel):
    roads: list[AdminRoadResponse]
    districts: list[str]
