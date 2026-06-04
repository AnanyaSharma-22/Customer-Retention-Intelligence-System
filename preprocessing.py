import os
import numpy as np
import pandas as pd

os.makedirs("data", exist_ok=True)

print(" CUSTOMER DATA PREPROCESSING")

# 1. LOAD DATA


try:
    df = pd.read_excel("data/Online Retail.xlsx")
    print(f"\n[OK] Dataset loaded — {df.shape[0]:,} rows, {df.shape[1]} columns")
except FileNotFoundError:
    print("\n[ERROR] 'data/Online Retail.xlsx' not found.")
    print("        Place the file in the data/ folder and retry.")
    exit()

# 2. BASIC CLEANING


print("\n[Step 1] Basic cleaning...")

# Drop rows without a customer
df = df.dropna(subset=["CustomerID"])
df["CustomerID"] = df["CustomerID"].astype(int)

# Parse dates
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

# Flag cancellations BEFORE any row filtering — we need
# the raw cancel count later for the feature, not a
# filtered version that would undercount cancels.
df["Is_Cancelled"] = (
    df["InvoiceNo"].astype(str).str.startswith("C").astype(int)
)

# Keep only valid transactions for RFM
df_valid = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)].copy()
df_valid["TotalAmount"] = df_valid["Quantity"] * df_valid["UnitPrice"]

print(f"       Cleaned shape : {df_valid.shape[0]:,} rows")

# 3. TEMPORAL SPLIT


print("\n[Step 2] Creating temporal split (90-day label window)")

max_date    = df_valid["InvoiceDate"].max()
cutoff_date = max_date - pd.Timedelta(days=90)

# Historical window  → used to build features
hist_df = df_valid[df_valid["InvoiceDate"] <= cutoff_date].copy()

# Future window      → used to build the churn label
future_df = df_valid[df_valid["InvoiceDate"] > cutoff_date].copy()

print(f"History  : up to {cutoff_date.date()}")
print(f"Future   : {cutoff_date.date()} → {max_date.date()}")
print(f"History rows  : {len(hist_df):,}")
print(f" Future rows   : {len(future_df):,}")

# 4. PURCHASE CADENCE FEATURES  (on historical window)


print("\n[Step 3] Engineering cadence features...")

hist_sorted = hist_df.sort_values(["CustomerID", "InvoiceDate"])

hist_sorted["Prev_InvoiceDate"] = (
    hist_sorted.groupby("CustomerID")["InvoiceDate"].shift(1)
)
hist_sorted["Days_Between"] = (
    hist_sorted["InvoiceDate"] - hist_sorted["Prev_InvoiceDate"]
).dt.days

cadence = (
    hist_sorted.groupby("CustomerID")["Days_Between"]
    .agg(
        Avg_Days_Between="mean",
        Max_Days_Between="max",
        Std_Days_Between="std",
    )
    .reset_index()
)

# 5. CORE RFM FEATURES


print("\n Computing RFM features...")

snapshot_date = hist_df["InvoiceDate"].max()

recency = (
    hist_df.groupby("CustomerID")["InvoiceDate"]
    .max()
    .reset_index()
)
recency["Recency"] = (snapshot_date - recency["InvoiceDate"]).dt.days

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

# 6. MERGE ALL FEATURES


rfm = (
    recency
    .merge(frequency,     on="CustomerID")
    .merge(monetary,      on="CustomerID")
    .merge(quantity,      on="CustomerID")
    .merge(first_purchase, on="CustomerID")
    .merge(cadence,       on="CustomerID", how="left")
)

# 7. DERIVED / ADVANCED FEATURES


print("\nEngineering derived features...")

rfm["TenureDays"] = (snapshot_date - rfm["FirstPurchase"]).dt.days

rfm["AvgOrderValue"] = (
    rfm["Lifetime_Monetary"] / rfm["Lifetime_Frequency"]
)

