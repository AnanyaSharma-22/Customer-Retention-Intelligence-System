import pandas as pd

# Load original dataset
df = pd.read_excel("data/raw/Online Retail.xlsx")

# Keep only rows with CustomerID
df = df.dropna(subset=["CustomerID"])

# Pick first 250 customers
customers = df["CustomerID"].unique()[:250]

sample = df[df["CustomerID"].isin(customers)]

# Save
sample.to_csv(
    "data/raw/sample_company_transactions.csv",
    index=False,
)

print(sample.shape)
print(sample["CustomerID"].nunique())