from datetime import datetime

from pydantic import BaseModel


class CustomerListItem(BaseModel):
    customer_id: str
    probability: float
    risk: str
    segment: str


class CustomerDetails(BaseModel):
    customer_id: str

    probability: float
    prediction: int

    confidence: float

    recommendation: str

    model_version: str

    risk: str

    recency: int
    frequency: int
    monetary: float

    segment: str

    created_at: datetime