rfm["ItemsPerOrder"] = (
    rfm["Total_Items_Bought"] / rfm["Lifetime_Frequency"]
)

rfm["PurchaseVelocity"] = (
    rfm["Lifetime_Frequency"] / (rfm["TenureDays"] + 1)
)

# Latency multiplier: how many "expected cycles" have passed
# without a purchase? >1 means overdue, >2 means very overdue.
rfm["Latency_Multiplier"] = (
    rfm["Recency"] / (rfm["Avg_Days_Between"] + 1)
)

rfm["RevenueVelocity"] = (
    rfm["Lifetime_Monetary"] / (rfm["TenureDays"] + 1)
)

# 8. CANCELLATION FEATURES
#    Computed from the FULL df (before valid-row filter)
#    so we don't undercount cancellations.


print("\n Adding cancellation features...")

# Use the full df (pre-filter) for cancel counts
hist_raw = df[
    (df["InvoiceDate"] <= cutoff_date) &
    (df["CustomerID"].notna())
].copy()
hist_raw["CustomerID"] = hist_raw["CustomerID"].astype(int)

cancel_counts = (
    hist_raw[hist_raw["Is_Cancelled"] == 1]
    .groupby("CustomerID")["InvoiceNo"]
    .nunique()
    .reset_index(name="Cancel_Count")
)

rfm = rfm.merge(cancel_counts, on="CustomerID", how="left")
rfm["Cancel_Count"] = rfm["Cancel_Count"].fillna(0)

rfm["CancelRate"] = rfm["Cancel_Count"] / (rfm["Lifetime_Frequency"] + 1)

# 9. COUNTRY / DIVERSITY FEATURES  (optional but useful)


country_counts = (
    hist_df.groupby("CustomerID")["Country"]
    .nunique()
    .reset_index(name="Num_Countries")
)
rfm = rfm.merge(country_counts, on="CustomerID", how="left")

# ─────────────────────────────────────────────────────────
# 10. KEEP ALL CUSTOMERS (including single-purchase ones)
#     Single-purchase customers are a high-churn segment —
#     dropping them makes the model less representative.
#     Their cadence features will be NaN → filled to 0.
# ────────────────────────────────────────────────────────

rfm.fillna(0, inplace=True)

print(f"\n       Customers in dataset : {len(rfm):,}")


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

print("\nCreating personalised churn label...")

active_future = (
    future_df["CustomerID"].dropna().astype(int).unique()
)
active_future_set = set(active_future)

def assign_churn(row):
    bought_in_future = row["CustomerID"] in active_future_set
    if bought_in_future:
        return 0                            # definitely active

    # Did not buy in future window — check cadence
    avg_gap = row["Avg_Days_Between"]

    if avg_gap > 0:
        # Overdue if recency > 1.5× personal average gap
        overdue = row["Recency"] > 1.5 * avg_gap
    else:
        # Single-purchase customer: use the flat 90-day rule
        overdue = row["Recency"] >= 90

    return 1 if overdue else 0

rfm["Churn"] = rfm.apply(assign_churn, axis=1)

churn_rate = rfm["Churn"].mean() * 100
print(f"       Churn rate : {churn_rate:.1f}%")
print(f"       Churned    : {rfm['Churn'].sum():,}")
print(f"       Retained   : {(rfm['Churn'] == 0).sum():,}")


# 13. DROP NON-FEATURE COLUMNS & SAVE


rfm = rfm.drop(columns=["InvoiceDate", "FirstPurchase"], errors="ignore")

rfm.to_csv("data/final_churn_data.csv", index=False)

print("PREPROCESSING COMPLETE")
print(f"\n   Saved  : data/final_churn_data.csv")
print(f"   Shape  : {rfm.shape[0]:,} rows × {rfm.shape[1]} columns")
print(f"\n   Features : {[c for c in rfm.columns if c not in ['CustomerID','Churn']]}")