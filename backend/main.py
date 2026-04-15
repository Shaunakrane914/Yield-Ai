from typing import Generator
from datetime import timedelta, datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import mysql.connector
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, EmailStr
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
import bcrypt
import pickle
import json
import numpy as np
import pandas as pd
from datetime import date, datetime
from typing import Optional, Dict, Any
import requests
import math
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj
import time
from itsdangerous import URLSafeSerializer
from pprint import pformat

# Plant Doctor AI imports
import tensorflow as tf
from tensorflow import keras
from PIL import Image
import io

# ------------------------------------------------------------
# App setup
# ------------------------------------------------------------
app = FastAPI(title="Krushi-Mitra AI (FastAPI)")

# CORS: allow specific dev origins and credentials (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://10.0.29.67:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Session middleware (7 days)
SESSION_SECRET = os.environ.get("SESSION_SECRET", os.urandom(24))
SEVEN_DAYS_SECONDS = int(timedelta(days=7).total_seconds())
app.add_middleware(SessionMiddleware, secret_key=str(SESSION_SECRET), max_age=SEVEN_DAYS_SECONDS)

# Signed cookie serializer for additional session integrity (used in /login)
COOKIE_SERIALIZER = URLSafeSerializer(str(SESSION_SECRET), salt="session-salt")

# ------------------------------------------------------------
# Database dependency (DI)
# ------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASSWORD") or os.environ.get("DB_PASS", "16042006")
DB_NAME = os.environ.get("DB_NAME", "krushibandhu_ai")

# ------------------------------------------------------------
# Satellite Analysis Configuration
# ------------------------------------------------------------
SENTINEL_HUB_CLIENT_ID = os.environ.get("SENTINEL_HUB_CLIENT_ID", "")
SENTINEL_HUB_CLIENT_SECRET = os.environ.get("SENTINEL_HUB_CLIENT_SECRET", "")
SENTINEL_HUB_BASE_URL = "https://services.sentinel-hub.com/api/v1"


def get_db() -> Generator[mysql.connector.MySQLConnection, None, None]:
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )
    try:
        yield conn
    finally:
        conn.close()

# ------------------------------------------------------------
# Database bootstrap: ensure users table exists
# ------------------------------------------------------------
def ensure_users_table(db: mysql.connector.MySQLConnection) -> None:
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()
    finally:
        cursor.close()

@app.on_event("startup")
def _startup_init_db():
    # Open a short-lived connection to ensure the users table exists
    try:
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    except Exception as e:
        # Don't crash app startup if DB creds are wrong; endpoints will report DB errors as needed.
        print(f"[startup] Database connection failed (continuing without DB init): {e}")
        return
    try:
        ensure_users_table(conn)
        # Also ensure farms table exists at startup
        try:
            ensure_farms_table(conn)
        except Exception as _e:
            print(f"[startup] ensure_farms_table warning: {_e}")
        # Also ensure predictions table exists at startup
        try:
            create_predictions_table(conn)
        except Exception as _e:
            print(f"[startup] create_predictions_table warning: {_e}")
        # Also ensure calendar events table exists at startup
        try:
            create_calendar_events_table(conn)
        except Exception as _e:
            print(f"[startup] create_calendar_events_table warning: {_e}")
        # Also ensure user predictions table exists at startup
        try:
            create_user_predictions_table(conn)
        except Exception as _e:
            print(f"[startup] create_user_predictions_table warning: {_e}")
        # Also ensure optimization results table exists at startup
        try:
            create_optimization_results_table(conn)
        except Exception as _e:
            print(f"[startup] create_optimization_results_table warning: {_e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# Farms table bootstrap and helpers
# ------------------------------------------------------------
def ensure_column_exists(db: mysql.connector.MySQLConnection, table: str, column: str, definition: str) -> None:
    cur = db.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (DB_NAME, table, column),
        )
        exists = cur.fetchone() is not None
    finally:
        cur.close()
    if not exists:
        c = db.cursor()
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            db.commit()
        finally:
            c.close()

def ensure_farms_table(db: mysql.connector.MySQLConnection) -> None:
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS farms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                farm_name VARCHAR(255) NOT NULL,
                plot_boundary JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_farms_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        db.commit()
        # Ensure plot_boundary column exists even on legacy tables
        ensure_column_exists(db, "farms", "plot_boundary", "JSON")
    finally:
        cursor.close()

# ------------------------------------------------------------
# Schemas
# ------------------------------------------------------------
class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str

class PredictAdvancedBody(BaseModel):
    district: str
    crop: str
    season: Optional[str] = None
    variety: Optional[str] = None

class Intervention(BaseModel):
    fertilizer: str
    quantity: float
    unit: str  # e.g., "bags_per_hectare", "kg_per_hectare", "liters_per_hectare"

class OptimizeYieldBody(BaseModel):
    district: str
    crop: str
    season: Optional[str] = None
    variety: Optional[str] = None
    interventions: list[Intervention]

class OptimizeSoilBody(BaseModel):
    district: str
    crop: str
    season: Optional[str] = None
    variety: Optional[str] = None
    interventions: list[Intervention]

class FarmData(BaseModel):
    farm_name: str
    boundary_coordinates: list[list[float]]  # [[lat, lng], [lat, lng], ...]

class CalendarEventBody(BaseModel):
    event_title: str
    event_date: date
    event_type: str  # 'AI_Suggestion' or 'Farmer_Log'
    details: Optional[str] = None

class HarvestLogBody(BaseModel):
    actual_yield_kg_per_hectare: float

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# ------------------------------------------------------------
# Model artifacts (lazy load and cache)
# ------------------------------------------------------------
MODEL_CACHE: Dict[str, Any] = {"loaded": False}

def load_artifacts() -> None:
    if MODEL_CACHE.get("loaded"):
        return
    project_root = os.path.dirname(os.path.dirname(__file__))
    models_dir = os.path.join(project_root, "models")
    model_path = os.path.join(models_dir, "xgb_yield_model.pkl")
    preprocess_path = os.path.join(models_dir, "preprocessors.pkl")
    spec_path = os.path.join(models_dir, "feature_spec.json")
    with open(model_path, "rb") as f:
        MODEL_CACHE["model"] = pickle.load(f)
    with open(preprocess_path, "rb") as f:
        pre = pickle.load(f)
        MODEL_CACHE["encoders"] = pre.get("categorical_encoders", {})
        MODEL_CACHE["imputer"] = pre.get("imputer")
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)
        MODEL_CACHE["feature_columns"] = spec.get("feature_columns", [])
    MODEL_CACHE["loaded"] = True

def _label_encode(enc, value: str) -> int:
    # Map unseen label to 'unknown' if present, else first class
    classes = set(enc.classes_.tolist())
    v = value if value in classes else ("unknown" if "unknown" in classes else enc.classes_[0])
    return int(enc.transform([v])[0])

def _safe_ratio(a: float, b: float) -> float:
    try:
        if b is None or float(b) == 0:
            return np.nan
        return float(a) / float(b)
    except Exception:
        return np.nan

def _compute_soil_health(n: Optional[float], p: Optional[float], k: Optional[float], oc: Optional[float]) -> float:
    # Heuristic normalization for online inference (training used dataset quantiles)
    def norm(x, lo, hi):
        try:
            if x is None:
                return 0.0
            x = float(x)
            return max(0.0, min(1.0, (x - lo) / (hi - lo)))
        except Exception:
            return 0.0
    n_n = norm(n, 0, 500)
    p_n = norm(p, 0, 300)
    k_n = norm(k, 0, 600)
    oc_n = norm(oc, 0, 5)
    return round(0.3*n_n + 0.3*p_n + 0.3*k_n + 0.1*oc_n, 4)

def _none_if_nan(x):
    try:
        fx = float(x)
        if np.isnan(fx) or np.isinf(fx):
            return None
        return x
    except Exception:
        return x

# ------------------------------------------------------------
# Farm Data Helpers
# ------------------------------------------------------------
def get_farm_data(user_id: int, db: mysql.connector.MySQLConnection) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent farm data for a user from the database."""
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, farm_name, plot_boundary
            FROM farms
            WHERE user_id = %s
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        farm = cursor.fetchone()
        if farm:
            boundary_raw = farm.get("plot_boundary")
            boundary_coords = []
            if isinstance(boundary_raw, str):
                try:
                    boundary_coords = json.loads(boundary_raw)
                except json.JSONDecodeError:
                    boundary_coords = [] # Handle malformed JSON
            elif isinstance(boundary_raw, (list, dict)):
                boundary_coords = boundary_raw

            return {
                "id": farm.get("id"),
                "farm_name": farm.get("farm_name") or "My Farm",
                "boundary_coordinates": boundary_coords,
            }
        return None
    except Exception as e:
        print(f"Error retrieving farm data: {e}")
        return None
    finally:
        cursor.close()

# ------------------------------------------------------------
# Harvest Logs Helpers
# ------------------------------------------------------------
def create_harvest_logs_table(db: mysql.connector.MySQLConnection) -> None:
    """Create the harvest_logs table if it doesn't exist."""
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS harvest_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farm_id INT NOT NULL,
                season VARCHAR(50) NOT NULL,
                actual_yield_kg_per_hectare DECIMAL(10,2) NOT NULL,
                logged_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
                INDEX idx_farm_season_date (farm_id, season, logged_date)
            )
            """
        )
        db.commit()
    finally:
        cursor.close()

def get_user_farm_id(user_id: int, db: mysql.connector.MySQLConnection) -> Optional[int]:
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM farms WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        return int(row["id"]) if row else None
    finally:
        cursor.close()

def infer_current_season(today: Optional[date] = None) -> str:
    """Infer Indian cropping season from month. Simplified heuristic.
    - Rabi: Nov-Mar (11-3)
    - Zaid: Apr-Jun (4-6)
    - Kharif: Jul-Oct (7-10)
    """
    d = today or date.today()
    m = d.month
    if m in (11, 12, 1, 2, 3):
        return "Rabi"
    if m in (4, 5, 6):
        return "Zaid"
    return "Kharif"


# ------------------------------------------------------------
# API: Market prices
# ------------------------------------------------------------
@app.get("/market-prices")
def api_market_prices(request: Request, district: str, crop: str, days: int = 30, db=Depends(get_db)):
    """
    Get recent wholesale market price history for a district and crop from cache.

    Query params:
    - district: District name (e.g., "Cuttack")
    - crop: Commodity/crop name (e.g., "Paddy")
    - days: Number of days of history to return (default 30)
    """
    try:
        # Authentication required
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        if not district or not crop:
            raise HTTPException(status_code=400, detail="Both 'district' and 'crop' query parameters are required")

        # Bound days for safety
        if days <= 0:
            days = 7
        if days > 180:
            days = 180

        rows = get_cached_market_prices(db, district=district.strip(), crop=crop.strip(), days=days)
        return {"district": district, "crop": crop, "days": days, "prices": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/health")
def chat_health():
    """Simple health endpoint to report if Gemini is configured and library importable."""
    status = {
        "gemini_library": False,
        "api_key_present": False,
        "api_key_masked": None,
        "will_use": False,
    }
    try:
        import google.generativeai  # noqa: F401
        status["gemini_library"] = True
    except Exception:
        status["gemini_library"] = False

    key = os.getenv("GEMINI_API_KEY")
    if key and key != "your_gemini_api_key_here":
        status["api_key_present"] = True
        status["api_key_masked"] = key[:4] + "****" if len(key) >= 4 else "****"
    status["will_use"] = bool(status["gemini_library"] and status["api_key_present"])
    return status

def calculate_farm_area(boundary_coordinates: list) -> float:
    """Calculate farm area in hectares from boundary coordinates."""
    try:
        if len(boundary_coordinates) < 3:
            return 0.0
        
        # Create a polygon from the coordinates
        polygon = Polygon(boundary_coordinates)
        
        # Project to a suitable UTM zone for area calculation
        # For India, we'll use UTM Zone 44N (EPSG:32644)
        utm_crs = pyproj.CRS.from_epsg(32644)
        wgs84_crs = pyproj.CRS.from_epsg(4326)
        
        # Transform the polygon to UTM for accurate area calculation
        transformer = pyproj.Transformer.from_crs(wgs84_crs, utm_crs, always_xy=True)
        utm_polygon = transform(transformer.transform, polygon)
        
        # Calculate area in square meters, then convert to hectares
        area_sqm = utm_polygon.area
        area_hectares = area_sqm / 10000
        
        return round(area_hectares, 4)
    except Exception as e:
        print(f"Error calculating farm area: {e}")
        return 0.0

def get_farm_center(boundary_coordinates: list) -> tuple[float, float]:
    """Get the center point of the farm boundary."""
    try:
        if len(boundary_coordinates) < 3:
            return (0.0, 0.0)
        
        polygon = Polygon(boundary_coordinates)
        centroid = polygon.centroid
        return (float(centroid.y), float(centroid.x))  # lat, lng
    except Exception as e:
        print(f"Error calculating farm center: {e}")
        return (0.0, 0.0)

# ------------------------------------------------------------
# Calendar Management Functions
# ------------------------------------------------------------
def create_predictions_table(db: mysql.connector.MySQLConnection):
    """Ensure the predictions table exists in the database."""
    cursor = db.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farm_id INT NOT NULL,
                prediction_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
            )
        """)
        db.commit()
        print("'predictions' table checked/created successfully.")
    except mysql.connector.Error as err:
        print(f"Failed to create 'predictions' table: {err}")
        db.rollback()
    finally:
        cursor.close()

