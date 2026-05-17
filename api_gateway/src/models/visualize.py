from pydantic import BaseModel


class VisualizeRequest(BaseModel):
    question: str


class VisualizeResponse(BaseModel):
    answer: str
    chart_data: str | None = None
