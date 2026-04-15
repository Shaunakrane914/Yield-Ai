"""
Krushi-Mitra AI - Phase 2.2: Advanced Model Training

This script connects to MySQL, fetches historical soil and yield data,
engineers features, trains an XGBoost regressor, and saves the model
and preprocessors to the models/ directory.
"""

import os
import json
import pickle
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer


# ----------------------------------------------------------------------------
# Environment and DB config
# ----------------------------------------------------------------------------
load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "16042006"))
DB_NAME = os.getenv("DB_NAME", "krushibandhu_ai")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
os.makedirs(MODELS_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# Data access
# ----------------------------------------------------------------------------

def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
    )


def fetch_training_data() -> pd.DataFrame:
    """Fetch training dataset by joining crop_yield_history with most recent soil_data per district.

    We choose crop_yield_history as the primary source (it contains the target: yield_kg_per_hectare)
    and left-join a representative soil_data row per district (latest sample_date) to enrich features.
    """
    query = """
    SELECT
        cyh.id as cyh_id,
        cyh.district_id,
        d.district_name,
        cyh.crop_type,
        cyh.variety,
        cyh.season,
        cyh.year,
        cyh.yield_kg_per_hectare,
        cyh.area_hectares,
        cyh.total_production_kg,
        cyh.rainfall_mm as hist_rainfall_mm,
        cyh.avg_temperature as hist_avg_temp_c,
        cyh.soil_health_score as hist_soil_health_score,
        sd.ph_level,
        sd.organic_carbon_percent,
        sd.nitrogen_mg_per_kg,
        sd.phosphorus_mg_per_kg,
        sd.potassium_mg_per_kg,
        sd.sample_date
    FROM crop_yield_history cyh
    LEFT JOIN districts d ON d.id = cyh.district_id
    LEFT JOIN (
        SELECT s1.*
        FROM soil_data s1
        INNER JOIN (
            SELECT district_id, MAX(sample_date) AS max_date
            FROM soil_data
            GROUP BY district_id
        ) s2 ON s1.district_id = s2.district_id AND s1.sample_date = s2.max_date
    ) sd ON sd.district_id = cyh.district_id
    ORDER BY cyh.year DESC
    """
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