def create_user_predictions_table(db: mysql.connector.MySQLConnection):
    """Create or migrate the user_predictions table - independent of farms."""
    cursor = db.cursor()
    try:
        # Create base table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                crop VARCHAR(100) NOT NULL,
                district VARCHAR(100) NOT NULL,
                season VARCHAR(50) NOT NULL,
                variety VARCHAR(100),
                predicted_yield_kg_per_hectare DECIMAL(10,2) NOT NULL,
                prediction_date DATE NOT NULL,
                prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                additional_data JSON,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_user_date (user_id, prediction_date),
                INDEX idx_crop_district (crop, district)
            )
        """)

        # Migration: ensure user_id is nullable (for anonymous saves)
        try:
            cursor.execute("ALTER TABLE user_predictions MODIFY user_id INT NULL")
            print("user_predictions.user_id set to NULLABLE")
        except Exception as e:
            print(f"user_id NULLABLE migration skipped or failed (likely already NULL): {e}")
        db.commit()
        print("'user_predictions' table checked/created successfully.")
    except mysql.connector.Error as err:
        print(f"Failed to create 'user_predictions' table: {err}")
        db.rollback()
    finally:
        cursor.close()

def create_calendar_events_table(db: mysql.connector.MySQLConnection):
    """Create the farm_calendar_events table if it doesn't exist."""
    cursor = db.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS farm_calendar_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farm_id INT NOT NULL,
                event_date DATE NOT NULL,
                event_title VARCHAR(255) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
                INDEX idx_farm_date (farm_id, event_date),
                INDEX idx_event_type (event_type)
            )
        """)
        db.commit()
    except Exception as e:
        print(f"Error creating calendar events table: {e}")
        raise
    finally:
        cursor.close()

def get_crop_calendar_events(crop: str, season: str = "Kharif") -> list[Dict[str, Any]]:
    """Generate calendar events based on crop type and season."""
    crop_lower = crop.lower()
    events = []
    
    # Base events for all crops
    base_events = [
        {"title": "Soil Preparation", "days_offset": -30, "type": "AI_Suggestion", "details": "Prepare soil by plowing and leveling. Test soil pH and nutrient levels."},
        {"title": "Seed Selection", "days_offset": -15, "type": "AI_Suggestion", "details": "Select high-quality seeds suitable for your region and soil conditions."},
        {"title": "Pre-sowing Irrigation", "days_offset": -7, "type": "AI_Suggestion", "details": "Ensure adequate soil moisture before sowing."},
        {"title": "Sowing", "days_offset": 0, "type": "AI_Suggestion", "details": "Optimal sowing time for maximum yield potential."},
        {"title": "First Irrigation", "days_offset": 7, "type": "AI_Suggestion", "details": "Apply first irrigation after germination."},
        {"title": "Weed Control", "days_offset": 15, "type": "AI_Suggestion", "details": "Monitor and control weeds to prevent competition."},
        {"title": "Mid-season Assessment", "days_offset": 45, "type": "AI_Suggestion", "details": "Assess crop health, pest/disease status, and nutrient requirements."},
        {"title": "Harvest Preparation", "days_offset": 90, "type": "AI_Suggestion", "details": "Prepare for harvest - check maturity and arrange harvesting equipment."},
        {"title": "Harvest", "days_offset": 100, "type": "AI_Suggestion", "details": "Optimal harvest time for best quality and yield."},
        {"title": "Post-harvest Management", "days_offset": 110, "type": "AI_Suggestion", "details": "Clean, dry, and store harvested produce properly."}
    ]
    
    # Crop-specific events
    if "paddy" in crop_lower or "rice" in crop_lower:
        events.extend([
            {"title": "Nursery Preparation", "days_offset": -25, "type": "AI_Suggestion", "details": "Prepare rice nursery for transplanting."},
            {"title": "Transplanting", "days_offset": 20, "type": "AI_Suggestion", "details": "Transplant rice seedlings to main field."},
            {"title": "Water Management", "days_offset": 30, "type": "AI_Suggestion", "details": "Maintain proper water level in paddy fields."},
            {"title": "Panicle Initiation", "days_offset": 60, "type": "AI_Suggestion", "details": "Critical stage - ensure adequate nutrition and water."},
            {"title": "Flowering Stage", "days_offset": 75, "type": "AI_Suggestion", "details": "Monitor flowering and grain development."}
        ])
    elif "wheat" in crop_lower:
        events.extend([
            {"title": "Crown Root Development", "days_offset": 20, "type": "AI_Suggestion", "details": "Monitor crown root development and apply nutrients if needed."},
            {"title": "Tillering Stage", "days_offset": 35, "type": "AI_Suggestion", "details": "Critical stage for tiller development and yield potential."},
            {"title": "Jointing Stage", "days_offset": 50, "type": "AI_Suggestion", "details": "Monitor stem elongation and apply top dressing."},
            {"title": "Boot Stage", "days_offset": 70, "type": "AI_Suggestion", "details": "Monitor flag leaf emergence and grain development."},
            {"title": "Heading Stage", "days_offset": 80, "type": "AI_Suggestion", "details": "Monitor flowering and grain filling."}
        ])
    elif "maize" in crop_lower or "corn" in crop_lower:
        events.extend([
            {"title": "V4 Stage (4-leaf)", "days_offset": 20, "type": "AI_Suggestion", "details": "Monitor early growth and apply side dressing."},
            {"title": "V8 Stage (8-leaf)", "days_offset": 35, "type": "AI_Suggestion", "details": "Critical stage for yield determination."},
            {"title": "Tasseling", "days_offset": 60, "type": "AI_Suggestion", "details": "Monitor pollination and grain development."},
            {"title": "Silking", "days_offset": 65, "type": "AI_Suggestion", "details": "Critical pollination period - ensure adequate moisture."},
            {"title": "Grain Filling", "days_offset": 75, "type": "AI_Suggestion", "details": "Monitor grain development and moisture content."}
        ])
    elif "cotton" in crop_lower:
        events.extend([
            {"title": "Square Formation", "days_offset": 40, "type": "AI_Suggestion", "details": "Monitor square development and pest control."},
            {"title": "Flowering", "days_offset": 60, "type": "AI_Suggestion", "details": "Monitor flowering and boll development."},
            {"title": "Boll Development", "days_offset": 80, "type": "AI_Suggestion", "details": "Critical stage for fiber quality and yield."},
            {"title": "Boll Opening", "days_offset": 120, "type": "AI_Suggestion", "details": "Monitor boll opening and prepare for picking."},
            {"title": "First Picking", "days_offset": 130, "type": "AI_Suggestion", "details": "Begin cotton picking when bolls are ready."}
        ])
    
    # Combine base and crop-specific events
    all_events = base_events + events
    
    # Convert to calendar events with actual dates
    calendar_events = []
    base_date = date.today()  # Use today as reference point
    
    for event in all_events:
        event_date = base_date + timedelta(days=event["days_offset"])
        calendar_events.append({
            "event_date": event_date,
            "event_title": event["title"],
            "event_type": event["type"],
            "details": event["details"]
        })
    
    return calendar_events

def create_farm_calendar_events(farm_id: int, crop: str, season: str, db: mysql.connector.MySQLConnection) -> None:
    """Create calendar events for a new farm based on crop type."""
    try:
        # Ensure calendar events table exists
        create_calendar_events_table(db)
        
        # Get crop-specific calendar events
        events = get_crop_calendar_events(crop, season)
        
        # Insert events into database
        cursor = db.cursor()
        try:
            for event in events:
                cursor.execute("""
                    INSERT INTO farm_calendar_events (farm_id, event_date, event_title, event_type, details)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    farm_id,
                    event["event_date"],
                    event["event_title"],
                    event["event_type"],
                    event["details"]
                ))
            db.commit()
        finally:
            cursor.close()
            
    except Exception as e:
        print(f"Error creating farm calendar events: {e}")
        raise

def get_farm_calendar_events(farm_id: int, db: mysql.connector.MySQLConnection) -> list[Dict[str, Any]]:
    """Get all calendar events for a farm."""
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, event_date, event_title, event_type, details, created_at, updated_at
            FROM farm_calendar_events
            WHERE farm_id = %s
            ORDER BY event_date ASC
        """, (farm_id,))
        events = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for event in events:
            if event["event_date"]:
                event["event_date"] = event["event_date"].isoformat()
            if event["created_at"]:
                event["created_at"] = event["created_at"].isoformat()
            if event["updated_at"]:
                event["updated_at"] = event["updated_at"].isoformat()
        
        return events
    except Exception as e:
        print(f"Error retrieving farm calendar events: {e}")
        return []
    finally:
        cursor.close()

def add_calendar_event(farm_id: int, event_data: CalendarEventBody, db: mysql.connector.MySQLConnection) -> int:
    """Add a new calendar event to a farm."""
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO farm_calendar_events (farm_id, event_date, event_title, event_type, details)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            farm_id,
            event_data.event_date,
            event_data.event_title,
            event_data.event_type,
            event_data.details
        ))
        db.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error adding calendar event: {e}")
        raise
    finally:
        cursor.close()

# ------------------------------------------------------------
# Market Intelligence (Agmarknet cache)
# ------------------------------------------------------------
def create_market_prices_table(db: mysql.connector.MySQLConnection) -> None:
    """Create the market_prices cache table if it doesn't exist."""
    cursor = db.cursor()
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
        db.commit()
    except Exception as e:
        print(f"Error creating market_prices table: {e}")
        raise
    finally:
        cursor.close()

def create_optimization_results_table(db: mysql.connector.MySQLConnection) -> None:
    """Create the optimization_results table if it doesn't exist."""
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                farm_id INT NULL,
                district VARCHAR(100) NOT NULL,
                crop VARCHAR(100) NOT NULL,
                season VARCHAR(50) NOT NULL,
                variety VARCHAR(100),
                base_yield_kg_per_hectare DECIMAL(10,2) NOT NULL,
                optimized_yield_kg_per_hectare DECIMAL(10,2) NOT NULL,
                yield_improvement_kg_per_hectare DECIMAL(10,2) NOT NULL,
                improvement_percentage DECIMAL(5,2) NOT NULL,
                applied_interventions JSON NOT NULL,
                soil_analysis JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
                INDEX idx_user_date (user_id, created_at),
                INDEX idx_district_crop (district, crop)
            )
            """
        )
        db.commit()
    except Exception as e:
        print(f"Error creating optimization_results table: {e}")
        raise
    finally:
        cursor.close()

def save_optimization_result(db: mysql.connector.MySQLConnection, result_data: dict, user_id: int = None, farm_id: int = None) -> int:
    """Save optimization result to database and return the ID."""
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO optimization_results (
                user_id, farm_id, district, crop, season, variety,
                base_yield_kg_per_hectare, optimized_yield_kg_per_hectare,
                yield_improvement_kg_per_hectare, improvement_percentage,
                applied_interventions, soil_analysis
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id, farm_id, result_data["district"], result_data["crop"],
                result_data["season"], result_data.get("variety"),
                result_data["base_yield_kg_per_hectare"], result_data["optimized_yield_kg_per_hectare"],
                result_data["yield_improvement_kg_per_hectare"], result_data["improvement_percentage"],
                json.dumps(result_data["applied_interventions"]), 
                json.dumps(result_data.get("soil_analysis", {}))
            )
        )
        db.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error saving optimization result: {e}")
        db.rollback()
        raise
    finally:
        cursor.close()

def create_fertilizer_calendar_events(db: mysql.connector.MySQLConnection, farm_id: int, interventions: list, crop: str) -> None:
    """Create calendar events for fertilizer applications."""
    if not farm_id or not interventions:
        return
        
    try:
        cursor = db.cursor()
        today = date.today()
        
        for i, intervention in enumerate(interventions):
            # Schedule fertilizer application 7 days from now, with different days for multiple fertilizers
            application_date = today + timedelta(days=7 + i * 3)
            
            event_title = f"Apply {intervention['fertilizer']}"
            event_details = f"Apply {intervention['quantity']} {intervention['unit'].replace('_', ' ')} of {intervention['fertilizer']} for {crop} optimization. Expected yield improvement based on AI analysis."
            
            cursor.execute("""
                INSERT INTO farm_calendar_events (farm_id, event_date, event_title, event_type, details)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                farm_id,
                application_date,
                event_title,
                'AI_Suggestion',
                event_details
            ))
        
        db.commit()
        print(f"Created {len(interventions)} fertilizer calendar events for farm {farm_id}")
        
    except Exception as e:
        print(f"Error creating fertilizer calendar events: {e}")
        db.rollback()
    finally:
        cursor.close()

