import os
import numpy as np
import pandas as pd

os.makedirs("data", exist_ok=True)

print(" CUSTOMER DATA PREPROCESSING")

# 1. LOAD DATA

def load_data(file_path):
    """
    Load Online Retail dataset.
    """

    try:
        df = pd.read_excel(file_path)

        print(
            f"\n[OK] Dataset loaded — "
            f"{df.shape[0]:,} rows, {df.shape[1]} columns"
        )

        return df

    except FileNotFoundError:
        print(f"\n[ERROR] '{file_path}' not found.")
        exit()




# 2. BASIC CLEANING




# Drop rows without a customer
def clean_data(df):
    """
    Perform basic preprocessing.
    """

    print("\n[Step 1] Basic cleaning...")

    df = df.dropna(subset=["CustomerID"]).copy()

    df["CustomerID"] = df["CustomerID"].astype(int)

    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    df["Is_Cancelled"] = (
        df["InvoiceNo"]
        .astype(str)
        .str.startswith("C")
        .astype(int)
    )

    df_valid = df[
        (df["Quantity"] > 0)
        &
        (df["UnitPrice"] > 0)
    ].copy()

    df_valid["TotalAmount"] = (
        df_valid["Quantity"]
        *
        df_valid["UnitPrice"]
    )

    print(
        f"       Cleaned shape : "
        f"{df_valid.shape[0]:,} rows"
    )

    return df, df_valid

# 3. TEMPORAL SPLIT


def temporal_split(df_valid):
    """
    Create history and future windows.
    """

    print(
        "\n[Step 2] Creating temporal split "
        "(90-day label window)"
    )

    max_date = df_valid["InvoiceDate"].max()

    cutoff_date = (
        max_date
        -
        pd.Timedelta(days=90)
    )

    hist_df = df_valid[
        df_valid["InvoiceDate"] <= cutoff_date
    ].copy()

    future_df = df_valid[
        df_valid["InvoiceDate"] > cutoff_date
    ].copy()

    print(f"History : up to {cutoff_date.date()}")

    print(
        f"Future  : "
        f"{cutoff_date.date()} → {max_date.date()}"
    )

    print(
        f"History rows : {len(hist_df):,}"
    )

    print(
        f"Future rows  : {len(future_df):,}"
    )

    return (
        hist_df,
        future_df,
        cutoff_date,
        max_date,
    )

# 4. PURCHASE CADENCE FEATURES  (on historical window)


def build_cadence_features(hist_df):
    """
    Calculate purchase cadence features.
    """

    print(
        "\n[Step 3] Engineering cadence features..."
    )

    hist_sorted = (
        hist_df
        .sort_values(
            ["CustomerID", "InvoiceDate"]
        )
    )

    hist_sorted["Prev_InvoiceDate"] = (
        hist_sorted
        .groupby("CustomerID")["InvoiceDate"]
        .shift(1)
    )

    hist_sorted["Days_Between"] = (
        hist_sorted["InvoiceDate"]
        -
        hist_sorted["Prev_InvoiceDate"]
    ).dt.days

    cadence = (
        hist_sorted
        .groupby("CustomerID")["Days_Between"]
        .agg(
            Avg_Days_Between="mean",
            Max_Days_Between="max",
            Std_Days_Between="std",
        )
        .reset_index()
    )

    return cadence




# 5. CORE RFM FEATURES


