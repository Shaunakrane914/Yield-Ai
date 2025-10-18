from typing import Optional
from datetime import timedelta

import os
import mysql.connector
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------
app = FastAPI(title="Krushi-Mitra AI (FastAPI)")

# CORS (allow credentials for session cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware (7 days)
SESSION_SECRET = os.environ.get("SESSION_SECRET", os.urandom(24))
SEVEN_DAYS_SECONDS = int(timedelta(days=7).total_seconds())
app.add_middleware(SessionMiddleware, secret_key=str(SESSION_SECRET), max_age=SEVEN_DAYS_SECONDS)

# ----------------------------------------------------------------------------
# Database utilities (reuse same connection settings as Flask api.py)
# ----------------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "16042006")
DB_NAME = os.environ.get("DB_NAME", "krushibandhu_ai")


def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )


# ----------------------------------------------------------------------------
# Request/Response models
# ----------------------------------------------------------------------------
class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class FarmData(BaseModel):
    farm_name: str
    boundary_coordinates: list[list[float]]  # [[lat, lng], [lat, lng], ...]


# ----------------------------------------------------------------------------
# Endpoints: Auth
# ----------------------------------------------------------------------------
@app.post("/register")
def register(body: RegisterBody):
    try:
        username = body.username.strip()
        email = str(body.email).lower().strip()
        password = body.password

        if not username or not email or not password:
            raise HTTPException(status_code=400, detail="All fields are required")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password),
            )
            conn.commit()
        except mysql.connector.Error as err:
            # 1062 = duplicate entry
            if getattr(err, 'errno', None) == 1062:
                raise HTTPException(status_code=409, detail="Username or email already exists")
            raise HTTPException(status_code=500, detail=str(err))
        finally:
            cursor.close()
            conn.close()

        return {"message": "User registered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login")
def login(body: LoginBody, request: Request):
    try:
        email = str(body.email).lower().strip()
        password = body.password

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password are required")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if not user or not check_password_hash(user["password"], password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Session (7-day cookie-based via SessionMiddleware)
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]

        return {
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}


@app.get("/check-auth")
def check_auth(request: Request):
    if request.session.get("user_id"):
        return {
            "authenticated": True,
            "user": {
                "id": request.session.get("user_id"),
                "username": request.session.get("username"),
            },
        }
    return {"authenticated": False}


@app.post("/my-farm")
def save_farm(farm_data: FarmData, request: Request):
    try:
        # Check if user is authenticated
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        farm_name = farm_data.farm_name.strip()
        boundary_coords = farm_data.boundary_coordinates
        
        if not farm_name:
            raise HTTPException(status_code=400, detail="Farm name is required")
        
        if not boundary_coords or len(boundary_coords) < 3:
            raise HTTPException(status_code=400, detail="At least 3 boundary points are required")
        
        # Convert coordinates to JSON string for storage
        import json
        boundary_json = json.dumps(boundary_coords)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if user already has a farm (update if exists, insert if new)
            cursor.execute("SELECT id FROM farms WHERE user_id = %s", (user_id,))
            existing_farm = cursor.fetchone()
            
            if existing_farm:
                # Update existing farm
                cursor.execute(
                    "UPDATE farms SET farm_name = %s, boundary_coordinates = %s, updated_at = NOW() WHERE user_id = %s",
                    (farm_name, boundary_json, user_id)
                )
            else:
                # Insert new farm
                cursor.execute(
                    "INSERT INTO farms (user_id, farm_name, boundary_coordinates, created_at, updated_at) VALUES (%s, %s, %s, NOW(), NOW())",
                    (user_id, farm_name, boundary_json)
                )
            
            conn.commit()
        except mysql.connector.Error as err:
            raise HTTPException(status_code=500, detail=f"Database error: {str(err)}")
        finally:
            cursor.close()
            conn.close()
        
        return {"message": "Farm saved successfully", "farm_name": farm_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------------
# Deprecated predict endpoint (kept for compatibility)
# ----------------------------------------------------------------------------
@app.post("/predict")
def predict_deprecated():
    return JSONResponse(
        status_code=410,
        content={
            "message": "This endpoint is deprecated. Please use the new recommendation endpoints in the upcoming release.",
        },
    )


# ----------------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "app": "Krushi-Mitra AI (FastAPI)"}


# ----------------------------------------------------------------------------
# Dev entrypoint
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
