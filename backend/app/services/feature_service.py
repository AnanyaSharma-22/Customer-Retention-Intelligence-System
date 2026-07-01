from app.db.customer_feature import CustomerFeature


def save_customer_features(
    db,
    customers,
    prediction_df,
    feature_names,
):
    feature_rows = []

    for customer, (_, row) in zip(
        customers,
        prediction_df.iterrows(),
    ):

        for feature in feature_names:

            feature_rows.append(
                CustomerFeature(
                    customer_id=customer.id,
                    feature_name=feature,
                    feature_value=float(row[feature]),
                )
            )

    db.add_all(feature_rows)
    db.commit()

    return feature_rows