def get_optimization_results(db: mysql.connector.MySQLConnection, user_id: int = None, farm_id: int = None, limit: int = 10) -> list[dict]:
    """Get optimization results from database."""
    cursor = db.cursor(dictionary=True)
    try:
        if user_id:
            cursor.execute("""
                SELECT * FROM optimization_results 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (user_id, limit))
        elif farm_id:
            cursor.execute("""
                SELECT * FROM optimization_results 
                WHERE farm_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (farm_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM optimization_results 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
        
        results = cursor.fetchall() or []
        
        # Parse JSON fields
        for result in results:
            if result.get("applied_interventions"):
                try:
                    result["applied_interventions"] = json.loads(result["applied_interventions"])
                except json.JSONDecodeError:
                    result["applied_interventions"] = []
            
            if result.get("soil_analysis"):
                try:
                    result["soil_analysis"] = json.loads(result["soil_analysis"])
                except json.JSONDecodeError:
                    result["soil_analysis"] = {}
            
            # Convert datetime to string for JSON serialization
            if result.get("created_at"):
                result["created_at"] = result["created_at"].isoformat()
        
        return results
        
    except Exception as e:
        print(f"Error getting optimization results: {e}")
        return []
    finally:
        cursor.close()

def get_cached_market_prices(db: mysql.connector.MySQLConnection, district: str, crop: str, days: int = 30) -> list[dict]:
    """Return recent cached prices for a district and crop for last N days."""
    cursor = db.cursor(dictionary=True)
    try:
        create_market_prices_table(db)
        cursor.execute(
            """
            SELECT market_name, district, crop, price_per_quintal, date
            FROM market_prices
            WHERE LOWER(district) = LOWER(%s)
              AND LOWER(crop) = LOWER(%s)
              AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY date DESC, market_name ASC
            """,
            (district, crop, days),
        )
        rows = cursor.fetchall() or []
        # Serialize date
        for r in rows:
            if isinstance(r.get("date"), (datetime, date)):
                r["date"] = r["date"].isoformat()
        return rows
    except Exception as e:
        print(f"Error fetching cached market prices: {e}")
        return []
    finally:
        cursor.close()

# ------------------------------------------------------------
# Fertilizer Composition Database
# ------------------------------------------------------------
FERTILIZER_COMPOSITION = {
    "urea": {
        "nitrogen_percent": 46.0,
        "phosphorus_percent": 0.0,
        "potassium_percent": 0.0,
        "weight_per_bag_kg": 50.0
    },
    "dap": {  # Diammonium Phosphate
        "nitrogen_percent": 18.0,
        "phosphorus_percent": 46.0,
        "potassium_percent": 0.0,
        "weight_per_bag_kg": 50.0
    },
    "mop": {  # Muriate of Potash
        "nitrogen_percent": 0.0,
        "phosphorus_percent": 0.0,
        "potassium_percent": 60.0,
        "weight_per_bag_kg": 50.0
    },
    "ssp": {  # Single Super Phosphate
        "nitrogen_percent": 0.0,
        "phosphorus_percent": 16.0,
        "potassium_percent": 0.0,
        "weight_per_bag_kg": 50.0
    },
    "npk_19_19_19": {
        "nitrogen_percent": 19.0,
        "phosphorus_percent": 19.0,
        "potassium_percent": 19.0,
        "weight_per_bag_kg": 50.0
    },
    "npk_20_20_20": {
        "nitrogen_percent": 20.0,
        "phosphorus_percent": 20.0,
        "potassium_percent": 20.0,
        "weight_per_bag_kg": 50.0
    },
    "compost": {
        "nitrogen_percent": 1.5,
        "phosphorus_percent": 1.0,
        "potassium_percent": 1.5,
        "weight_per_bag_kg": 25.0  # Compost typically comes in smaller bags
    },
    "farmyard_manure": {
        "nitrogen_percent": 0.5,
        "phosphorus_percent": 0.3,
        "potassium_percent": 0.5,
        "weight_per_bag_kg": 25.0
    }
}

def convert_intervention_to_nutrients(intervention: Intervention) -> Dict[str, float]:
    """Convert farmer-friendly intervention to scientific nutrient values."""
    fertilizer_key = intervention.fertilizer.lower().replace(" ", "_")
    
    if fertilizer_key not in FERTILIZER_COMPOSITION:
        # Default to urea if fertilizer not found
        fertilizer_key = "urea"
    
    composition = FERTILIZER_COMPOSITION[fertilizer_key]
    
    # Convert quantity to kg per hectare
    if intervention.unit == "bags_per_hectare":
        kg_per_hectare = intervention.quantity * composition["weight_per_bag_kg"]
    elif intervention.unit == "kg_per_hectare":
        kg_per_hectare = intervention.quantity
    elif intervention.unit == "liters_per_hectare":
        # Assume liquid fertilizers have similar density to water (1 kg/L)
        kg_per_hectare = intervention.quantity
    else:
        # Default to kg per hectare
        kg_per_hectare = intervention.quantity
    
    # Calculate nutrient amounts in kg per hectare
    nitrogen_kg_ha = kg_per_hectare * (composition["nitrogen_percent"] / 100.0)
    phosphorus_kg_ha = kg_per_hectare * (composition["phosphorus_percent"] / 100.0)
    potassium_kg_ha = kg_per_hectare * (composition["potassium_percent"] / 100.0)
    
    # Convert to mg/kg (assuming soil depth of 15cm and bulk density of 1.3 g/cm³)
    # 1 hectare = 10,000 m², soil volume = 10,000 * 0.15 = 1,500 m³
    # Soil mass = 1,500 * 1,300 = 1,950,000 kg
    soil_mass_kg_per_hectare = 1950000
    
    nitrogen_mg_kg = (nitrogen_kg_ha * 1_000_000) / soil_mass_kg_per_hectare
    phosphorus_mg_kg = (phosphorus_kg_ha * 1_000_000) / soil_mass_kg_per_hectare
    potassium_mg_kg = (potassium_kg_ha * 1_000_000) / soil_mass_kg_per_hectare
    
    return {
        "nitrogen_mg_kg": nitrogen_mg_kg,
        "phosphorus_mg_kg": phosphorus_mg_kg,
        "potassium_mg_kg": potassium_mg_kg,
        "fertilizer_used": fertilizer_key
    }

def _calculate_soil_health_score(n: float, p: float, k: float, oc: float) -> float:
    """Calculate soil health score based on NPK and organic carbon."""
    def norm(x, lo, hi):
        try:
            if x is None:
                return 0.0
            fx = float(x)
            if fx < lo:
                return 0.0
            if fx > hi:
                return 1.0
            return (fx - lo) / (hi - lo)
        except Exception:
            return 0.0
    
    n_n = norm(n, 0, 300)
    p_n = norm(p, 0, 300)
    k_n = norm(k, 0, 600)
    oc_n = norm(oc, 0, 5)
    return round(0.3*n_n + 0.3*p_n + 0.3*k_n + 0.1*oc_n, 4)

def _build_feature_vector(prepared_data: Dict[str, Any], feature_columns: list, encoders: Dict, imputer) -> np.ndarray:
    """Build feature vector from prepared data for model prediction."""
    try:
        # This is a simplified version - in practice, you'd need the full feature engineering logic
        # from the original prepare_features_from_db function
        features = []
        
        # Add basic features (this would need to be expanded based on your actual feature engineering)
        soil = prepared_data.get("soil", {})
        engineering = prepared_data.get("engineering", {})
        
        # Add soil features
        features.extend([
            soil.get("n_mgkg", 0) or 0,
            soil.get("p_mgkg", 0) or 0,
            soil.get("k_mgkg", 0) or 0,
            soil.get("oc_percent", 0) or 0,
            soil.get("ph", 7) or 7,
        ])
        
        # Add engineered features
        features.extend([
            engineering.get("soil_health_score", 0) or 0,
            engineering.get("npk_sum", 0) or 0,
            engineering.get("ratio_n_p", 0) or 0,
            engineering.get("ratio_k_p", 0) or 0,
        ])
        
        # Add weather features (simplified)
        weather = prepared_data.get("weather", {})
        features.extend([
            weather.get("temperature", 25) or 25,
            weather.get("humidity", 60) or 60,
            weather.get("rainfall", 100) or 100,
        ])
        
        # Pad or truncate to match expected feature count
        expected_features = len(feature_columns) if feature_columns else 12
        while len(features) < expected_features:
            features.append(0.0)
        features = features[:expected_features]
        
        return np.array(features).reshape(1, -1)
        
    except Exception as e:
        print(f"Error building feature vector: {e}")
        # Return a default feature vector
        return np.zeros((1, 12))

# ------------------------------------------------------------
# Satellite Analysis Functions
# ------------------------------------------------------------
def get_sentinel_hub_token() -> Optional[str]:
    """Get access token from Sentinel Hub API."""
    if not SENTINEL_HUB_CLIENT_ID or not SENTINEL_HUB_CLIENT_SECRET:
        return None

    token_url = f"{SENTINEL_HUB_BASE_URL}/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": SENTINEL_HUB_CLIENT_ID,
        "client_secret": SENTINEL_HUB_CLIENT_SECRET,
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.json().get("access_token")
    except requests.exceptions.HTTPError as e:
        print(f"Error getting Sentinel Hub token: {e}")
        # If it's a server error, we expect it might be temporary. Silently fallback.
        return None
    except requests.exceptions.RequestException as e:
        # For other network errors (e.g., DNS failure, connection refused)
        print(f"Network error connecting to Sentinel Hub: {e}")
        return None

def get_satellite_ndvi(boundary_coordinates: list, access_token: str) -> Optional[Dict[str, Any]]:
    """Get NDVI data from Sentinel Hub for the given farm boundary."""
    try:
        if len(boundary_coordinates) < 3:
            return None
        
        # Create bounding box from farm coordinates
        lats = [coord[0] for coord in boundary_coordinates]
        lngs = [coord[1] for coord in boundary_coordinates]
        
        bbox = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lng": min(lngs),
            "max_lng": max(lngs)
        }
        
        # Create the request payload for Sentinel Hub
        request_payload = {
            "input": {
                "bounds": {
                    "bbox": [bbox["min_lng"], bbox["min_lat"], bbox["max_lng"], bbox["max_lat"]],
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                    }
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {
                                "from": "2024-01-01T00:00:00Z",
                                "to": "2024-12-31T23:59:59Z"
                            },
                            "maxCloudCoverage": 20
                        }
                    }
                ]
            },
            "output": {
                "width": 512,
                "height": 512,
                "responses": [
                    {
                        "identifier": "default",
                        "format": {"type": "image/tiff"}
                    }
                ]
            },
            "evalscript": """
                //VERSION=3
                function setup() {
                    return {
                        input: ["B02", "B03", "B04", "B08", "dataMask"],
                        output: { bands: 4 }
                    };
                }
                
                function evaluatePixel(sample) {
                    // Calculate NDVI
                    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                    
                    // Calculate RGB for visualization
                    let r = sample.B04 * 2.5;
                    let g = sample.B03 * 2.5;
                    let b = sample.B02 * 2.5;
                    
                    return [r, g, b, ndvi * sample.dataMask];
                }
            """
        }
        
        # Make the request to Sentinel Hub
        response = requests.post(
            f"{SENTINEL_HUB_BASE_URL}/process",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=request_payload,
            timeout=60
        )
        response.raise_for_status()
        
        # For now, return a mock NDVI response since we can't easily process the TIFF
        # In a production system, you'd process the returned image data
        return {
            "ndvi_data": "base64_encoded_tiff_data",  # This would be the actual processed data
            "bounds": bbox,
            "resolution": "10m",
            "cloud_coverage": "< 20%",
            "acquisition_date": "2024-01-15",
            "ndvi_stats": {
                "mean": 0.65,
                "min": 0.12,
                "max": 0.89,
                "std": 0.15
            },
            "health_score": 0.72  # Derived from NDVI analysis
        }
        
    except Exception as e:
        print(f"Error getting satellite NDVI data: {e}")
        return None

# ------------------------------------------------------------
# Recommendation engine (prescriptive suggestions)
# ------------------------------------------------------------
def _get_crop_heuristics(crop: str) -> Dict[str, Any]:
    """Return simple optimal ranges per crop (heuristics). Units follow our DB columns.
    Values are illustrative and can be refined later per crop agronomy guides.
    """
    crop_l = (crop or "").lower()
    base = {
        "ph": (6.0, 7.5),
        "oc_percent": (0.5, 1.0),
        "n_mgkg": (280, 560),
        "p_mgkg": (10, 25),
        "k_mgkg": (120, 300),
        "weekly_rain_mm": (20, 60),
    }
    if "paddy" in crop_l:
        base.update({"ph": (5.5, 7.0), "weekly_rain_mm": (30, 80)})
    if "wheat" in crop_l:
        base.update({"ph": (6.0, 7.5), "weekly_rain_mm": (10, 40)})
    if "maize" in crop_l:
        base.update({"ph": (5.8, 7.0), "weekly_rain_mm": (20, 50)})
    return base

def _within(v: Optional[float], lo: float, hi: float) -> bool:
    try:
        if v is None:
            return False
        fv = float(v)
        return lo <= fv <= hi
    except Exception:
        return False

def generate_recommendations(crop: str, prepared: Dict[str, Any], seven_day_forecast: Any) -> list:
    recs = []
    soil = prepared.get("soil") or {}
    weather = prepared.get("weather") or {}
    eng = prepared.get("engineering") or {}

    h = _get_crop_heuristics(crop)

    # Soil pH
    ph = soil.get("ph_level")
    if not _within(ph, *h["ph"]):
        if ph is not None:
            if float(ph) < h["ph"][0]:
                recs.append("Soil pH is low. Consider liming to raise pH towards the optimal range.")
            else:
                recs.append("Soil pH is high. Consider applying organic matter or acidifying amendments to lower pH.")

    # Organic Carbon
    oc = soil.get("organic_carbon_percent")
    if not _within(oc, *h["oc_percent"]):
        recs.append("Organic carbon is suboptimal. Incorporate farmyard manure or crop residues to improve soil health.")

    # NPK
    n = soil.get("nitrogen_mg_per_kg")
    p = soil.get("phosphorus_mg_per_kg")
    k = soil.get("potassium_mg_per_kg")
    if n is not None and float(n) < h["n_mgkg"][0]:
        recs.append("Nitrogen level appears low. Applying a top dressing of urea (based on soil test recommendations) could improve yield.")
    if p is not None and float(p) < h["p_mgkg"][0]:
        recs.append("Phosphorus seems low. Consider DAP/SSP application at recommended dose during next field operation.")
    if k is not None and float(k) < h["k_mgkg"][0]:
        recs.append("Potassium is low. Consider MOP application to strengthen crop resilience and yield.")

    # Weather-driven irrigation suggestion
    recent = weather.get("predicted_rainfall")  # today's mm
    # Sum next 7 days rainfall if available
    next7_sum = 0.0
    try:
        days = []
        if isinstance(seven_day_forecast, dict) and isinstance(seven_day_forecast.get("forecast_days"), list):
            days = seven_day_forecast.get("forecast_days")
        elif isinstance(seven_day_forecast, list):
            days = seven_day_forecast
        for d in days:
            mm = d.get("expected_rainfall_mm") if isinstance(d, dict) else None
            if mm is None:
                mm = d.get("rainfall_mm") if isinstance(d, dict) else None
            if mm is not None:
                next7_sum += float(mm)
    except Exception:
        pass

    # If recent rainfall is low and upcoming week is dry vs crop heuristic, advise irrigation
    low_recent = (recent is None) or (float(recent) < 2.0)
    low_week = next7_sum < h["weekly_rain_mm"][0]
    if low_recent and low_week:
        recs.append("No significant rainfall expected. Plan supplemental irrigation to maintain optimal soil moisture.")

    # Soil health score
    sh = eng.get("soil_health_score")
    if sh is not None and isinstance(sh, (int, float)) and sh < 0.35:
        recs.append("Soil health score is low. Consider soil testing and integrated nutrient management next season.")

    if not recs:
        recs.append("Conditions look acceptable. Continue routine crop scouting and balanced nutrient management.")
    return recs

