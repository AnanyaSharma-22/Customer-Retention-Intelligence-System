import os
import joblib
import warnings
import numpy as np
import pandas as pd

from sklearn.pipeline        import Pipeline
from sklearn.impute          import SimpleImputer
from sklearn.preprocessing   import RobustScaler
from sklearn.base            import BaseEstimator, TransformerMixin
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
    RandomizedSearchCV,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    f1_score,
    average_precision_score,
    precision_score,
    recall_score,
)

from imblearn.over_sampling import SMOTE
from imblearn.pipeline      import Pipeline as ImbPipeline
from xgboost                import XGBClassifier

warnings.filterwarnings("ignore")
os.makedirs("models", exist_ok=True)

print(" TRAINING ")

# 1. LOAD DATA


try:
    df = pd.read_csv("data/final_churn_data.csv")
    print(f"\n[OK] Loaded {df.shape[0]:,} rows × {df.shape[1]} columns")
except FileNotFoundError:
    print("[ERROR] Run preprocess.py first.")
    exit()

# 2. SMART FEATURE ENGINEERING
#
#    The biggest accuracy gains come from giving the model
#    better features — not from complicated sampling.
#    These 6 interaction features encode the most important
#    churn signals directly so XGBoost doesn't have to
#    discover them through many tree splits.


print("\n[Step 1] Engineering interaction features...")

# How many "expected cycles" overdue is this customer?
# >1 = overdue, >2 = very overdue — strongest churn signal
df["Recency_x_Latency"] = df["Recency"] * df["Latency_Multiplier"]

# Revenue per day since last purchase — drops as customer drifts
df["Monetary_per_Recency"] = df["Lifetime_Monetary"] / (df["Recency"] + 1)

# What fraction of their entire lifetime has passed without buying?
df["Recency_Tenure_Ratio"] = df["Recency"] / (df["TenureDays"] + 1)

# Order value × purchase speed — high = very engaged customer
df["AOV_x_Velocity"] = df["AvgOrderValue"] * df["PurchaseVelocity"]

# Cancel rate weighted by how often they ordered
df["Weighted_CancelRate"] = df["CancelRate"] * df["Lifetime_Frequency"]

# Frequency normalised by tenure (purchase density)
df["Freq_per_Tenure"] = df["Lifetime_Frequency"] / (df["TenureDays"] + 1)

print(f" Features after engineering : {df.shape[1] - 2}")

# 3. FEATURES & TARGET


DROP_COLS = ["CustomerID", "Churn"]
X = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
X = X.select_dtypes(include=["int64", "float64"])
y = df["Churn"]

feature_names = X.columns.tolist()

churn_count    = y.sum()
retained_count = (y == 0).sum()
pos_weight     = retained_count / churn_count   # for scale_pos_weight

print(f"\n   Total features : {len(feature_names)}")
print(f"   Churned        : {churn_count:,}  ({y.mean()*100:.1f}%)")
print(f"   Retained       : {retained_count:,}  ({(1-y.mean())*100:.1f}%)")
print(f"   pos_weight     : {pos_weight:.2f}")


# 4. LOG TRANSFORMER  (inside pipeline — no train/serve skew)

LOG_COLUMNS = [
    "Lifetime_Monetary",
    "AvgOrderValue",
    "Total_Items_Bought",
    "RevenueVelocity",
    "Monetary_per_Recency",
    "AOV_x_Velocity",
]

class LogTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        if hasattr(X, "columns"):
            self.col_indices_ = [
                i for i, c in enumerate(X.columns) if c in self.columns
            ]
        else:
            self.col_indices_ = list(range(X.shape[1]))
        return self

    def transform(self, X):
        X = X.copy()
        if hasattr(X, "iloc"):
            for col in self.columns:
                if col in X.columns:
                    X[col] = np.log1p(X[col].clip(lower=0))
        else:
            for idx in self.col_indices_:
                X[:, idx] = np.log1p(np.clip(X[:, idx], 0, None))
        return X

# 5. THREE-WAY SPLIT  (60 / 20 / 20)


print("\n[Step 2] Splitting 60 / 20 / 20...")

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.40, random_state=42, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
)

print(f"   Train {len(X_train):,} | Val {len(X_val):,} | Test {len(X_test):,}")

