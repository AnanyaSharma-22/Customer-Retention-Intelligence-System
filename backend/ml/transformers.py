import numpy as np

from sklearn.base import (
    BaseEstimator,
    TransformerMixin,
)


class LogTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, columns):
        self.columns = columns

    def fit(self, X, y=None):
        if hasattr(X, "columns"):
            self.col_indices_ = [
                i
                for i, c in enumerate(X.columns)
                if c in self.columns
            ]
        else:
            self.col_indices_ = list(range(X.shape[1]))

        return self

    def transform(self, X):
        X = X.copy()

        if hasattr(X, "iloc"):
            for col in self.columns:
                if col in X.columns:
                    X[col] = np.log1p(
                        X[col].clip(lower=0)
                    )
        else:
            for idx in self.col_indices_:
                X[:, idx] = np.log1p(
                    np.clip(
                        X[:, idx],
                        0,
                        None,
                    )
                )

        return X