# ----------------------------------------------------------------------------
# Feature engineering
# ----------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """Create model features and target.

    Returns (X, y, metadata) where metadata holds encoders and feature names.
    """
    if df.empty:
        raise RuntimeError("No training data found in crop_yield_history. Populate data before training.")

    # Target
    y = df["yield_kg_per_hectare"].astype(float)

    # Basic numeric features from history
    X = pd.DataFrame()
    X["hist_rainfall_mm"] = pd.to_numeric(df.get("hist_rainfall_mm"), errors="coerce")
    X["hist_avg_temp_c"] = pd.to_numeric(df.get("hist_avg_temp_c"), errors="coerce")
    X["area_hectares"] = pd.to_numeric(df.get("area_hectares"), errors="coerce")

    # Soil features
    X["ph_level"] = pd.to_numeric(df.get("ph_level"), errors="coerce")
    X["organic_carbon_percent"] = pd.to_numeric(df.get("organic_carbon_percent"), errors="coerce")
    X["nitrogen_mg_per_kg"] = pd.to_numeric(df.get("nitrogen_mg_per_kg"), errors="coerce")
    X["phosphorus_mg_per_kg"] = pd.to_numeric(df.get("phosphorus_mg_per_kg"), errors="coerce")
    X["potassium_mg_per_kg"] = pd.to_numeric(df.get("potassium_mg_per_kg"), errors="coerce")

    # Advanced engineered features
    # Soil health score (simple weighted aggregate as an example)
    # Normalize NPK roughly by min-max heuristic to avoid scale dominance
    def safe_norm(s: pd.Series) -> pd.Series:
        s = s.copy()
        min_v = np.nanpercentile(s.dropna(), 5) if s.dropna().size else 0.0
        max_v = np.nanpercentile(s.dropna(), 95) if s.dropna().size else 1.0
        if max_v - min_v == 0:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - min_v) / (max_v - min_v)

    n_norm = safe_norm(X["nitrogen_mg_per_kg"])
    p_norm = safe_norm(X["phosphorus_mg_per_kg"])
    k_norm = safe_norm(X["potassium_mg_per_kg"])
    oc_norm = safe_norm(X["organic_carbon_percent"])

    X["soil_health_score"] = (0.3 * n_norm + 0.3 * p_norm + 0.3 * k_norm + 0.1 * oc_norm)

    # Ratios (with safe division)
    def safe_div(a, b):
        return np.where((b is None) | (np.array(b, dtype=float) == 0), np.nan, np.array(a, dtype=float) / np.array(b, dtype=float))

    X["npk_sum"] = X[["nitrogen_mg_per_kg", "phosphorus_mg_per_kg", "potassium_mg_per_kg"]].sum(axis=1)
    X["ratio_n_p"] = X["nitrogen_mg_per_kg"] / X["phosphorus_mg_per_kg"].replace({0: np.nan})
    X["ratio_k_p"] = X["potassium_mg_per_kg"] / X["phosphorus_mg_per_kg"].replace({0: np.nan})

    # Optional: temperature range (if min/max available in future schema)
    # For now, use a proxy: variability around historical avg (set to 0 where unknown)
    X["temperature_range"] = 0.0

    # Categorical encodings
    cat_cols = {}
    for col in ["district_name", "crop_type", "season", "variety"]:
        le = LabelEncoder()
        values = df[col].astype(str).fillna("unknown")
        X[f"{col}_le"] = le.fit_transform(values)
        cat_cols[col] = le

    # Impute missing numerics
    num_cols = X.columns.tolist()
    # Handle columns that are entirely NaN to avoid imputer errors and shape mismatches
    all_nan_cols = [c for c in num_cols if X[c].isna().all()]
    if all_nan_cols:
        # Fill those entirely-missing columns with 0 (neutral default) before imputation
        X[all_nan_cols] = 0

    imputer = SimpleImputer(strategy="median")
    X[num_cols] = imputer.fit_transform(X[num_cols])

    metadata = {
        "categorical_encoders": cat_cols,
        "imputer": imputer,
        "feature_columns": num_cols,
    }

    return X, y, metadata


# ----------------------------------------------------------------------------
# Training
# ----------------------------------------------------------------------------

def train_model(X: pd.DataFrame, y: pd.Series) -> Tuple[XGBRegressor, Dict[str, float]]:
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    r2 = r2_score(y_test, preds) if len(y_test.unique()) > 1 else float("nan")
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))

    metrics = {"r2": r2, "rmse": rmse}
    return model, metrics


# ----------------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------------

def save_artifacts(model: XGBRegressor, metadata: Dict[str, Any]) -> None:
    model_path = os.path.join(MODELS_DIR, "xgb_yield_model.pkl")
    preprocess_path = os.path.join(MODELS_DIR, "preprocessors.pkl")
    spec_path = os.path.join(MODELS_DIR, "feature_spec.json")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    # Serialize encoders and imputer
    serializable_meta = {
        "feature_columns": metadata["feature_columns"],
    }
    with open(preprocess_path, "wb") as f:
        pickle.dump({
            "categorical_encoders": metadata["categorical_encoders"],
            "imputer": metadata["imputer"],
        }, f)

    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(serializable_meta, f, indent=2)

    print(f"✅ Saved model to {model_path}")
    print(f"✅ Saved preprocessors to {preprocess_path}")
    print(f"✅ Saved feature spec to {spec_path}")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    print("🚀 Training Advanced XGBoost Model (Phase 2.2)")
    try:
        df = fetch_training_data()
        if df.empty:
            print("❌ No data available in crop_yield_history. Populate training data first.")
            return
        print(f"📦 Loaded training rows: {len(df)}")

        X, y, metadata = engineer_features(df)
        print(f"🔧 Features built: {len(metadata['feature_columns'])}")

        model, metrics = train_model(X, y)
        print(f"📈 Metrics -> R2: {metrics['r2']:.4f} | RMSE: {metrics['rmse']:.4f}")

        save_artifacts(model, metadata)
        print("🎉 Training completed successfully!")
    except Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Training error: {e}")


if __name__ == "__main__":
    main()