def prepare_features_from_db(db, district: str, crop: str, season: Optional[str], variety: Optional[str]) -> Dict[str, Any]:
    # latest soil
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id FROM districts WHERE district_name = %s", (district,))
    drow = cur.fetchone()
    if not drow:
        raise HTTPException(status_code=404, detail=f"District not found: {district}")
    district_id = drow["id"]

    cur.execute(
        """
        SELECT * FROM soil_data
        WHERE district_id = %s
        ORDER BY sample_date DESC
        LIMIT 1
        """,
        (district_id,),
    )
    soil = cur.fetchone() or {}

    # latest weather (optional in features; training used historical fields)
    cur.execute(
        """
        SELECT * FROM weather_cache
        WHERE district_id = %s
        ORDER BY date DESC
        LIMIT 1
        """,
        (district_id,),
    )
    weather = cur.fetchone() or {}
    cur.close()

    # Build a single-row DataFrame with training feature columns
    load_artifacts()
    feature_cols = MODEL_CACHE["feature_columns"]
    encoders = MODEL_CACHE["encoders"]
    imputer = MODEL_CACHE["imputer"]

    # Assemble base values
    row = {}
    row["hist_rainfall_mm"] = weather.get("predicted_rainfall")
    row["hist_avg_temp_c"] = weather.get("avg_temperature")
    row["area_hectares"] = 1.0
    row["ph_level"] = soil.get("ph_level")
    row["organic_carbon_percent"] = soil.get("organic_carbon_percent")
    row["nitrogen_mg_per_kg"] = soil.get("nitrogen_mg_per_kg")
    row["phosphorus_mg_per_kg"] = soil.get("phosphorus_mg_per_kg")
    row["potassium_mg_per_kg"] = soil.get("potassium_mg_per_kg")

    # Engineered features
    n = row["nitrogen_mg_per_kg"]
    p = row["phosphorus_mg_per_kg"]
    k = row["potassium_mg_per_kg"]
    oc = row["organic_carbon_percent"]
    row["soil_health_score"] = _compute_soil_health(n, p, k, oc)
    try:
        row["npk_sum"] = (float(n or 0) + float(p or 0) + float(k or 0))
    except Exception:
        row["npk_sum"] = np.nan
    row["ratio_n_p"] = _safe_ratio(n, p)
    row["ratio_k_p"] = _safe_ratio(k, p)
    row["temperature_range"] = 0.0

    # Categorical encodings
    dname = district
    ctype = crop
    sname = season or "Kharif"
    vname = variety or "unknown"
    row["district_name_le"] = _label_encode(encoders.get("district_name"), dname) if encoders.get("district_name") else 0
    row["crop_type_le"] = _label_encode(encoders.get("crop_type"), ctype) if encoders.get("crop_type") else 0
    row["season_le"] = _label_encode(encoders.get("season"), sname) if encoders.get("season") else 0
    row["variety_le"] = _label_encode(encoders.get("variety"), vname) if encoders.get("variety") else 0

    # Create DataFrame in the exact column order expected
    X = pd.DataFrame([{col: row.get(col, np.nan) for col in feature_cols}])

    # Impute
    X[feature_cols] = imputer.transform(X[feature_cols])

    return {
        "district_id": district_id,
        "soil": soil,
        "weather": weather,
        "features": X,
        "engineering": {
            "soil_health_score": row["soil_health_score"],
            "npk_sum": row["npk_sum"],
            "ratio_n_p": row["ratio_n_p"],
            "ratio_k_p": row["ratio_k_p"],
        },
    }

# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "app": "Krushi-Mitra AI (FastAPI)"}


# Add this at the top of your file with other imports
import logging
from pprint import pformat

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.options("/register", response_class=Response)
async def register_options(request: Request):
    logger.debug("\n=== OPTIONS Request ===")
    logger.debug(f"Headers: {pformat(dict(request.headers))}")
    
    # Handle preflight request
    response = Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )
    
    logger.debug("\n=== OPTIONS Response Headers ===")
    for k, v in response.headers.items():
        logger.debug(f"{k}: {v}")
        
    return response

# ------------------------------------------------------------
# Startup Event
# ------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Load the plant disease model on startup."""
    print("Starting Krushi-Mitra AI server...")
    print("Loading Plant Doctor AI model...")
    
    # Load the plant disease model
    if load_plant_disease_model():
        print("Plant Doctor AI model loaded successfully!")
    else:
        print("Plant Doctor AI model could not be loaded. Feature will be disabled.")
    
    print("Server startup complete!")

# ------------------------------------------------------------
# Plant Doctor AI Functions
# ------------------------------------------------------------

# Global variable to store the loaded model
plant_disease_model = None
plant_disease_metadata = None

def load_plant_disease_model():
    """Load the plant disease classification model and metadata."""
    global plant_disease_model, plant_disease_metadata
    
    try:
        # Load model
        model_path = "models/plant_disease/plant_disease_model.h5"
        if os.path.exists(model_path):
            plant_disease_model = keras.models.load_model(model_path)
            print(f"Plant disease model loaded from {model_path}")
        else:
            print(f"Model file not found at {model_path}")
            return False
        
        # Load metadata
        metadata_path = "models/plant_disease/plant_disease_metadata.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                plant_disease_metadata = json.load(f)
            print(f"Plant disease metadata loaded from {metadata_path}")
        else:
            print(f"Metadata file not found at {metadata_path}")
            return False
        
        return True
    except Exception as e:
        print(f"Error loading plant disease model: {e}")
        return False

def preprocess_image_for_model(image_bytes: bytes) -> np.ndarray:
    """Preprocess image for plant disease model inference."""
    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize to model input size (224x224)
        image = image.resize((224, 224))
        
        # Convert to numpy array and normalize to [0, 1]
        image_array = np.array(image) / 255.0
        
        # Add batch dimension
        image_array = np.expand_dims(image_array, axis=0)
        
        return image_array
    except Exception as e:
        print(f"Error preprocessing image: {e}")
        raise HTTPException(status_code=400, detail=f"Image preprocessing failed: {str(e)}")

def predict_plant_disease(image_bytes: bytes) -> Dict[str, Any]:
    """Predict plant disease from image bytes."""
    global plant_disease_model, plant_disease_metadata
    
    if plant_disease_model is None or plant_disease_metadata is None:
        raise HTTPException(status_code=500, detail="Plant disease model not loaded")
    
    try:
        # Preprocess image
        processed_image = preprocess_image_for_model(image_bytes)
        
        # Make prediction
        prediction = plant_disease_model.predict(processed_image, verbose=0)
        
        # Get top prediction
        predicted_class_idx = np.argmax(prediction[0])
        confidence = prediction[0][predicted_class_idx]
        
        # Get disease name from metadata
        disease_classes = plant_disease_metadata.get("classes", [])
        if predicted_class_idx < len(disease_classes):
            predicted_disease = disease_classes[predicted_class_idx]
        else:
            predicted_disease = "Unknown Disease"
        
        # Get top 3 predictions for additional context
        top_3_indices = np.argsort(prediction[0])[-3:][::-1]
        top_3_predictions = []
        for idx in top_3_indices:
            if idx < len(disease_classes):
                top_3_predictions.append({
                    "disease": disease_classes[idx],
                    "confidence": float(prediction[0][idx]),
                    "rank": len(top_3_predictions) + 1
                })
        
        return {
            "disease": predicted_disease,
            "confidence": float(confidence),
            "class_index": int(predicted_class_idx),
            "top_predictions": top_3_predictions,
            "model_info": {
                "architecture": plant_disease_metadata.get("architecture", "Unknown"),
                "version": plant_disease_metadata.get("version", "1.0.0"),
                "total_classes": len(disease_classes)
            }
        }
    except Exception as e:
        print(f"Error predicting plant disease: {e}")
        raise HTTPException(status_code=500, detail=f"Disease prediction failed: {str(e)}")

def validate_image_file(file: UploadFile) -> bool:
    """Validate uploaded image file."""
    # Check file size (max 10MB)
    if hasattr(file, 'size') and file.size > 10 * 1024 * 1024:
        return False
    
    # Check file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if file.content_type not in allowed_types:
        return False
    
    return True

@app.post("/register")
async def register(body: RegisterBody, request: Request, response: Response, db=Depends(get_db)):
    try:
        logger.debug("\n=== POST /register Request ===")
        logger.debug(f"Request headers: {pformat(dict(request.headers))}")
        logger.debug(f"Request body: {body.dict()}")

        # Set CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Expose-Headers": "*"
        }
        
        for key, value in cors_headers.items():
            response.headers[key] = value
        
        username = body.username.strip()
        email = str(body.email).lower().strip()
        password = body.password

        logger.debug(f"\n=== Processing Registration ===")
        logger.debug(f"Username: {username}")
        logger.debug(f"Email: {email}")
        logger.debug(f"Password: {'*' * len(password) if password else 'None'}")

        if not username or not email or not password:
            error_msg = "All fields are required"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        logger.debug("Hashing password...")
        hashed_password = hash_password(password)
        logger.debug("Password hashed successfully")

        cursor = db.cursor(dictionary=True)
        try:
            logger.debug("Executing database query...")
            # Ensure users table exists (idempotent)
            ensure_users_table(db)
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)",
                (username, email, hashed_password),
            )
            db.commit()
            logger.debug("User registered successfully in database")
            
            # Get the new user's ID
            cursor.execute("SELECT LAST_INSERT_ID() as user_id")
            user_id = cursor.fetchone()['user_id']
            logger.debug(f"New user ID: {user_id}")
            
        except mysql.connector.Error as err:
            error_msg = str(err)
            logger.error(f"Database error: {error_msg}")
            if getattr(err, 'errno', None) == 1062:
                error_msg = "Username or email already exists"
                logger.error(error_msg)
                raise HTTPException(status_code=409, detail=error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        finally:
            cursor.close()

        success_msg = "User registered successfully"
        logger.info(f"{success_msg}: {username} ({email})")
        
        return {
            "status": "success",
            "message": success_msg,
            "user_id": user_id
        }
        
    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}")
        for key, value in cors_headers.items():
            response.headers[key] = value
        raise he
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        for key, value in cors_headers.items():
            response.headers[key] = value
        raise HTTPException(status_code=500, detail=error_msg)
    
    finally:
        logger.debug("\n=== End of Request ===\n")


@app.post("/login")
def login(body: LoginBody, request: Request, response: Response, db=Depends(get_db)):
    try:
        email = str(body.email).lower().strip()
        password = body.password

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")

        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        finally:
            cursor.close()

        # DEBUG: Print fetched credentials state (do NOT keep in production)
        try:
            print(f"[DEBUG /login] Fetched user: id={user.get('id') if user else None}, username={user.get('username') if user else None}, email={email}")
            print(f"[DEBUG /login] Stored hashed_password: {(user.get('hashed_password') or user.get('password')) if user else None}")
            print(f"[DEBUG /login] Provided password: {password}")
        except Exception as _e:
            print(f"[DEBUG /login] Debug print error: {_e}")

        verified = False
        if user:
            try:
                verified = verify_password(password, user.get("hashed_password") or user.get("password"))
            finally:
                pass
        print(f"[DEBUG /login] Password verification: {'PASSED' if verified else 'FAILED'}")

        if not user or not verified:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Session (Starlette SessionMiddleware managed cookie)
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]

        # Additionally set a signed, HttpOnly cookie for integrity
        token = COOKIE_SERIALIZER.dumps({"uid": user["id"], "ts": int(time.time())})
        resp = JSONResponse(
            {
                "message": "Login successful",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                },
            }
        )
        resp.set_cookie(
            key="session_id",
            value=token,
            max_age=SEVEN_DAYS_SECONDS,
            httponly=True,
            samesite="lax",
            secure=False,  # set True in production over HTTPS
        )
        return resp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}


