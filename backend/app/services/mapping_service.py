from typing import Dict

# Internal fields required by RetainIQ
REQUIRED_FIELDS = [
    "customer_id",
    "transaction_id",
    "transaction_date",
]

OPTIONAL_FIELDS = [
    "transaction_value",
    "quantity",
    "unit_price",
    "country",
]


def validate_mapping(mapping: Dict[str, str]):
    """
    Validate that the required business fields
    have been mapped by the user.
    """

    missing = []

    for field in REQUIRED_FIELDS:
        if field not in mapping or not mapping[field]:
            missing.append(field)

    # Either transaction_value OR (quantity + unit_price)
    has_transaction_value = (
        "transaction_value" in mapping
        and mapping["transaction_value"]
    )

    has_quantity = (
        "quantity" in mapping
        and mapping["quantity"]
    )

    has_unit_price = (
        "unit_price" in mapping
        and mapping["unit_price"]
    )

    if not has_transaction_value:
        if not (has_quantity and has_unit_price):
            raise ValueError(
                "Map either 'Transaction Value' OR both "
                "'Quantity' and 'Unit Price'."
            )

    if missing:
        raise ValueError(
            f"Missing required mappings: {missing}"
        )

    return True


def apply_mapping(df, mapping):
    """
    Rename uploaded columns to RetainIQ's
    internal column names.
    """

    rename_dict = {}

    if "customer_id" in mapping:
        rename_dict[mapping["customer_id"]] = "CustomerID"

    if "transaction_id" in mapping:
        rename_dict[mapping["transaction_id"]] = "InvoiceNo"

    if "transaction_date" in mapping:
        rename_dict[mapping["transaction_date"]] = "InvoiceDate"

    if "transaction_value" in mapping:
        rename_dict[mapping["transaction_value"]] = "TransactionValue"

    if "quantity" in mapping:
        rename_dict[mapping["quantity"]] = "Quantity"

    if "unit_price" in mapping:
        rename_dict[mapping["unit_price"]] = "UnitPrice"

    if "country" in mapping:
        rename_dict[mapping["country"]] = "Country"

    df = df.rename(columns=rename_dict)

    return df