# ─────────────────────────────────────────────────────────
# 6. BUILD PIPELINE
#
#    Steps:
#      log transform  → handle skewed monetary columns
#      imputer        → fill any NaN with median
#      RobustScaler   → scale using IQR, not mean/std
#                       so bulk-order outliers don't
#                       distort the scale for everyone
#      SMOTE          → oversample minority class
#                       (kept simple — just plain SMOTE)
#      XGBoost        → main model
# ─────────────────────────────────────────────────────────

print("\nBuilding pipeline...")

pipeline = ImbPipeline([
    ("log",     LogTransformer(LOG_COLUMNS)),
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler",  RobustScaler()),
    ("smote",   SMOTE(
                    sampling_strategy = 0.8,
                    random_state      = 42,
                    k_neighbors       = 5,
                )),
    ("model",   XGBClassifier(
        n_estimators      = 500,
        learning_rate     = 0.05,
        max_depth         = 6,
        min_child_weight  = 5,
        subsample         = 0.80,
        colsample_bytree  = 0.75,
        gamma             = 0.15,
        reg_alpha         = 0.5,
        reg_lambda        = 1.5,

        # This is the most important single change:
        # tells XGBoost that each churned customer is
        # worth pos_weight times a retained customer.
        # Directly improves recall on the minority class.
        scale_pos_weight  = pos_weight,

        # Optimise PR-AUC internally — better than logloss
        # for imbalanced data because it focuses the tree
        # splits on the minority class boundary.
        objective         = "binary:logistic",
        eval_metric       = "aucpr",

        random_state      = 42,
        n_jobs            = -1,
    )),
])

# ─────────────────────────────────────────────────────────
# 7. HYPERPARAMETER TUNING  with RandomizedSearchCV
#
#    Searches 30 random combinations from the param grid.
#    Tuning is done on training fold only (CV=5).
#    Much more effective than manually tweaking parameters.
#    Runtime: ~3-5 minutes on this dataset size.
# ─────────────────────────────────────────────────────────

print("\n Hyperparameter search (30 trials, 5-fold)...")


param_grid = {
    "model__n_estimators"     : [300, 400, 500, 600, 700],
    "model__learning_rate"    : [0.01, 0.03, 0.05, 0.08, 0.10],
    "model__max_depth"        : [4, 5, 6, 7, 8],
    "model__min_child_weight" : [3, 5, 7, 10],
    "model__subsample"        : [0.70, 0.75, 0.80, 0.85],
    "model__colsample_bytree" : [0.65, 0.70, 0.75, 0.80],
    "model__gamma"            : [0.0, 0.1, 0.15, 0.2, 0.3],
    "model__reg_alpha"        : [0.0, 0.5, 1.0, 2.0],
    "model__reg_lambda"       : [1.0, 1.5, 2.0, 3.0],
}

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

search = RandomizedSearchCV(
    estimator   = pipeline,
    param_distributions = param_grid,
    n_iter      = 30,               # 30 random combos
    scoring     = "roc_auc",        # optimise ROC-AUC
    cv          = cv,
    n_jobs      = -1,
    random_state= 42,
    verbose     = 1,
    refit       = True,             # refit best model on full train set
)

search.fit(X_train, y_train)

print(f"\n   Best CV ROC-AUC : {search.best_score_:.4f}")
print(f"\n   Best params found:")
for param, val in search.best_params_.items():
    clean = param.replace("model__", "")
    print(f"     {clean:<25} : {val}")

best_pipeline = search.best_estimator_

# 8. CROSS-VALIDATE BEST MODEL  


print("\nCross-validating best model...")

cv_roc = cross_val_score(best_pipeline, X_train, y_train,
                         cv=cv, scoring="roc_auc", n_jobs=-1)
cv_prc = cross_val_score(best_pipeline, X_train, y_train,
                         cv=cv, scoring="average_precision", n_jobs=-1)
cv_f1  = cross_val_score(best_pipeline, X_train, y_train,
                         cv=cv, scoring="f1", n_jobs=-1)

print(f"\n   CV ROC-AUC : {cv_roc.mean():.4f}  ±  {cv_roc.std():.4f}")
print(f"   CV PR-AUC  : {cv_prc.mean():.4f}  ±  {cv_prc.std():.4f}")
print(f"   CV F1      : {cv_f1.mean():.4f}  ±  {cv_f1.std():.4f}")