def build_rfm_features(hist_df, cadence):
    """
    Build core RFM features.
    """

    print("\n Computing RFM features...")

    snapshot_date = hist_df["InvoiceDate"].max()

    recency = (
        hist_df.groupby("CustomerID")["InvoiceDate"]
        .max()
        .reset_index()
    )

    recency["Recency"] = (
        snapshot_date - recency["InvoiceDate"]
    ).dt.days

    frequency = (
        hist_df.groupby("CustomerID")["InvoiceNo"]
        .nunique()
        .reset_index(name="Lifetime_Frequency")
    )

    monetary = (
        hist_df.groupby("CustomerID")["TotalAmount"]
        .sum()
        .reset_index(name="Lifetime_Monetary")
    )

    quantity = (
        hist_df.groupby("CustomerID")["Quantity"]
        .sum()
        .reset_index(name="Total_Items_Bought")
    )

    first_purchase = (
        hist_df.groupby("CustomerID")["InvoiceDate"]
        .min()
        .reset_index(name="FirstPurchase")
    )

    rfm = (
        recency
        .merge(frequency, on="CustomerID")
        .merge(monetary, on="CustomerID")
        .merge(quantity, on="CustomerID")
        .merge(first_purchase, on="CustomerID")
        .merge(cadence, on="CustomerID", how="left")
    )

    return rfm, snapshot_date


# 7. DERIVED / ADVANCED FEATURES


# Latency multiplier: how many "expected cycles" have passed
# without a purchase? >1 means overdue, >2 means very overdue.
def build_derived_features(rfm, snapshot_date):

    print("\nEngineering derived features...")

    rfm["TenureDays"] = (
        snapshot_date - rfm["FirstPurchase"]
    ).dt.days

    rfm["AvgOrderValue"] = (
        rfm["Lifetime_Monetary"]
        / rfm["Lifetime_Frequency"]
    )

    rfm["ItemsPerOrder"] = (
        rfm["Total_Items_Bought"]
        / rfm["Lifetime_Frequency"]
    )

    rfm["PurchaseVelocity"] = (
        rfm["Lifetime_Frequency"]
        / (rfm["TenureDays"] + 1)
    )

    rfm["Latency_Multiplier"] = (
        rfm["Recency"]
        / (rfm["Avg_Days_Between"] + 1)
    )

    rfm["RevenueVelocity"] = (
        rfm["Lifetime_Monetary"]
        / (rfm["TenureDays"] + 1)
    )


    # -------- Additional engineered features --------

    rfm["Recency_x_Latency"] = (
        rfm["Recency"]
        * rfm["Latency_Multiplier"]
    )

    rfm["Monetary_per_Recency"] = (
        rfm["Lifetime_Monetary"]
        / (rfm["Recency"] + 1)
    )

    rfm["Recency_Tenure_Ratio"] = (
        rfm["Recency"]
        / (rfm["TenureDays"] + 1)
    )

    rfm["AOV_x_Velocity"] = (
        rfm["AvgOrderValue"]
        * rfm["PurchaseVelocity"]
    )

    
    rfm["Freq_per_Tenure"] = (
        rfm["Lifetime_Frequency"]
        / (rfm["TenureDays"] + 1)
    )

    return rfm

# 8. CANCELLATION FEATURES
#    Computed from the FULL df (before valid-row filter)
#    so we don't undercount cancellations.




# Use the full df (pre-filter) for cancel counts
def build_cancellation_features(df, rfm, cutoff_date):

    print("\n Adding cancellation features...")

    hist_raw = df[
        (df["InvoiceDate"] <= cutoff_date)
        &
        (df["CustomerID"].notna())
    ].copy()

    hist_raw["CustomerID"] = hist_raw["CustomerID"].astype(int)

    cancel_counts = (
        hist_raw[
            hist_raw["Is_Cancelled"] == 1
        ]
        .groupby("CustomerID")["InvoiceNo"]
        .nunique()
        .reset_index(name="Cancel_Count")
    )

    rfm = rfm.merge(
        cancel_counts,
        on="CustomerID",
        how="left",
    )

    rfm["Cancel_Count"] = (
        rfm["Cancel_Count"].fillna(0)
    )

    rfm["CancelRate"] = (
        rfm["Cancel_Count"]
        /
        (rfm["Lifetime_Frequency"] + 1)
    )

    rfm["Weighted_CancelRate"] = (
    rfm["CancelRate"]
    * rfm["Lifetime_Frequency"]
)

    return rfm