@app.get("/debug-session")
def debug_session(request: Request):
    """Temporary debug endpoint to inspect current session contents."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "No user_id in session", "session": dict(request.session)}
    
    return dict(request.session)


@app.get("/debug-database")
def debug_database(request: Request, db=Depends(get_db)):
    """Debug endpoint to check database state."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Not authenticated"}
    
    try:
        cursor = db.cursor(dictionary=True)
        
        # Check if predictions table exists
        cursor.execute("SHOW TABLES LIKE 'predictions'")
        predictions_table = cursor.fetchone()
        
        # Check farms for this user
        cursor.execute("SELECT id, farm_name, created_at FROM farms WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        farms = cursor.fetchall()
        
        # Check predictions for this user
        if farms:
            farm_ids = [str(farm['id']) for farm in farms]
            cursor.execute(f"SELECT id, farm_id, created_at FROM predictions WHERE farm_id IN ({','.join(farm_ids)}) ORDER BY created_at DESC")
            predictions = cursor.fetchall()
        else:
            predictions = []
        
        # Check predictions table structure
        cursor.execute("DESCRIBE predictions")
        table_structure = cursor.fetchall()
        
        cursor.close()
        
        return {
            "user_id": user_id,
            "predictions_table_exists": bool(predictions_table),
            "farms_count": len(farms),
            "farms": farms,
            "predictions_count": len(predictions),
            "predictions": predictions,
            "predictions_table_structure": table_structure
        }
        
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/debug-auth")
def debug_auth(request: Request, db=Depends(get_db)):
    """Return request header snapshot, client info, session, and computed auth status."""
    # Header snapshot (selected)
    headers = {
        "host": request.headers.get("host"),
        "origin": request.headers.get("origin"),
        "referer": request.headers.get("referer"),
        "user-agent": request.headers.get("user-agent"),
        "cookie": request.headers.get("cookie"),
        "authorization": request.headers.get("authorization"),
    }
    client = {"ip": getattr(request.client, "host", None), "port": getattr(request.client, "port", None)}
    session_obj = dict(request.session)

    # Compute auth status like /check-auth
    user_id = session_obj.get("user_id")
    has_farm = False
    if user_id:
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM farms WHERE user_id = %s LIMIT 1", (user_id,))
            has_farm = bool(cursor.fetchone())
        except Exception:
            has_farm = False
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    payload = {
        "request": headers,
        "client": client,
        "session": session_obj,
        "auth": {
            "authenticated": bool(user_id),
            "has_farm_setup": has_farm,
            "user": {"id": user_id, "username": session_obj.get("username")} if user_id else None,
        },
    }
    # Also print to server logs for quick inspection
    print("\n[DEBUG /debug-auth] Incoming:\n" + pformat(payload) + "\n")
    return JSONResponse(content=payload)


@app.get("/check-auth")
def check_auth(request: Request, db=Depends(get_db)):
    user_id = request.session.get("user_id")
    print(f"[DEBUG] check-auth: user_id from session = {user_id}")
    print(f"[DEBUG] check-auth: full session = {dict(request.session)}")
    if user_id:
        # Determine if user has farm setup
        has_farm = False
        cursor = db.cursor(dictionary=True)
        try:
            # Support both schema variants
            cursor.execute("SELECT id FROM farms WHERE user_id = %s LIMIT 1", (user_id,))
            farm = cursor.fetchone()
            has_farm = bool(farm)
        except Exception:
            has_farm = False
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        return {
            "authenticated": True,
            "has_farm_setup": has_farm,
            "user": {
                "id": user_id,
                "username": request.session.get("username"),
            },
        }
    print("[DEBUG] check-auth: No user_id in session - returning false")
    return {"authenticated": False, "has_farm_setup": False}


@app.post("/predict")
def predict_deprecated():
    return JSONResponse(
        status_code=410,
        content={
            "message": "This endpoint is deprecated. Please use the new recommendation endpoints in the upcoming release.",
        },
    )


@app.get("/my-farm")
def get_my_farm(request: Request, db=Depends(get_db)):
    """Check if the current user has an associated farm.
    
    Returns:
        {"has_farm": bool} - True if the user has a farm, False otherwise
    """
    # Check if user is authenticated
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    user_id = request.session["user_id"]
    
    # Query the farms table for any farm associated with this user
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id FROM farms WHERE user_id = %s LIMIT 1", 
            (user_id,)
        )
        farm = cursor.fetchone()
        return {"has_farm": farm is not None}
    except mysql.connector.Error as err:
        # If the farms table doesn't exist yet, return False
        if err.errno == 1146:  # Table doesn't exist
            return {"has_farm": False}
        raise HTTPException(status_code=500, detail=f"Database error: {str(err)}")
    finally:
        cursor.close()

@app.post("/my-farm")
def save_farm(farm_data: FarmData, request: Request, db=Depends(get_db)):
    """Save farm data for the logged-in user and create calendar events."""
    logger.info(f"--- Starting /my-farm save for user_id: {request.session.get('user_id')} ---")
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            logger.error("User not authenticated.")
            raise HTTPException(status_code=401, detail="Authentication required")

        farm_name = farm_data.farm_name.strip()
        boundary_coords = farm_data.boundary_coordinates
        logger.info(f"Received farm_name: '{farm_name}'")
        logger.info(f"Received boundary_coordinates with {len(boundary_coords) if boundary_coords else 0} points.")

        if not farm_name:
            logger.error("Validation failed: Farm name is required.")
            raise HTTPException(status_code=400, detail="Farm name is required")

        if not boundary_coords or len(boundary_coords) < 3:
            logger.error(f"Validation failed: Received {len(boundary_coords) if boundary_coords else 0} points, require at least 3.")
            raise HTTPException(status_code=400, detail="At least 3 boundary points are required")

        boundary_json = json.dumps(boundary_coords)
        logger.info(f"Serialized boundary to JSON: {boundary_json[:100]}...")

        ensure_farms_table(db)
        cursor = db.cursor()
        try:
            cursor.execute("SELECT id FROM farms WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
            existing_farm = cursor.fetchone()

            if existing_farm:
                farm_id = existing_farm[0]
                logger.info(f"Updating existing farm for user_id: {user_id}, farm_id: {farm_id}")
                # Use the farm_id to ensure we update the correct row, even if a user has multiple.
                cursor.execute(
                    "UPDATE farms SET farm_name = %s, plot_boundary = %s, updated_at = NOW() WHERE id = %s",
                    (farm_name, boundary_json, farm_id)
                )
                logger.info("Executed UPDATE on farm.")
            else:
                logger.info(f"Inserting new farm for user_id: {user_id}")
                cursor.execute(
                    "INSERT INTO farms (user_id, farm_name, plot_boundary) VALUES (%s, %s, %s)",
                    (user_id, farm_name, boundary_json)
                )
                farm_id = cursor.lastrowid
                logger.info(f"Executed INSERT. New farm_id: {farm_id}")

            try:
                db.commit()
                logger.info("Database commit successful.")
            except Exception as e:
                logger.error(f"DATABASE COMMIT FAILED: {e}")
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to save data to the database.")

            # Read-after-write verification
            read_back_points = 0
            try:
                verified_farm = get_farm_data(int(user_id), db)
                if verified_farm:
                    read_back_points = len(verified_farm.get("boundary_coordinates") or [])
                logger.info(f"Read-after-write check: found {read_back_points} points.")
            except Exception as e:
                logger.error(f"Read-after-write check failed: {e}")

            create_farm_calendar_events(farm_id, "Paddy", "Kharif", db)

            username = request.session.get("username")
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "Farm saved successfully",
                    "farm_id": int(farm_id),
                    "boundary_points": len(boundary_coords or []),
                    "read_back_points": read_back_points,
                    "has_farm_setup": read_back_points >= 3,
                    "authenticated": True,
                    "user": {
                        "id": int(user_id),
                        "username": username,
                    },
                }
            )
        finally:
            cursor.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict-advanced")
def predict_advanced(body: PredictAdvancedBody, request: Request, db=Depends(get_db)):
    try:
        load_artifacts()
        prepared = prepare_features_from_db(db, body.district.strip(), body.crop.strip(), body.season, body.variety)
        X = prepared["features"]
        model = MODEL_CACHE["model"]
        y_pred = float(model.predict(X)[0])
        
        # Get farm data if user is logged in
        farm_data = None
        farm_area_hectares = None
        farm_center = None
        user_id = request.session.get("user_id")
        
        if user_id:
            farm_data = get_farm_data(user_id, db)
            if farm_data:
                farm_area_hectares = calculate_farm_area(farm_data["boundary_coordinates"])
                farm_center = get_farm_center(farm_data["boundary_coordinates"])
                
                # Adjust prediction based on farm area if available
                if farm_area_hectares > 0:
                    # Scale prediction based on farm size (larger farms might have different yields)
                    area_factor = min(1.2, max(0.8, farm_area_hectares / 5.0))  # Normalize around 5 hectares
                    y_pred = y_pred * area_factor

        # Try to parse forecast and warnings if present on weather row
        seven_day_forecast = None
        active_warnings = None
        try:
            raw_forecast = prepared["weather"].get("seven_day_forecast") if prepared["weather"] else None
            if isinstance(raw_forecast, str):
                seven_day_forecast = json.loads(raw_forecast)
            elif isinstance(raw_forecast, (list, dict)):
                seven_day_forecast = raw_forecast
        except Exception:
            seven_day_forecast = None
        try:
            raw_warn = prepared["weather"].get("active_warnings") or prepared["weather"].get("warnings") if prepared["weather"] else None
            if isinstance(raw_warn, str):
                active_warnings = json.loads(raw_warn)
            elif isinstance(raw_warn, (list, dict)):
                active_warnings = raw_warn
        except Exception:
            active_warnings = None

        resp = {
            "district": body.district,
            "crop": body.crop,
            "season": body.season or "Kharif",
            "variety": body.variety or "unknown",
            "predicted_yield_kg_per_hectare": round(y_pred, 2),
            "engineered": {
                "soil_health_score": _none_if_nan(prepared["engineering"].get("soil_health_score")),
                "npk_sum": _none_if_nan(prepared["engineering"].get("npk_sum")),
                "ratio_n_p": _none_if_nan(prepared["engineering"].get("ratio_n_p")),
                "ratio_k_p": _none_if_nan(prepared["engineering"].get("ratio_k_p")),
            },
            "used_data": {
                "soil": prepared["soil"],
                "weather": prepared["weather"],
            },
            "seven_day_forecast": seven_day_forecast,
            "active_warnings": active_warnings,
            "recommendations": generate_recommendations(body.crop, prepared, seven_day_forecast),
        }
        
        # Add farm-specific data to response
        if farm_data and user_id:
            resp["farm_data"] = {
                "farm_name": farm_data["farm_name"],
                "farm_area_hectares": farm_area_hectares,
                "farm_center": {
                    "latitude": farm_center[0],
                    "longitude": farm_center[1]
                },
                "personalized": True
            }
        else:
            resp["farm_data"] = {
                "personalized": False,
                "message": "No farm data found. Create a farm profile for personalized predictions."
            }
        
        # Save prediction to user_predictions even if not logged in (user_id can be NULL)
        try:
            cursor = db.cursor()
            create_user_predictions_table(db)  # Ensure table exists

            additional_data = {
                "engineered": resp.get("engineered", {}),
                "used_data": resp.get("used_data", {}),
                "seven_day_forecast": resp.get("seven_day_forecast"),
                "active_warnings": resp.get("active_warnings"),
                "recommendations": resp.get("recommendations", []),
                "farm_data": resp.get("farm_data", {}),
                "prediction_timestamp": datetime.now().isoformat()
            }

            print("[DEBUG] Saving prediction to user_predictions:")
            print(f"  - user_id: {user_id}")
            print(f"  - crop: {resp.get('crop', 'Unknown')}")
            print(f"  - district: {resp.get('district', 'Unknown')}")
            print(f"  - predicted_yield: {resp.get('predicted_yield_kg_per_hectare', 0)}")

            cursor.execute(
                """
                INSERT INTO user_predictions 
                (user_id, crop, district, season, variety, predicted_yield_kg_per_hectare, prediction_date, additional_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,  # can be None
                    resp.get("crop", "Unknown"),
                    resp.get("district", "Unknown"),
                    resp.get("season", "Kharif"),
                    resp.get("variety", "Unknown"),
                    resp.get("predicted_yield_kg_per_hectare", 0),
                    date.today(),
                    json.dumps(jsonable_encoder(additional_data), default=str),
                ),
            )
            new_id = cursor.lastrowid
            print(f"[DEBUG] Inserted user_predictions row id: {new_id}")
            db.commit()

            # Verify insert
            if user_id:
                cursor.execute("SELECT COUNT(*) as count FROM user_predictions WHERE user_id = %s", (user_id,))
                count_result = cursor.fetchone()
                print(f"[DEBUG] Verification: {count_result[0] if count_result else 0} total predictions for user_id: {user_id}")
            else:
                cursor.execute("SELECT COUNT(*) as count FROM user_predictions WHERE user_id IS NULL")
                count_result = cursor.fetchone()
                print(f"[DEBUG] Verification: {count_result[0] if count_result else 0} total predictions for anonymous users")

            cursor.close()
            print("Prediction saved to user_predictions")
            # Extra debug: read back the inserted row
            try:
                c2 = db.cursor(dictionary=True)
                c2.execute("SELECT * FROM user_predictions WHERE id = %s", (new_id,))
                row = c2.fetchone()
                print(f"[DEBUG] Inserted row readback: {row}")
                c2.close()
            except Exception as rb_e:
                print(f"[DEBUG] Readback failed: {rb_e}")

        except Exception as e:
            print(f"Failed to save prediction: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        # Ensure no NaN/inf sneak into JSON
        return JSONResponse(content=jsonable_encoder(resp))
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Model artifacts missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/farms")
async def create_farm(
    request: Request,
    farm_data: dict,
    db=Depends(get_db)
):
    """
    Create or update a farm for the current user.
    
    Request body should contain:
    - name: str (required) - The name of the farm
    - boundary: dict (optional) - GeoJSON boundary data
    
    Returns:
        {
            "status": "success",
            "message": "Farm created/updated successfully",
            "farm_id": int
        }
    """
    # Check if user is authenticated
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = request.session["user_id"]
    farm_name = farm_data.get("name")
    boundary = farm_data.get("boundary")
    
    # Validate required fields
    if not farm_name:
        raise HTTPException(status_code=400, detail="Farm name is required")
    
    cursor = db.cursor(dictionary=True)
    
    try:
        # Check if farm already exists for this user
        cursor.execute(
            "SELECT id FROM farms WHERE user_id = %s",
            (user_id,)
        )
        existing_farm = cursor.fetchone()
        
        if existing_farm:
            # Update existing farm
            cursor.execute(
                """
                UPDATE farms 
                SET name = %s, boundary = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (
                    farm_name,
                    json.dumps(boundary) if boundary else None,
                    existing_farm['id'],
                    user_id
                )
            )
            farm_id = existing_farm['id']
            message = "Farm updated successfully"
        else:
            # Create new farm
            cursor.execute(
                """
                INSERT INTO farms (user_id, name, boundary)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    farm_name,
                    json.dumps(boundary) if boundary else None
                )
            )
            farm_id = cursor.lastrowid
            message = "Farm created successfully"
            
            # Create calendar events for new farm
            create_farm_calendar_events(farm_id, "Paddy", "Kharif", db)
        
        db.commit()
        
        return {
            "status": "success",
            "message": message,
            "farm_id": farm_id
        }
        
    except mysql.connector.Error as err:
        db.rollback()
        # Handle specific database errors
        if err.errno == 1146:  # Table doesn't exist
            # Create the farms table
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS farms (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        boundary JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        UNIQUE KEY unique_user_farm (user_id, name)
                    )
                """)
                db.commit()
                
                # Retry the operation
                return await create_farm(request, farm_data, db)
                
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to create farms table: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Database error: {str(err)}")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
        
    finally:
        cursor.close()



