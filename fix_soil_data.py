"""
Krushi-Mitra AI - Fix Soil Data (Backfill Nutrients)

This script connects to MySQL, reads merged_crop_data.csv, and for each CSV row
updates the corresponding soil_data record (by district and crop) to populate
NULL nutrient columns using cleaned numeric values from the CSV.

Columns updated (if currently NULL):
- organic_carbon_percent <- oc_(%)
- nitrogen_mg_per_kg    <- p_(%)  (proxy; CSV lacks explicit N)
- phosphorus_mg_per_kg  <- p_(%)
- potassium_mg_per_kg   <- k_(%)
- calcium_percent       <- ca_(%)
- magnesium_percent     <- mg_(%)
- sulfur_mg_per_kg      <- s_(%)
- zinc_mg_per_kg        <- zn_(%)
- boron_mg_per_kg       <- b_(%)
- iron_mg_per_kg        <- fe_(%)
- copper_mg_per_kg      <- cu_(%)
- manganese_mg_per_kg   <- mn_(%)

We only fill columns that are NULL in the database to avoid overwriting data.
"""
import os
from typing import Optional, Dict, Any

import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "16042006"))
DB_NAME = os.getenv("DB_NAME", "krushibandhu_ai")
DB_PORT = int(os.getenv("DB_PORT", 3306))

CSV_PATH = os.path.join(os.path.dirname(__file__), "merged_crop_data.csv")

# Map: db_column -> csv_column
COLUMN_MAP = {
    "organic_carbon_percent": "oc_(%)",
    "nitrogen_mg_per_kg": "p_(%)",   # proxy
    "phosphorus_mg_per_kg": "p_(%)",
    "potassium_mg_per_kg": "k_(%)",
    "calcium_percent": "ca_(%)",
    "magnesium_percent": "mg_(%)",
    "sulfur_mg_per_kg": "s_(%)",
    "zinc_mg_per_kg": "zn_(%)",
    "boron_mg_per_kg": "b_(%)",
    "iron_mg_per_kg": "fe_(%)",
    "copper_mg_per_kg": "cu_(%)",
    "manganese_mg_per_kg": "mn_(%)",
}


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
    )


def dec2(val: Any) -> Optional[float]:
    """Coerce to float rounded to 2 decimals. Return None if invalid."""
    try:
        if val is None:
            return None
        v = float(val)
        if pd.isna(v):
            return None
        return round(v, 2)
    except Exception:
        return None


def find_district_id(cur, district_name: str) -> Optional[int]:
    cur.execute("SELECT id FROM districts WHERE district_name = %s", (district_name,))
    r = cur.fetchone()
    return r[0] if r else None


def find_target_soil_id(cur, district_id: int, crop_type: str) -> Optional[int]:
    # Pick the most recent soil record for the district and crop
    cur.execute(
        """
        SELECT id FROM soil_data
        WHERE district_id = %s AND crop_type = %s
        ORDER BY sample_date DESC
        LIMIT 1
        """,
        (district_id, crop_type),
    )
    r = cur.fetchone()
    return r[0] if r else None


def build_update_clause(row: pd.Series) -> Dict[str, Optional[float]]:
    updates: Dict[str, Optional[float]] = {}
    for db_col, csv_col in COLUMN_MAP.items():
        if csv_col in row:
            updates[db_col] = dec2(row[csv_col])
        else:
            updates[db_col] = None
    return updates


def update_soil_row(cur, soil_id: int, updates: Dict[str, Optional[float]]) -> int:
    # Only include columns where (value is not None) and (column IS NULL currently)
    set_parts = []
    params = []
    for col, val in updates.items():
        if val is None:
            continue
        # Use CASE to set only when current value IS NULL
        set_parts.append(f"{col} = CASE WHEN {col} IS NULL THEN %s ELSE {col} END")
        params.append(val)

    if not set_parts:
        return 0

    sql = f"UPDATE soil_data SET {', '.join(set_parts)} WHERE id = %s"
    params.append(soil_id)
    cur.execute(sql, tuple(params))
    return cur.rowcount


def main():
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV not found: {CSV_PATH}")
        return

    df = pd.read_csv(CSV_PATH)
    if df.empty:
        print("❌ CSV is empty. Nothing to update.")
        return

    conn = get_connection()
    cur = conn.cursor()
    updated_rows = 0
    scanned = 0

    try:
        for _, row in df.iterrows():
            scanned += 1
            district_name = str(row.get("district", "")).strip()
            crop_type = str(row.get("crop", "Unknown")).strip() or "Unknown"
            if not district_name:
                continue

            district_id = find_district_id(cur, district_name)
            if not district_id:
                continue

            soil_id = find_target_soil_id(cur, district_id, crop_type)
            if not soil_id:
                # if there's no specific crop match, try any soil record for the district
                cur.execute(
                    "SELECT id FROM soil_data WHERE district_id = %s ORDER BY sample_date DESC LIMIT 1",
                    (district_id,),
                )
                r = cur.fetchone()
                soil_id = r[0] if r else None
                if not soil_id:
                    continue

            updates = build_update_clause(row)
            changed = update_soil_row(cur, soil_id, updates)
            if changed:
                updated_rows += 1

        conn.commit()
        print(f"✅ Backfill complete. Scanned: {scanned}, Rows updated: {updated_rows}")
    except Error as e:
        print(f"❌ Database error: {e}")
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