# 9. COUNTRY / DIVERSITY FEATURES  (optional but useful)
def build_country_features(hist_df, rfm):

    country_counts = (
        hist_df.groupby("CustomerID")["Country"]
        .nunique()
        .reset_index(name="Num_Countries")
    )

    rfm = rfm.merge(
        country_counts,
        on="CustomerID",
        how="left",
    )

    rfm.fillna(0, inplace=True)

    print(
        f"\n       Customers in dataset : {len(rfm):,}"
    )

    return rfm


# ─────────────────────────────────────────────────────────
# 10. KEEP ALL CUSTOMERS (including single-purchase ones)
#     Single-purchase customers are a high-churn segment —
#     dropping them makes the model less representative.
#     Their cadence features will be NaN → filled to 0.
# ────────────────────────────────────────────────────────



# 11. PERSONALISED CHURN LABEL
#
#     Flat 90-day rule mislabels seasonal/low-frequency
#     buyers. Instead, a customer is "churned" if:
#       (a) they did NOT purchase in the future window, AND
#       (b) they are overdue relative to their own cadence
#           (Recency > 1.5× their average inter-purchase gap)
#
#     Customers who naturally buy infrequently but are NOT
#     yet overdue are labelled 0 (not churned).
# ─────────────────────────────────────────────────────────

def generate_labels(rfm, future_df):

    print("\nCreating personalised churn label...")

    active_future = (
        future_df["CustomerID"]
        .dropna()
        .astype(int)
        .unique()
    )

    active_future_set = set(active_future)

    def assign_churn(row):

        bought_in_future = (
            row["CustomerID"]
            in active_future_set
        )

        if bought_in_future:
            return 0

        avg_gap = row["Avg_Days_Between"]

        if avg_gap > 0:
            overdue = (
                row["Recency"]
                >
                1.5 * avg_gap
            )
        else:
            overdue = (
                row["Recency"] >= 90
            )

        return 1 if overdue else 0

    rfm["Churn"] = rfm.apply(
        assign_churn,
        axis=1,
    )

    churn_rate = rfm["Churn"].mean() * 100

    print(
        f"       Churn rate : {churn_rate:.1f}%"
    )

    print(
        f"       Churned : {rfm['Churn'].sum():,}"
    )

    print(
        f"       Retained : {(rfm['Churn']==0).sum():,}"
    )

    return rfm





# 13. DROP NON-FEATURE COLUMNS & SAVE

def save_processed_data(rfm):

    rfm = rfm.drop(
        columns=[
            "InvoiceDate",
            "FirstPurchase",
        ],
        errors="ignore",
    )

    rfm.to_csv(
        "data/processed/final_churn_data.csv",
        index=False,
    )

    print("PREPROCESSING COMPLETE")

    print(
        "\nSaved : data/processed/final_churn_data.csv"
    )

    print(
        f"Shape : {rfm.shape[0]:,} × {rfm.shape[1]}"
    )

    print(
        f"\nFeatures : "
        f"{[c for c in rfm.columns if c not in ['CustomerID','Churn']]}"
    )

    return rfm

if __name__ == "__main__":

    print(" CUSTOMER DATA PREPROCESSING")

    df = load_data("data/raw/Online Retail.xlsx")

    df, df_valid = clean_data(df)

    hist_df, future_df, cutoff_date, max_date = temporal_split(df_valid)

    cadence = build_cadence_features(hist_df)

    rfm, snapshot_date = build_rfm_features(
        hist_df,
        cadence,
    )

    rfm = build_derived_features(
        rfm,
        snapshot_date,
    )

    rfm = build_cancellation_features(
        df,
        rfm,
        cutoff_date,
    )

    rfm = build_country_features(
        hist_df,
        rfm,
    )

    rfm = generate_labels(
        rfm,
        future_df,
    )

    rfm = save_processed_data(rfm)

