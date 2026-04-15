"""
Krushi-Mitra AI - Phase 2.3: Populate Historical Yield Data

This script connects to MySQL and inserts 100-200 realistic sample rows
into the crop_yield_history table for various districts, crops, seasons, and years.
"""
import os
import json
import random
from datetime import datetime
from typing import List, Dict, Tuple

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", os.getenv("DB_PASS", "16042006"))
DB_NAME = os.getenv("DB_NAME", "krushibandhu_ai")
DB_PORT = int(os.getenv("DB_PORT", 3306))

random.seed(42)

CROPS = [
    ("Paddy", {"base_yield": 3000, "varieties": ["Swarna", "MTU-1010", "IR-36"]}),
    ("Wheat", {"base_yield": 2800, "varieties": ["HD-2967", "PBW-343"]}),
    ("Maize", {"base_yield": 3500, "varieties": ["Ganga-5", "HQPM-1"]}),
    ("Turmeric", {"base_yield": 8000, "varieties": ["Lakadong", "Roma"]}),
    ("Groundnut", {"base_yield": 2200, "varieties": ["TAG-24", "JL-24"]}),
]

SEASONS = ["Kharif", "Rabi", "Zaid"]
YEARS = list(range(2015, datetime.now().year))


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=DB_PORT,
    )


def get_districts(conn) -> List[Tuple[int, str]]:
    cur = conn.cursor()
    cur.execute("SELECT id, district_name FROM districts ORDER BY district_name")
    rows = cur.fetchall()
    cur.close()
    return rows


def generate_sample_row(district_id: int, district_name: str) -> Dict:
    crop, meta = random.choice(CROPS)
    base = meta["base_yield"]
    variety = random.choice(meta["varieties"]) if meta.get("varieties") else None
    season = random.choice(SEASONS)
    year = random.choice(YEARS)

    # Environmental factors (rough synthetic realism)
    rainfall_mm = round(random.uniform(600, 1800), 2)
    avg_temp = round(random.uniform(20, 34), 2)

    # Soil health proxy
    soil_health = round(random.uniform(0.3, 0.85), 2)

    # Yield influenced by season, soil health and random noise
    season_factor = {
        "Kharif": 1.0,
        "Rabi": 0.95,
        "Zaid": 0.9,
    }[season]

    # District climate coarse adjustment (coastal vs inland proxy)
    coastal_names = ["Puri", "Balasore", "Kendrapara", "Jagatsinghpur", "Ganjam", "Bhadrak"]
    coastal_factor = 1.03 if any(n.lower() in district_name.lower() for n in coastal_names) else 1.0

    noise = random.uniform(-0.15, 0.15)  # +/-15%
    yield_kg_per_ha = max(800, int(base * season_factor * coastal_factor * (0.8 + soil_health * 0.4) * (1 + noise)))

    # Area and production
    area_hectares = round(random.uniform(0.5, 5.0), 2)
    total_production_kg = int(yield_kg_per_ha * area_hectares)

    # Farming practices JSON
    practices = {
        "irrigation": random.choice(["Canal", "Tube-well", "Rainfed"]),
        "fertilizer": random.choice(["Urea", "DAP", "NPK", "Organic"]),
        "sowing_method": random.choice(["Broadcasting", "Drilling", "Transplanting"]),
    }

    return {
        "district_id": district_id,
        "crop_type": crop,
        "variety": variety,
        "season": season,
        "year": year,
        "yield_kg_per_hectare": yield_kg_per_ha,
        "area_hectares": area_hectares,
        "total_production_kg": total_production_kg,
        "rainfall_mm": rainfall_mm,
        "avg_temperature": avg_temp,
        "soil_health_score": soil_health,
        "farming_practices": json.dumps(practices),
    }


def insert_rows(conn, rows: List[Dict]):
    if not rows:
        return 0
    cur = conn.cursor()
    sql = (
        "INSERT INTO crop_yield_history (district_id, crop_type, variety, season, year, "
        "yield_kg_per_hectare, area_hectares, total_production_kg, rainfall_mm, avg_temperature, "
        "soil_health_score, farming_practices) VALUES (" + ",".join(["%s"] * 12) + ")"
    )
    data = [
        (
            r["district_id"], r["crop_type"], r["variety"], r["season"], r["year"],
            r["yield_kg_per_hectare"], r["area_hectares"], r["total_production_kg"],
            r["rainfall_mm"], r["avg_temperature"], r["soil_health_score"], r["farming_practices"]
        ) for r in rows
    ]
    cur.executemany(sql, data)
    conn.commit()
    inserted = cur.rowcount
    cur.close()
    return inserted


def main():
    try:
        conn = get_connection()
        districts = get_districts(conn)
        if not districts:
            print("❌ No districts found. Populate districts table first.")
            return

        target_rows = random.randint(100, 200)
        samples: List[Dict] = []

        # Distribute roughly evenly across districts
        while len(samples) < target_rows:
            for (did, dname) in districts:
                if len(samples) >= target_rows:
                    break
                samples.append(generate_sample_row(did, dname))

        inserted = insert_rows(conn, samples)
        print(f"✅ Inserted {inserted} sample rows into crop_yield_history")
    except Error as e:
        print(f"❌ Database error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
