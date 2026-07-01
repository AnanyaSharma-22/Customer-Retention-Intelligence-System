from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_customers: int
    high_risk: int
    medium_risk: int
    low_risk: int

    churn_rate: float
    average_probability: float
    revenue_at_risk: float