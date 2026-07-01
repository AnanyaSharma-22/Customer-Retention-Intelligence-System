from sqlalchemy import func

from app.db.customer import Customer
from app.db.prediction import Prediction


def get_dashboard_summary(
    db,
    dataset_id,
):
    # Total customers
    total_customers = (
        db.query(Customer)
        .filter(Customer.dataset_id == dataset_id)
        .count()
    )

    # High Risk (>= 70%)
    high_risk = (
        db.query(Prediction)
        .join(Customer)
        .filter(
            Customer.dataset_id == dataset_id,
            Prediction.probability >= 0.70,
        )
        .count()
    )

    # Medium Risk (40% - 70%)
    medium_risk = (
        db.query(Prediction)
        .join(Customer)
        .filter(
            Customer.dataset_id == dataset_id,
            Prediction.probability >= 0.40,
            Prediction.probability < 0.70,
        )
        .count()
    )

    # Low Risk (< 40%)
    low_risk = (
        db.query(Prediction)
        .join(Customer)
        .filter(
            Customer.dataset_id == dataset_id,
            Prediction.probability < 0.40,
        )
        .count()
    )

    # Average churn probability
    average_probability = (
        db.query(func.avg(Prediction.probability))
        .join(Customer)
        .filter(Customer.dataset_id == dataset_id)
        .scalar()
    ) or 0

    # Revenue at Risk
    revenue_at_risk = (
        db.query(func.sum(Customer.monetary))
        .join(Prediction)
        .filter(
            Customer.dataset_id == dataset_id,
            Prediction.prediction == 1,
        )
        .scalar()
    ) or 0

    # Churn rate
    predicted_churn = (
        db.query(Prediction)
        .join(Customer)
        .filter(
            Customer.dataset_id == dataset_id,
            Prediction.prediction == 1,
        )
        .count()
    )

    churn_rate = (
        (predicted_churn / total_customers) * 100
        if total_customers > 0
        else 0
    )

    return {
        "total_customers": total_customers,
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,
        "churn_rate": round(churn_rate, 2),
        "average_probability": round(float(average_probability), 4),
        "revenue_at_risk": round(float(revenue_at_risk), 2),
    }