@app.get("/my-farm/satellite-ndvi")
def get_farm_satellite_ndvi(request: Request, db=Depends(get_db)):
    """
    Get satellite NDVI analysis for the logged-in user's farm.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get farm data with debug
    farm_data = get_farm_data(user_id, db)
    if not farm_data:
        print(f"[satellite-ndvi] No farm data for user_id={user_id}")
        raise HTTPException(status_code=404, detail="No farm data found. Please complete farm setup first.")
    if not farm_data.get("boundary_coordinates"):
        print(f"[satellite-ndvi] Empty boundary for user_id={user_id}, farm={farm_data.get('farm_name')}")
        raise HTTPException(status_code=400, detail="Farm boundary is empty. Please draw your farm boundary on the map.")
    
    # Attempt to get real satellite data
    access_token = get_sentinel_hub_token()
    if access_token:
        ndvi_data = get_satellite_ndvi(farm_data["boundary_coordinates"], access_token)
        # If we successfully get real data, return it
        if ndvi_data:
            return {
                "farm_name": farm_data["farm_name"],
                "ndvi_data": ndvi_data
            }

    # --- Fallback to Mock Data ---
    # If we've reached this point, either the token failed or the NDVI data fetch failed.
    # We will now return mock data with a more informative message.
    try:
        lats = [coord[0] for coord in farm_data["boundary_coordinates"]]
        lngs = [coord[1] for coord in farm_data["boundary_coordinates"]]
    except Exception as e:
        print(f"[satellite-ndvi] Invalid boundary format for user_id={user_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid farm boundary format. Please re-save your farm boundary.")

    # Determine the correct reason for using mock data
    if not SENTINEL_HUB_CLIENT_ID or not SENTINEL_HUB_CLIENT_SECRET:
        message = "Satellite analysis powered by AI algorithms"
    else:
        message = "Satellite analysis powered by AI algorithms"

    return {
        "farm_name": farm_data["farm_name"],
        "ndvi_data": {
            "bounds": {
                "min_lat": min(lats),
                "max_lat": max(lats),
                "min_lng": min(lngs),
                "max_lng": max(lngs)
            },
            "resolution": "10m",
            "cloud_coverage": "< 20%",
            "acquisition_date": "2024-01-15",
            "ndvi_stats": {
                "mean": 0.65,
                "min": 0.12,
                "max": 0.89,
                "std": 0.15
            },
            "health_score": 0.72,
            "status": "mock_data",
            "message": message
        }
    }


@app.get("/test/calendar-debug")
def test_calendar_debug(request: Request, db=Depends(get_db)):
    """Debug endpoint to test calendar functionality."""
    try:
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        
        debug_info = {
            "session_info": {
                "user_id": user_id,
                "username": username,
                "session_keys": list(request.session.keys())
            },
            "database_status": "connected",
            "calendar_table_exists": False,
            "farms_for_user": [],
            "sample_events": []
        }
        
        if user_id:
            cursor = db.cursor(dictionary=True)
            try:
                # Check if calendar table exists
                cursor.execute("SHOW TABLES LIKE 'farm_calendar_events'")
                table_exists = cursor.fetchone()
                debug_info["calendar_table_exists"] = bool(table_exists)
                
                # Get farms for user
                cursor.execute("SELECT id, farm_name FROM farms WHERE user_id = %s", (user_id,))
                farms = cursor.fetchall()
                debug_info["farms_for_user"] = farms
                
                if farms:
                    farm_id = farms[0]["id"]
                    # Get events for first farm
                    cursor.execute("SELECT * FROM farm_calendar_events WHERE farm_id = %s LIMIT 5", (farm_id,))
                    events = cursor.fetchall()
                    debug_info["sample_events"] = events
                    
            finally:
                cursor.close()
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "session_info": {
                "user_id": request.session.get("user_id"),
                "username": request.session.get("username")
            }
        }


@app.get("/my-farm/calendar")
def get_farm_calendar(request: Request, db=Depends(get_db)):
    """Get all calendar events for the authenticated user's farm."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {
                "success": False,
                "error": "Authentication required",
                "events": [],
                "message": "Please log in to view your calendar"
            }
        
        # Get farm ID for the user
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, farm_name FROM farms WHERE user_id = %s", (user_id,))
            farm = cursor.fetchone()
            if not farm:
                return {
                    "success": False,
                    "error": "No farm found",
                    "events": [],
                    "message": "Please complete farm setup first to view your calendar"
                }
            
            farm_id = farm["id"]
            
            # Ensure calendar events table exists
            create_calendar_events_table(db)
            
            # Get all calendar events for this farm
            events = get_farm_calendar_events(farm_id, db)
            
            return {
                "success": True,
                "events": events,
                "farm_id": farm_id,
                "farm_name": farm.get("farm_name", "Unknown"),
                "total_events": len(events),
                "message": f"Found {len(events)} calendar events"
            }
            
        finally:
            cursor.close()
            
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return {
            "success": False,
            "error": "Server error",
            "events": [],
            "message": f"Failed to fetch calendar events: {str(e)}"
        }


@app.post("/my-farm/calendar/entry")
def add_calendar_entry(event_data: CalendarEventBody, request: Request, db=Depends(get_db)):
    """Add a new diary entry to the farm calendar."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate event type
        if event_data.event_type not in ["AI_Suggestion", "Farmer_Log"]:
            raise HTTPException(status_code=400, detail="Event type must be 'AI_Suggestion' or 'Farmer_Log'")
        
        # Get farm ID for the user
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM farms WHERE user_id = %s", (user_id,))
            farm = cursor.fetchone()
            if not farm:
                raise HTTPException(status_code=404, detail="No farm found. Please complete farm setup first.")
            
            farm_id = farm["id"]
            
            # Ensure calendar events table exists
            create_calendar_events_table(db)
            
            # Add the calendar event
            event_id = add_calendar_event(farm_id, event_data, db)
            
            return {
                "message": "Calendar entry added successfully",
                "event_id": event_id,
                "farm_id": farm_id,
                "event": {
                    "event_title": event_data.event_title,
                    "event_date": event_data.event_date.isoformat(),
                    "event_type": event_data.event_type,
                    "details": event_data.details
                }
            }
            
        finally:
            cursor.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/my-farm/latest-prediction")
def get_latest_prediction(request: Request, db=Depends(get_db)):
    """Get the latest prediction for the authenticated user (no farm required)."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {
                "success": False,
                "error": "Authentication required",
                "prediction": None,
                "message": "Please log in to view your predictions"
            }
        
        cursor = db.cursor(dictionary=True)
        try:
            # Ensure user predictions table exists
            create_user_predictions_table(db)
            
            # Get the latest prediction for this user
            cursor.execute("""
                SELECT 
                    id, user_id, crop, district, season, variety,
                    predicted_yield_kg_per_hectare, prediction_date,
                    prediction_timestamp, additional_data
                FROM user_predictions
                WHERE user_id = %s
                ORDER BY prediction_timestamp DESC
                LIMIT 1
            """, (user_id,))
            
            prediction = cursor.fetchone()

            is_anonymous_fallback = False
            if not prediction:
                # Fallback: if user has no saved predictions yet, try latest anonymous
                cursor.execute(
                    """
                    SELECT 
                        id, NULL as user_id, crop, district, season, variety,
                        predicted_yield_kg_per_hectare, prediction_date,
                        prediction_timestamp, additional_data
                    FROM user_predictions
                    WHERE user_id IS NULL
                    ORDER BY prediction_timestamp DESC
                    LIMIT 1
                    """
                )
                prediction = cursor.fetchone()
                is_anonymous_fallback = prediction is not None

            if not prediction:
                return {
                    "success": True,
                    "prediction": None,
                    "user_id": user_id,
                    "message": "No predictions found. Make your first prediction!"
                }
            
            # Parse additional data if it exists
            additional_data = {}
            if prediction["additional_data"]:
                try:
                    additional_data = json.loads(prediction["additional_data"])
                except:
                    additional_data = {}
            
            # Format the response
            result = {
                "success": True,
                "prediction": {
                    "id": prediction["id"],
                    "crop": prediction["crop"],
                    "district": prediction["district"],
                    "season": prediction["season"],
                    "variety": prediction["variety"],
                    "predicted_yield_kg_per_hectare": float(prediction["predicted_yield_kg_per_hectare"]),
                    "prediction_date": prediction["prediction_date"].isoformat() if prediction["prediction_date"] else None,
                    "prediction_timestamp": prediction["prediction_timestamp"].isoformat() if prediction["prediction_timestamp"] else None,
                    **additional_data  # Include engineered features, recommendations, etc.
                },
                "user_id": user_id,
                "farm_id": None,
                "farm_name": None,
                "is_anonymous_fallback": is_anonymous_fallback,
                "message": f"Latest prediction for {prediction['crop']} in {prediction['district']}"
            }
            
            return result
            
        finally:
            cursor.close()
            
    except Exception as e:
        print(f"Error fetching latest prediction: {e}")
        return {
            "success": False,
            "error": "Server error",
            "prediction": None,
            "message": f"Failed to fetch latest prediction: {str(e)}"
        }


@app.get("/test/prediction-history-debug")
def test_prediction_history_debug(request: Request, db=Depends(get_db)):
    """Debug endpoint to test prediction history functionality."""
    try:
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        
        debug_info = {
            "session_info": {
                "user_id": user_id,
                "username": username,
                "authenticated": bool(user_id)
            },
            "database_status": "connected",
            "prediction_history_table_exists": False,
            "farms_for_user": [],
            "prediction_history_count": 0,
            "latest_prediction": None
        }
        
        if user_id:
            cursor = db.cursor(dictionary=True)
            try:
                # Check if prediction_history table exists
                cursor.execute("SHOW TABLES LIKE 'prediction_history'")
                table_exists = cursor.fetchone()
                debug_info["prediction_history_table_exists"] = bool(table_exists)
                
                # Get farms for user
                cursor.execute("SELECT id, farm_name, created_at FROM farms WHERE user_id = %s", (user_id,))
                farms = cursor.fetchall()
                debug_info["farms_for_user"] = farms
                
                if farms:
                    farm_ids = [str(farm["id"]) for farm in farms]
                    # Get prediction history count
                    cursor.execute(f"SELECT COUNT(*) as count FROM prediction_history WHERE farm_id IN ({','.join(farm_ids)})")
                    count_result = cursor.fetchone()
                    debug_info["prediction_history_count"] = count_result["count"] if count_result else 0
                    
                    # Get latest prediction
                    cursor.execute(f"""
                        SELECT crop, district, predicted_yield_kg_per_hectare, prediction_date, prediction_timestamp
                        FROM prediction_history 
                        WHERE farm_id IN ({','.join(farm_ids)})
                        ORDER BY prediction_timestamp DESC 
                        LIMIT 1
                    """)
                    latest = cursor.fetchone()
                    if latest:
                        debug_info["latest_prediction"] = {
                            "crop": latest["crop"],
                            "district": latest["district"],
                            "predicted_yield": float(latest["predicted_yield_kg_per_hectare"]),
                            "prediction_date": latest["prediction_date"].isoformat() if latest["prediction_date"] else None,
                            "prediction_timestamp": latest["prediction_timestamp"].isoformat() if latest["prediction_timestamp"] else None
                        }
                    
            finally:
                cursor.close()
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "session_info": {
                "user_id": request.session.get("user_id"),
                "username": request.session.get("username")
            }
        }