# ─────────────────────────────────────────────────────────
# 9. THRESHOLD TUNING ON VALIDATION SET
#
#    Sweep thresholds from 0.20 to 0.80.
#    Optimise F1 — balanced between precision and recall.
#
#    If your business cares more about catching every
#    churner (even at cost of false alarms), change
#    scoring to "recall" and pick the recall-maximising t.
# ─────────────────────────────────────────────────────────

print("\n Tuning threshold on validation set...\n")

val_probs   = best_pipeline.predict_proba(X_val)[:, 1]
thresholds  = np.arange(0.20, 0.80, 0.01)

best_t      = 0.50
best_f1_val = 0.0

for t in thresholds:
    preds = (val_probs > t).astype(int)
    score = f1_score(y_val, preds, zero_division=0)
    if score > best_f1_val:
        best_f1_val = score
        best_t      = t

best_t = round(best_t, 2)

print(f"   {'Threshold':>10}  {'F1':>8}  {'Recall':>8}  {'Precision':>10}  {'Accuracy':>10}")
print("   " + "-" * 56)

for t in np.arange(0.30, 0.71, 0.05):
    t     = round(t, 2)
    preds = (val_probs > t).astype(int)
    marker = "  ← best" if abs(t - best_t) < 0.005 else ""
    print(f"   {t:>10.2f}  "
          f"{f1_score(y_val, preds, zero_division=0):>8.4f}  "
          f"{recall_score(y_val, preds, zero_division=0):>8.4f}  "
          f"{precision_score(y_val, preds, zero_division=0):>10.4f}  "
          f"{accuracy_score(y_val, preds):>10.4f}{marker}")

print(f"\n   Best threshold : {best_t}")

# 10. FINAL EVALUATION  


print("\n Final evaluation on held-out test set...\n")

test_probs = best_pipeline.predict_proba(X_test)[:, 1]
test_preds = (test_probs > best_t).astype(int)

acc     = accuracy_score(y_test, test_preds)
f1      = f1_score(y_test, test_preds)
roc_auc = roc_auc_score(y_test, test_probs)
avg_pr  = average_precision_score(y_test, test_probs)


print(f" Accuracy          :  {acc:.4f}           ")
print(f" F1 Score          :  {f1:.4f}               ")
print(f" ROC-AUC           :  {roc_auc:.4f}     ")         
print(f" PR-AUC            :  {avg_pr:.4f}       ")        

print("\n   Classification Report:")
print(classification_report(y_test, test_preds,
                             target_names=["Retained", "Churned"]))

cm = confusion_matrix(y_test, test_preds)
tn, fp, fn, tp = cm.ravel()
print("   Confusion Matrix:")
print(f"\n                    Predicted Retained   Predicted Churned")
print(f"   Actual Retained        {tn:>6}                {fp:>6}")
print(f"   Actual Churned         {fn:>6}                {tp:>6}")
print(f"\n   Churners correctly caught : {tp}  /  {tp+fn}  ({tp/(tp+fn)*100:.1f}%)")
print(f"   Loyal wrongly flagged     : {fp}  /  {tn+fp}  ({fp/(tn+fp)*100:.1f}%)")


# 11. FEATURE IMPORTANCE


print("\n Feature importance...\n")

xgb_model     = best_pipeline.named_steps["model"]
importance_df = pd.DataFrame({
    "Feature"   : feature_names,
    "Importance": xgb_model.feature_importances_,
}).sort_values("Importance", ascending=False).reset_index(drop=True)

print(f"   {'Rank':>4}  {'Feature':<35}  {'Importance':>10}")
print("   " + "-" * 55)
for i, row in importance_df.head(15).iterrows():
    print(f"   {i+1:>4}  {row['Feature']:<35}  {row['Importance']:>10.4f}")

importance_df.to_csv("models/feature_importance.csv", index=False)


# 12. SAVE

print("\nSaving artifacts...")

joblib.dump(best_pipeline, "models/churn_pipeline.pkl")
joblib.dump(best_t,        "models/best_threshold.pkl")
joblib.dump(feature_names, "models/feature_names.pkl")

print("TRAINING COMPLETE")

