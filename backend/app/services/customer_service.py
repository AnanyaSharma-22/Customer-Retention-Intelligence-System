from app.db.customer import Customer
from app.db.prediction import Prediction
from app.db.dataset import Dataset


def get_customers(
    db,
    dataset_id,
    customer_id=None,
    risk=None,
    page=1,
    page_size=20,
):

    query = (
        db.query(Customer)
        .filter(Customer.dataset_id == dataset_id)
    )

    if customer_id:
        query = query.filter(
            Customer.customer_id.ilike(f"%{customer_id}%")
        )

    query = query.order_by(
        Customer.churn_probability.desc()
    )

    customers = query.all()

    result = []

    for customer in customers:

        if customer.churn_probability >= 0.70:
            customer_risk = "High"
        elif customer.churn_probability >= 0.40:
            customer_risk = "Medium"
        else:
            customer_risk = "Low"

        if risk and customer_risk != risk:
            continue

        result.append(
            {
                "customer_id": customer.customer_id,
                "probability": round(
                    customer.churn_probability,
                    4,
                ),
                "risk": customer_risk,
                "segment": customer.segment,
            }
        )

    start = (page - 1) * page_size
    end = start + page_size

    return result[start:end]


def get_customer_details(
    db,
    dataset_id,
    customer_id,
):

    result = (
        db.query(Customer, Prediction)
        .join(Prediction)
        .filter(
            Customer.dataset_id == dataset_id,
            Customer.customer_id == customer_id,
        )
        .first()
    )

    if not result:
        return None

    customer, prediction = result

    if customer.churn_probability >= 0.70:
        risk = "High"
    elif customer.churn_probability >= 0.40:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        "customer_id": customer.customer_id,
        "probability": round(prediction.probability, 4),
        "prediction": prediction.prediction,
        "confidence": round(prediction.confidence, 4),
        "recommendation": prediction.recommendation,
        "model_version": prediction.model_version,
        "risk": risk,
        "recency": customer.recency,
        "frequency": customer.frequency,
        "monetary": customer.monetary,
        "segment": customer.segment,
        "created_at": prediction.created_at,
    }