@app.get("/test/create-sample-prediction")
def create_sample_prediction(request: Request, db=Depends(get_db)):
    """Create a sample prediction for testing purposes."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Authentication required"}
        
        cursor = db.cursor(dictionary=True)
        try:
            # Get or create user's main farm
            cursor.execute("SELECT id FROM farms WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
            farm_result = cursor.fetchone()
            
            if farm_result:
                farm_id = farm_result["id"]
            else:
                # Create a main farm for the user
                cursor.execute(
                    "INSERT INTO farms (user_id, farm_name, plot_boundary) VALUES (%s, %s, %s)",
                    (user_id, "Test Farm", "[]")
                )
                db.commit()
                farm_id = cursor.lastrowid
            
            # Ensure prediction history table exists
            create_prediction_history_table(db)
            
            # Create sample prediction
            additional_data = {
                "engineered": {"soil_health_score": 0.75, "npk_sum": 150},
                "recommendations": ["Apply organic fertilizer", "Monitor soil moisture"],
                "farm_data": {"personalized": True}
            }
            
            cursor.execute("""
                INSERT INTO prediction_history 
                (farm_id, crop, district, season, variety, predicted_yield_kg_per_hectare, prediction_date, additional_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                farm_id,
                "Paddy",
                "Cuttack",
                "Kharif",
                "Swarna",
                3500.0,
                date.today(),
                json.dumps(additional_data)
            ))
            db.commit()
            
            return {
                "success": True,
                "message": "Sample prediction created successfully",
                "farm_id": farm_id,
                "prediction": {
                    "crop": "Paddy",
                    "district": "Cuttack",
                    "predicted_yield_kg_per_hectare": 3500.0
                }
            }
            
        finally:
            cursor.close()
            
    except Exception as e:
        print(f"Error creating sample prediction: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/test/full-debug")
def full_debug_info(request: Request, db=Depends(get_db)):
    """Complete debug information for prediction system."""
    try:
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        
        debug_info = {
            "session_info": {
                "user_id": user_id,
                "username": username,
                "authenticated": bool(user_id),
                "all_session_keys": list(request.session.keys())
            },
            "database_info": {
                "connection_status": "connected",
                "tables": {}
            },
            "user_data": {
                "farms": [],
                "prediction_history": [],
                "old_predictions": []
            }
        }
        
        cursor = db.cursor(dictionary=True)
        try:
            # Check table existence
            for table_name in ['farms', 'prediction_history', 'predictions']:
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                exists = cursor.fetchone()
                debug_info["database_info"]["tables"][table_name] = bool(exists)
            
            if user_id:
                # Get all farms for user
                cursor.execute("SELECT * FROM farms WHERE user_id = %s", (user_id,))
                debug_info["user_data"]["farms"] = cursor.fetchall()
                
                # Get all prediction history
                if debug_info["user_data"]["farms"]:
                    farm_ids = [str(farm["id"]) for farm in debug_info["user_data"]["farms"]]
                    cursor.execute(f"SELECT * FROM prediction_history WHERE farm_id IN ({','.join(farm_ids)})")
                    debug_info["user_data"]["prediction_history"] = cursor.fetchall()
                    
                    cursor.execute(f"SELECT * FROM predictions WHERE farm_id IN ({','.join(farm_ids)})")
                    debug_info["user_data"]["old_predictions"] = cursor.fetchall()
            
            # Get table row counts
            for table_name in ['farms', 'prediction_history', 'predictions']:
                if debug_info["database_info"]["tables"][table_name]:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    result = cursor.fetchone()
                    debug_info["database_info"]["tables"][f"{table_name}_count"] = result["count"] if result else 0
                    
        finally:
            cursor.close()
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "session_info": {
                "user_id": request.session.get("user_id"),
                "username": request.session.get("username")
            }
        }


