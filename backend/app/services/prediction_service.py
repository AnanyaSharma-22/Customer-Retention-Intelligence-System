from pathlib import Path

import pandas as pd

import joblib

import numpy as np


from sklearn.base import BaseEstimator, TransformerMixin
from ml.transformers import LogTransformer

from sqlalchemy.orm import Session

from app.db.customer import Customer
from app.db.prediction import Prediction
from app.db.prediction_history import PredictionHistory


from ml.preprocessing import (
    clean_data,
    temporal_split,
    build_cadence_features,
    build_rfm_features,
    build_derived_features,
    build_cancellation_features,
    build_country_features,
)


def preprocess_uploaded_dataset(file_path: str):
    """
    Convert uploaded transaction data
    into model features.
    """

    file_path = Path(file_path)

    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # Basic cleaning
    df, df_valid = clean_data(df)

    # Temporal split
    (
        hist_df,
        future_df,
        cutoff_date,
        max_date,
    ) = temporal_split(df_valid)

    # Cadence features
    cadence = build_cadence_features(hist_df)

    # Core RFM
    rfm, snapshot_date = build_rfm_features(
        hist_df,
        cadence,
    )

    # Derived features
    rfm = build_derived_features(
        rfm,
        snapshot_date,
    )

    # Cancellation features
    rfm = build_cancellation_features(
        df,
        rfm,
        cutoff_date,
    )

    # Country features
    rfm = build_country_features(
        hist_df,
        rfm,
    )

    # Remove columns not used for prediction
    rfm = rfm.drop(
        columns=[
            "InvoiceDate",
            "FirstPurchase",
        ],
        errors="ignore",
    )

    return rfm



def load_prediction_artifacts():
    """
    Load trained model and supporting files.
    """

    models_path = Path("models")

    pipeline = joblib.load(
        models_path / "churn_pipeline.pkl"
    )

    feature_names = joblib.load(
        models_path / "feature_names.pkl"
    )

    threshold = joblib.load(
        models_path / "best_threshold.pkl"
    )

    return pipeline, feature_names, threshold

def predict_dataset(file_path: str):
    """
    Run preprocessing and prediction on an uploaded dataset.
    Returns:
        prediction_df
        feature_names
    """

    features = preprocess_uploaded_dataset(file_path)

    pipeline, feature_names, threshold = load_prediction_artifacts()

    X = features[feature_names]

    probabilities = pipeline.predict_proba(X)[:, 1]

    predictions = (
        probabilities >= threshold
    ).astype(int)

    result = features.copy()

    result["Churn_Probability"] = probabilities

    result["Prediction"] = predictions

    result["Risk"] = result["Prediction"].map(
        {
            1: "High",
            0: "Low",
        }
    )

    return result, feature_names

def save_customers(
    db: Session,
    dataset_id,
    prediction_df,
):

    customers = []

    for _, row in prediction_df.iterrows():

        customer = Customer(

            dataset_id=dataset_id,

            customer_id=str(
                row["CustomerID"]
            ),

            recency=int(
                row["Recency"]
            ),

            frequency=int(
                row["Lifetime_Frequency"]
            ),

            monetary=float(
                row["Lifetime_Monetary"]
            ),

            churn_probability=float(
                row["Churn_Probability"]
            ),

            churn_prediction=int(
                row["Prediction"]
            ),

            segment="Unknown",
        )

        customers.append(customer)

    db.add_all(customers)
    db.commit()
    for customer in customers:
     db.refresh(customer)

   

    return customers

def save_predictions(
    db: Session,
    customers,
    prediction_df,
):
    predictions = []

    for customer, (_, row) in zip(
        customers,
        prediction_df.iterrows(),
    ):

        probability = float(
            row["Churn_Probability"]
        )

        prediction = int(
            row["Prediction"]
        )

        confidence = max(
            probability,
            1 - probability,
        )

        recommendation = (
            "Launch retention campaign"
            if prediction == 1
            else "Maintain engagement"
        )

        prediction_obj = Prediction(
            customer_id=customer.id,
            probability=probability,
            prediction=prediction,
            confidence=confidence,
            recommendation=recommendation,
            model_version="v1",
        )

        predictions.append(
            prediction_obj
        )

    db.add_all(predictions)

    db.commit()

    for prediction in predictions:
        db.refresh(prediction)

    return predictions