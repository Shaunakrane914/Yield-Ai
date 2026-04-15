"""
Market Intelligence Data Engine

- Fetches wholesale market prices from the Government of India (Agmarknet) dataset on data.gov.in
- Caches results into MySQL table `market_prices`
- Designed to be run periodically (e.g., daily via Task Scheduler/Cron)

Environment variables:
- DB_HOST, DB_USER, DB_PASS, DB_NAME
- AGMARKNET_API_KEY (required)
- AGMARKNET_RESOURCE_ID (optional; default: Agricultural Commodities Prices resource)

Usage (Windows PowerShell):
  $env:AGMARKNET_API_KEY="<your_api_key_here>"
  python market_data_engine.py

Notes:
- The `market_prices` table is created if it does not exist.
- We collect prices for a curated list of Odisha districts and key crops.
"""
from __future__ import annotations

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import requests
import mysql.connector

# -------------------------------
# Config
# -------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "16042006")
DB_NAME = os.environ.get("DB_NAME", "krushibandhu_ai")

AGMARKNET_API_KEY = os.environ.get("AGMARKNET_API_KEY", "")
# Default resource id widely used for Agmarknet daily market prices (data.gov.in)
AGMARKNET_RESOURCE_ID = os.environ.get(
    "AGMARKNET_RESOURCE_ID",
    "9ef84268-d588-465a-a308-a864a43d0070",
)

# Odisha focus (curated; extend as needed)
ODISHA_DISTRICTS: List[str] = [
    "Cuttack",
    "Khordha",
    "Puri",
    "Balasore",
    "Ganjam",
    "Sambalpur",
    "Mayurbhanj",
    "Bargarh",
]

KEY_CROPS: List[str] = [
    "Paddy",
    "Wheat",
    "Maize",
    "Turmeric",
    "Potato",
    "Onion",
    "Tomato",
]

# -------------------------------
# Logging
# -------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("market_data_engine")

# -------------------------------
# DB helpers
# -------------------------------

def get_db_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )


def ensure_table(conn):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS market_prices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                market_name VARCHAR(255) NOT NULL,
                district VARCHAR(255) NOT NULL,
                crop VARCHAR(255) NOT NULL,
                price_per_quintal DECIMAL(10,2) NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_market_price (market_name, district, crop, date),
                INDEX idx_district_crop_date (district, crop, date)
            )
            """
        )
        conn.commit()
    finally:
        cursor.close()


def upsert_market_price(
    conn,
    market_name: str,
    district: str,
    crop: str,
    price_per_quintal: float,
    date_str: str,
):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO market_prices (market_name, district, crop, price_per_quintal, date)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE price_per_quintal = VALUES(price_per_quintal)
            """,
            (market_name, district, crop, price_per_quintal, date_str),
        )
        conn.commit()
    finally:
        cursor.close()


# -------------------------------
# Agmarknet fetch
# -------------------------------

def fetch_agmarknet_prices(
    api_key: str,
    resource_id: str,
    state: str,
    district: str,
    commodity: str,
    start_date: datetime,
    end_date: datetime,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Fetch prices from data.gov.in Agmarknet resource with filters.

    Fields expected: state, district, market, commodity, modal_price, arrival_date
    """
    if not api_key:
        raise RuntimeError("AGMARKNET_API_KEY is required")

    # data.gov.in supports filters and pagination via offset
    base_url = "https://api.data.gov.in/resource/" + resource_id

    records: List[Dict[str, Any]] = []
    offset = 0

    # Date format dd/mm/yyyy in this dataset
    date_from = start_date.strftime("%d/%m/%Y")
    date_to = end_date.strftime("%d/%m/%Y")

    while True:
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": str(limit),
            "offset": str(offset),
            # Filters
            "filters[state]": state,
            "filters[district]": district,
            "filters[commodity]": commodity,
            "filters[arrival_date]": f"{date_from} to {date_to}",
        }
        resp = requests.get(base_url, params=params, timeout=30)
        # Debug: print raw API response to help diagnose connectivity/format issues
        try:
            print("--- RAW API RESPONSE ---")
            print(resp.json())
        except Exception:
            try:
                print(resp.text)
            except Exception as _e:
                print(f"<non-textual response body: {_e}>")
        resp.raise_for_status()
        data = resp.json()
        recs = data.get("records") or []
        records.extend(recs)
        logger.debug(f"Fetched {len(recs)} records (offset={offset}) for {district}-{commodity}")
        if len(recs) < limit:
            break
        offset += limit
        # be gentle
        time.sleep(0.25)

    return records


# -------------------------------
# Main routine
# -------------------------------

def run_daily_refresh():
    logger.info("Starting Market Data Engine refresh...")
    conn = get_db_conn()
    try:
        ensure_table(conn)

        # Use last 90 days window to capture a broader history (and late updates)
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=90)

        total_inserted = 0
        for district in ODISHA_DISTRICTS:
            for crop in KEY_CROPS:
                try:
                    records = fetch_agmarknet_prices(
                        api_key=AGMARKNET_API_KEY,
                        resource_id=AGMARKNET_RESOURCE_ID,
                        state="Odisha",
                        district=district,
                        commodity=crop,
                        start_date=start_dt,
                        end_date=end_dt,
                    )
                except Exception as e:
                    logger.warning(f"Fetch error for {district}-{crop}: {e}")
                    continue

                for r in records:
                    try:
                        market = (r.get("market") or "").strip() or "Unknown Market"
                        commodity = (r.get("commodity") or "").strip() or crop
                        arrival_date = (r.get("arrival_date") or "").strip()
                        modal_price = r.get("modal_price")

                        # modal_price is usually Rs/Quintal (string). Normalize to float.
                        try:
                            price_val = float(str(modal_price).strip())
                        except Exception:
                            continue

                        # Convert dd/mm/yyyy to yyyy-mm-dd for MySQL
                        try:
                            dt = datetime.strptime(arrival_date, "%d/%m/%Y").date()
                            date_sql = dt.isoformat()
                        except Exception:
                            # If missing/invalid date, skip
                            continue

                        upsert_market_price(
                            conn,
                            market_name=market,
                            district=district,
                            crop=commodity,
                            price_per_quintal=price_val,
                            date_str=date_sql,
                        )
                        total_inserted += 1
                    except Exception as e:
                        logger.debug(f"Skip record due to error: {e}")
                        continue

        logger.info(f"Market Data Engine refresh complete. Upserts: {total_inserted}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        run_daily_refresh()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