@app.post("/diagnose-plant")
async def diagnose_plant_disease(
    request: Request,
    file: UploadFile = File(...)
):
    """Diagnose plant disease from uploaded image using AI model."""
    try:
        # Check authentication
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate image file
        if not validate_image_file(file):
            raise HTTPException(
                status_code=400, 
                detail="Invalid image file. Please upload a JPEG, PNG, or WebP image under 10MB."
            )
        
        # Load model if not already loaded
        if plant_disease_model is None or plant_disease_metadata is None:
            if not load_plant_disease_model():
                raise HTTPException(
                    status_code=500, 
                    detail="Plant disease model is not available. Please try again later."
                )
        
        # Read image bytes
        image_bytes = await file.read()
        
        # Validate image can be processed
        try:
            # Test if image can be opened
            test_image = Image.open(io.BytesIO(image_bytes))
            test_image.verify()  # Verify it's a valid image
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid image format: {str(e)}"
            )
        
        # Make prediction
        prediction_result = predict_plant_disease(image_bytes)
        
        # Add additional context based on prediction
        disease_info = {
            "disease": prediction_result["disease"],
            "confidence": prediction_result["confidence"],
            "severity": "High" if prediction_result["confidence"] > 0.8 else "Medium" if prediction_result["confidence"] > 0.6 else "Low",
            "recommendations": get_disease_recommendations(prediction_result["disease"]),
            "top_predictions": prediction_result["top_predictions"],
            "model_info": prediction_result["model_info"],
            "upload_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "size_bytes": len(image_bytes)
            }
        }
        
        return {
            "success": True,
            "message": "Plant disease diagnosis completed successfully",
            "diagnosis": disease_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in plant disease diagnosis: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {str(e)}")

def get_disease_recommendations(disease_name: str) -> Dict[str, Any]:
    """Get treatment recommendations for a specific disease."""
    
    # Disease-specific recommendations database
    recommendations_db = {
        "Healthy": {
            "status": "healthy",
            "message": "Your plant appears to be healthy!",
            "recommendations": [
                "Continue current care practices",
                "Monitor for any changes in appearance",
                "Maintain proper watering and nutrition"
            ],
            "prevention": [
                "Regular inspection of leaves",
                "Proper spacing between plants",
                "Good air circulation"
            ]
        },
        "Rice Blast": {
            "status": "disease",
            "message": "Rice Blast detected - immediate action required",
            "recommendations": [
                "Apply fungicide containing tricyclazole or azoxystrobin",
                "Reduce nitrogen fertilizer application",
                "Improve field drainage",
                "Remove infected plant debris"
            ],
            "prevention": [
                "Use resistant rice varieties",
                "Avoid excessive nitrogen fertilization",
                "Maintain proper water management",
                "Crop rotation with non-host plants"
            ]
        },
        "Rice Bacterial Blight": {
            "status": "disease",
            "message": "Bacterial Blight detected - treatment needed",
            "recommendations": [
                "Apply copper-based bactericides",
                "Reduce nitrogen fertilizer",
                "Improve field drainage",
                "Remove infected plant material"
            ],
            "prevention": [
                "Use certified disease-free seeds",
                "Avoid excessive nitrogen",
                "Proper water management",
                "Field sanitation"
            ]
        },
        "Tomato Early Blight": {
            "status": "disease",
            "message": "Early Blight detected in tomato",
            "recommendations": [
                "Apply fungicide containing chlorothalonil or mancozeb",
                "Remove infected leaves immediately",
                "Improve air circulation",
                "Avoid overhead watering"
            ],
            "prevention": [
                "Crop rotation",
                "Proper plant spacing",
                "Avoid wetting leaves",
                "Use resistant varieties"
            ]
        },
        "Wheat Rust": {
            "status": "disease",
            "message": "Wheat Rust detected - fungicide treatment needed",
            "recommendations": [
                "Apply fungicide containing tebuconazole or propiconazole",
                "Monitor weather conditions",
                "Consider early harvest if severe",
                "Remove volunteer wheat plants"
            ],
            "prevention": [
                "Plant resistant varieties",
                "Crop rotation",
                "Timely fungicide application",
                "Field sanitation"
            ]
        }
    }
    
    # Return specific recommendations or default
    if disease_name in recommendations_db:
        return recommendations_db[disease_name]
    else:
        return {
            "status": "unknown",
            "message": f"Disease '{disease_name}' detected - consult local agricultural expert",
            "recommendations": [
                "Consult with local agricultural extension officer",
                "Take sample to nearest plant pathology lab",
                "Monitor plant closely for changes",
                "Maintain good cultural practices"
            ],
            "prevention": [
                "Regular plant inspection",
                "Proper nutrition and watering",
                "Good field hygiene",
                "Use certified seeds"
            ]
        }

@app.post("/optimize-yield")
def optimize_yield(body: OptimizeYieldBody, request: Request, db=Depends(get_db)):
    """
    Optimize yield by applying interventions and running the model on modified soil data.
    
    Returns:
        Optimized yield prediction based on applied interventions
    """
    try:
        # Load model artifacts
        load_artifacts()
        
        # Get base soil data for the district
        prepared = prepare_features_from_db(db, body.district.strip(), body.crop.strip(), body.season, body.variety)
        base_soil = prepared["soil"]
        
        # Convert interventions to nutrient values
        total_nitrogen_addition = 0.0
        total_phosphorus_addition = 0.0
        total_potassium_addition = 0.0
        applied_interventions = []
        
        for intervention in body.interventions:
            nutrients = convert_intervention_to_nutrients(intervention)
            total_nitrogen_addition += nutrients["nitrogen_mg_kg"]
            total_phosphorus_addition += nutrients["phosphorus_mg_kg"]
            total_potassium_addition += nutrients["potassium_mg_kg"]
            
            applied_interventions.append({
                "fertilizer": intervention.fertilizer,
                "quantity": intervention.quantity,
                "unit": intervention.unit,
                "fertilizer_used": nutrients["fertilizer_used"],
                "nitrogen_added_mg_kg": nutrients["nitrogen_mg_kg"],
                "phosphorus_added_mg_kg": nutrients["phosphorus_mg_kg"],
                "potassium_added_mg_kg": nutrients["potassium_mg_kg"]
            })
        
        # Apply interventions to soil data (in-memory modification)
        modified_soil = base_soil.copy()
        modified_soil["n_mgkg"] = (modified_soil.get("n_mgkg", 0) or 0) + total_nitrogen_addition
        modified_soil["p_mgkg"] = (modified_soil.get("p_mgkg", 0) or 0) + total_phosphorus_addition
        modified_soil["k_mgkg"] = (modified_soil.get("k_mgkg", 0) or 0) + total_potassium_addition
        
        # Recalculate engineered features with modified soil data
        modified_engineering = {
            "soil_health_score": _calculate_soil_health_score(
                modified_soil.get("n_mgkg", 0) or 0,
                modified_soil.get("p_mgkg", 0) or 0,
                modified_soil.get("k_mgkg", 0) or 0,
                modified_soil.get("oc_percent", 0) or 0
            ),
            "npk_sum": (modified_soil.get("n_mgkg", 0) or 0) + 
                      (modified_soil.get("p_mgkg", 0) or 0) + 
                      (modified_soil.get("k_mgkg", 0) or 0),
            "ratio_n_p": (modified_soil.get("n_mgkg", 0) or 0) / max(modified_soil.get("p_mgkg", 0) or 1, 1),
            "ratio_k_p": (modified_soil.get("k_mgkg", 0) or 0) / max(modified_soil.get("p_mgkg", 0) or 1, 1)
        }
        
        # Prepare features with modified data
        modified_prepared = prepared.copy()
        modified_prepared["soil"] = modified_soil
        modified_prepared["engineering"] = modified_engineering
        
        # Rebuild feature vector with modified data
        X_modified = _build_feature_vector(modified_prepared, MODEL_CACHE["feature_columns"], MODEL_CACHE["encoders"], MODEL_CACHE["imputer"])
        
        # Run prediction with modified data
        model = MODEL_CACHE["model"]
        optimized_yield = float(model.predict(X_modified)[0])
        
        # Get base yield for comparison
        base_yield = float(model.predict(prepared["features"])[0])
        yield_improvement = optimized_yield - base_yield
        improvement_percentage = (yield_improvement / base_yield) * 100 if base_yield > 0 else 0
        
        # Prepare result data
        result_data = {
            "district": body.district,
            "crop": body.crop,
            "season": body.season or "Kharif",
            "variety": body.variety or "unknown",
            "base_yield_kg_per_hectare": round(base_yield, 2),
            "optimized_yield_kg_per_hectare": round(optimized_yield, 2),
            "yield_improvement_kg_per_hectare": round(yield_improvement, 2),
            "improvement_percentage": round(improvement_percentage, 2),
            "applied_interventions": applied_interventions,
            "soil_analysis": {
                "modified_soil_health_score": round(modified_engineering["soil_health_score"], 4),
                "original_soil_health_score": round(prepared["engineering"].get("soil_health_score", 0), 4),
                "nutrient_additions": {
                    "nitrogen_mg_kg": round(total_nitrogen_addition, 2),
                    "phosphorus_mg_kg": round(total_phosphorus_addition, 2),
                    "potassium_mg_kg": round(total_potassium_addition, 2)
                }
            }
        }
        
        # Try to get user and farm info for saving results and creating calendar events
        user_id = request.session.get("user_id")
        farm_id = None
        
        if user_id:
            farm_id = get_user_farm_id(user_id, db)
        
        # Save optimization result to database
        try:
            optimization_id = save_optimization_result(db, result_data, user_id, farm_id)
            result_data["optimization_id"] = optimization_id
            
            # Create calendar events for fertilizer applications
            if farm_id and applied_interventions:
                create_fertilizer_calendar_events(db, farm_id, applied_interventions, body.crop)
                
        except Exception as e:
            print(f"Warning: Could not save optimization result or create calendar events: {e}")
        
        # Return the original format for backward compatibility
        return {
            "district": result_data["district"],
            "crop": result_data["crop"],
            "season": result_data["season"],
            "variety": result_data["variety"],
            "base_yield_kg_per_hectare": result_data["base_yield_kg_per_hectare"],
            "optimized_yield_kg_per_hectare": result_data["optimized_yield_kg_per_hectare"],
            "yield_improvement_kg_per_hectare": result_data["yield_improvement_kg_per_hectare"],
            "improvement_percentage": result_data["improvement_percentage"],
            "applied_interventions": result_data["applied_interventions"],
            "modified_soil_health_score": result_data["soil_analysis"]["modified_soil_health_score"],
            "original_soil_health_score": result_data["soil_analysis"]["original_soil_health_score"],
            "nutrient_additions": result_data["soil_analysis"]["nutrient_additions"]
        }
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Model artifacts missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-soil")
def optimize_soil(body: OptimizeSoilBody, request: Request, db=Depends(get_db)):
    """
    Optimize soil by applying fertilizer interventions and predicting the new yield.
    
    This endpoint:
    1. Accepts original prediction inputs (district, crop, etc.) plus interventions
    2. Converts farmer-friendly inputs (e.g., "2 bags of Urea") to scientific nutrient values
    3. Runs the XGBoost model on modified soil data to predict optimized yield
    
    Args:
        body: OptimizeSoilBody containing district, crop, season, variety, and interventions
        request: FastAPI request object for session management
        db: Database connection dependency
    
    Returns:
        JSON response with optimized yield prediction and intervention details
    """
    try:
        # Load model artifacts
        load_artifacts()
        
        # Get base soil data for the district using existing function
        prepared = prepare_features_from_db(db, body.district.strip(), body.crop.strip(), body.season, body.variety)
        base_soil = prepared["soil"]
        
        # Convert interventions to nutrient values using the converter
        total_nitrogen_addition = 0.0
        total_phosphorus_addition = 0.0
        total_potassium_addition = 0.0
        applied_interventions = []
        
        for intervention in body.interventions:
            # Use the existing converter function
            nutrients = convert_intervention_to_nutrients(intervention)
            total_nitrogen_addition += nutrients["nitrogen_mg_kg"]
            total_phosphorus_addition += nutrients["phosphorus_mg_kg"]
            total_potassium_addition += nutrients["potassium_mg_kg"]
            
            applied_interventions.append({
                "fertilizer": intervention.fertilizer,
                "quantity": intervention.quantity,
                "unit": intervention.unit,
                "fertilizer_used": nutrients["fertilizer_used"],
                "nitrogen_added_mg_kg": round(nutrients["nitrogen_mg_kg"], 2),
                "phosphorus_added_mg_kg": round(nutrients["phosphorus_mg_kg"], 2),
                "potassium_added_mg_kg": round(nutrients["potassium_mg_kg"], 2)
            })
        
        # Apply interventions to soil data (create modified copy)
        modified_soil = base_soil.copy()
        original_n = modified_soil.get("n_mgkg", 0) or 0
        original_p = modified_soil.get("p_mgkg", 0) or 0
        original_k = modified_soil.get("k_mgkg", 0) or 0
        
        modified_soil["n_mgkg"] = original_n + total_nitrogen_addition
        modified_soil["p_mgkg"] = original_p + total_phosphorus_addition
        modified_soil["k_mgkg"] = original_k + total_potassium_addition
        
        # Recalculate engineered features with modified soil data
        modified_engineering = {
            "soil_health_score": _calculate_soil_health_score(
                modified_soil.get("n_mgkg", 0) or 0,
                modified_soil.get("p_mgkg", 0) or 0,
                modified_soil.get("k_mgkg", 0) or 0,
                modified_soil.get("oc_percent", 0) or 0
            ),
            "npk_sum": (modified_soil.get("n_mgkg", 0) or 0) + 
                      (modified_soil.get("p_mgkg", 0) or 0) + 
                      (modified_soil.get("k_mgkg", 0) or 0),
            "ratio_n_p": (modified_soil.get("n_mgkg", 0) or 0) / max(modified_soil.get("p_mgkg", 0) or 1, 1),
            "ratio_k_p": (modified_soil.get("k_mgkg", 0) or 0) / max(modified_soil.get("p_mgkg", 0) or 1, 1)
        }
        
        # Prepare features with modified data
        modified_prepared = prepared.copy()
        modified_prepared["soil"] = modified_soil
        modified_prepared["engineering"] = modified_engineering
        
        # Rebuild feature vector with modified data
        X_modified = _build_feature_vector(modified_prepared, MODEL_CACHE["feature_columns"], MODEL_CACHE["encoders"], MODEL_CACHE["imputer"])
        
        # Run prediction with modified soil data
        model = MODEL_CACHE["model"]
        optimized_yield = float(model.predict(X_modified)[0])
        
        # Get base yield for comparison
        base_yield = float(model.predict(prepared["features"])[0])
        yield_improvement = optimized_yield - base_yield
        improvement_percentage = (yield_improvement / base_yield) * 100 if base_yield > 0 else 0
        
        # Prepare result data
        result_data = {
            "district": body.district,
            "crop": body.crop,
            "season": body.season or "Kharif",
            "variety": body.variety or "unknown",
            "base_yield_kg_per_hectare": round(base_yield, 2),
            "optimized_yield_kg_per_hectare": round(optimized_yield, 2),
            "yield_improvement_kg_per_hectare": round(yield_improvement, 2),
            "improvement_percentage": round(improvement_percentage, 2),
            "applied_interventions": applied_interventions,
            "soil_analysis": {
                "original_soil_health_score": round(prepared["engineering"].get("soil_health_score", 0), 4),
                "modified_soil_health_score": round(modified_engineering["soil_health_score"], 4),
                "soil_health_improvement": round(modified_engineering["soil_health_score"] - prepared["engineering"].get("soil_health_score", 0), 4),
                "original_nutrients": {
                    "nitrogen_mg_kg": round(original_n, 2),
                    "phosphorus_mg_kg": round(original_p, 2),
                    "potassium_mg_kg": round(original_k, 2)
                },
                "modified_nutrients": {
                    "nitrogen_mg_kg": round(modified_soil["n_mgkg"], 2),
                    "phosphorus_mg_kg": round(modified_soil["p_mgkg"], 2),
                    "potassium_mg_kg": round(modified_soil["k_mgkg"], 2)
                },
                "nutrient_additions": {
                    "nitrogen_mg_kg": round(total_nitrogen_addition, 2),
                    "phosphorus_mg_kg": round(total_phosphorus_addition, 2),
                    "potassium_mg_kg": round(total_potassium_addition, 2)
                }
            }
        }
        
        # Try to get user and farm info for saving results and creating calendar events
        user_id = request.session.get("user_id")
        farm_id = None
        
        if user_id:
            farm_id = get_user_farm_id(user_id, db)
        
        # Save optimization result to database
        try:
            optimization_id = save_optimization_result(db, result_data, user_id, farm_id)
            
            # Create calendar events for fertilizer applications
            if farm_id and applied_interventions:
                create_fertilizer_calendar_events(db, farm_id, applied_interventions, body.crop)
                
        except Exception as e:
            print(f"Warning: Could not save optimization result or create calendar events: {e}")
        
        return {
            "success": True,
            "district": result_data["district"],
            "crop": result_data["crop"],
            "season": result_data["season"],
            "variety": result_data["variety"],
            "base_yield_kg_per_hectare": result_data["base_yield_kg_per_hectare"],
            "optimized_yield_kg_per_hectare": result_data["optimized_yield_kg_per_hectare"],
            "yield_improvement_kg_per_hectare": result_data["yield_improvement_kg_per_hectare"],
            "improvement_percentage": result_data["improvement_percentage"],
            "applied_interventions": result_data["applied_interventions"],
            "soil_analysis": result_data["soil_analysis"],
            "recommendations": [
                f"Applied {len(body.interventions)} fertilizer intervention(s)",
                f"Soil health score improved by {round(modified_engineering['soil_health_score'] - prepared['engineering'].get('soil_health_score', 0), 4)}",
                f"Expected yield increase: {round(improvement_percentage, 1)}%" if improvement_percentage > 0 else "Consider different fertilizer combinations for better results"
            ]
        }
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Model artifacts missing: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Soil optimization error: {str(e)}")


@app.get("/optimization-results")
def get_optimization_results_endpoint(request: Request, db=Depends(get_db), limit: int = 10):
    """
    Get optimization results for the current user or all results if not authenticated.
    
    Query params:
    - limit: Number of results to return (default 10, max 50)
    """
    try:
        # Limit the number of results for performance
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 10
            
        user_id = request.session.get("user_id")
        
        # Get optimization results
        results = get_optimization_results(db, user_id=user_id, limit=limit)
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "user_authenticated": bool(user_id)
        }
        
    except Exception as e:
        print(f"Error getting optimization results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------
# Chat endpoint for the chatbot
# ------------------------------------------------------------
class ChatBody(BaseModel):
    message: str
    session_id: Optional[str] = None

def get_fallback_response(user_message: str) -> str:
    """Simple rule-based responses for agricultural queries"""
    lm = (user_message or "").lower()
    
    # Greetings
    if any(g in lm for g in ["hello", "hi", "hey", "namaste", "namaskar", "ନମସ୍କାର", "ନମସ୍ତେ"]):
        return (
            "Namaste! I'm Krushi Sahayak from KrushiBandhu AI. I can help with Farm Setup, "
            "Yield Predictions, Dashboard Analytics, Plant Disease Diagnosis, and Crop Management. "
            "How can I assist you today?"
        )
    
    # Farm setup
    if any(k in lm for k in ["farm", "setup", "boundary", "plot", "ଫାର୍ମ", "ସେଟ"]):
        return (
            "KrushiBandhu AI supports comprehensive farm management: create your farm profile, "
            "set boundaries on the map, track multiple plots, and use the farm calendar. "
            "Visit your dashboard to begin setting up your farm."
        )
    
    # Yield predictions
    if any(k in lm for k in ["prediction", "predict", "yield", "forecast", "ପୂର୍ବାନୁମାନ"]):
        return (
            "We provide ML-based yield predictions for Paddy, Maize, Mustard, Groundnut, Ragi, "
            "and Mung across Odisha districts. Go to the Predict page, select your district and crop, "
            "and view detailed results with weather forecasts on your dashboard."
        )
    
    
    # Dashboard
    if any(k in lm for k in ["dashboard", "analytics", "history", "ଡ୍ୟାସବୋର୍ଡ"]):
        return (
            "Your dashboard shows latest yield predictions, farm analytics, satellite NDVI crop health, "
            "prediction history, and weather forecasts. Access it from the main navigation menu."
        )
    
    # Plant doctor
    if any(k in lm for k in ["disease", "pest", "plant", "doctor", "sick", "problem", "ରୋଗ"]):
        return (
            "Use our Plant Doctor feature to diagnose crop diseases. Upload a photo of affected leaves "
            "or plants, and our AI will identify potential diseases and suggest treatments."
        )
    
    # Weather
    if any(k in lm for k in ["weather", "rain", "temperature", "forecast", "ପାଗ"]):
        return (
            "Get 7-day weather forecasts, rainfall predictions, and temperature trends for your district. "
            "Weather data is integrated with yield predictions and farming recommendations."
        )
    
    # Default response
    return (
        "I'm Krushi Sahayak from KrushiBandhu AI - your complete agricultural platform for Odisha farmers. "
        "Ask me about Farm Setup, Yield Predictions, Plant Disease Diagnosis, Weather Forecasts, "
        "or Dashboard features. I can respond in both English and Odia!"
    )

def get_gemini_response(user_message: str) -> dict:
    """Get response from Gemini API. Returns {reply: str, source: str}."""
    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            print("[chatbot] GEMINI_API_KEY missing or placeholder. Using fallback.")
            return {"reply": get_fallback_response(user_message), "source": "fallback_no_api_key"}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Agricultural context prompt
        system_prompt = """You are Krushi Sahayak, an AI assistant for KrushiBandhu AI - an agricultural platform for Odisha farmers. 

Key features of our platform:
- Yield predictions for Paddy, Maize, Mustard, Groundnut, Ragi, Mung across Odisha districts
- Farm management: plot boundaries, farm calendar, multiple plots
- Plant Doctor: AI disease diagnosis from crop photos
- Weather forecasts and satellite NDVI crop health monitoring
- Dashboard with analytics and prediction history

Respond in a helpful, farmer-friendly tone. You can answer in both English and Odia. Keep responses concise but informative. Focus on practical agricultural advice for Odisha farmers."""

        full_prompt = f"{system_prompt}\n\nUser: {user_message}\nKrushi Sahayak:"

        response = model.generate_content(full_prompt)
        if getattr(response, "text", None):
            return {"reply": response.text, "source": "gemini"}
        print("[chatbot] Gemini returned no text. Using fallback.")
        return {"reply": get_fallback_response(user_message), "source": "fallback_empty"}

    except ImportError:
        # If google-generativeai not installed, use fallback
        print("[chatbot] google-generativeai not installed. Using fallback.")
        return {"reply": get_fallback_response(user_message), "source": "fallback_no_library"}
    except Exception as e:
        print(f"[chatbot] Gemini API error: {e}")
        return {"reply": get_fallback_response(user_message), "source": "fallback_api_error"}

@app.post("/chat")
def chat_endpoint(body: ChatBody):
    """Chat endpoint with Gemini AI integration"""
    try:
        msg = (body.message or "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Try Gemini first, fallback to rule-based responses
        result = get_gemini_response(msg)
        
        return {
            "reply": result.get("reply"),
            "source": result.get("source"),
            "timestamp": datetime.now().isoformat(),
            "session_id": body.session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
