import pandas as pd
from sklearn.datasets import load_wine as load_wine_sk


def load_wine():
    """Load wine dataset. Multiclass problem"""
    X, y = load_wine_sk(return_X_y=True)
    return pd.DataFrame(X), pd.Series(y)