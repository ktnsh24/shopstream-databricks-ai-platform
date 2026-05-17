from pydantic import BaseModel


class MetricsResponse(BaseModel):
    answer: str
