from pydantic import BaseModel


class ForecastResponse(BaseModel):
    horizon_days: int
    answer: str
