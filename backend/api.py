import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import mysql.connector
import joblib
import os
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import timedelta

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="16042006",
        database="cropai_db"
    )

# Initialize database and tables
def init_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="16042006"
    )
    cursor = conn.cursor()
    
    # Create database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS cropai_db")
    cursor.execute("USE cropai_db")
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# Initialize database on startup
init_db()

# User registration endpoint
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validate input
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Insert user into database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            conn.commit()
            return jsonify({'message': 'User registered successfully'}), 201
        except mysql.connector.Error as err:
            if err.errno == 1062:  # Duplicate entry error
                return jsonify({'error': 'Username or email already exists'}), 409
            else:
                return jsonify({'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User login endpoint
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        # Validate input
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Check credentials
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not user or not check_password_hash(user['password'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Set session
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Logout endpoint
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

# Check authentication status
@app.route('/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'username': session['username']
            }
        })
    return jsonify({'authenticated': False})

# Simple prediction function based on the data patterns
# Load the trained model and encoders
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
model_path = os.path.join(MODELS_DIR, "rf_model.pkl")
encoder_path = os.path.join(MODELS_DIR, "label_encoders.pkl")
features_path = os.path.join(MODELS_DIR, "feature_columns.pkl")

# Check if model files exist and load them
if os.path.exists(model_path) and os.path.exists(encoder_path) and os.path.exists(features_path):
    model = joblib.load(model_path)
    label_encoders = joblib.load(encoder_path)
    feature_columns = joblib.load(features_path)
    model_loaded = True
else:
    model_loaded = False
    print("Warning: Model files not found. Falling back to rule-based prediction.")

def predict_yield(district, crop, rainfall, temperature):
    """Predict yield using trained model or fallback to rule-based method"""
    
    # Try to use the trained model if available
    if model_loaded:
        try:
            # Prepare input data for the model
            sample_data = {
                'district': district,
                'crop': crop + " (Kharif)",  # Adjust crop name to match dataset format
                'variety': 'Local/Hybrid',
                'duration (days)': '110-155',  # Changed to string to match dataset format
                'soil type': 'Sandy Loam',
                'rainfall (mm)': rainfall,
                'max temp (°c)': temperature + 5,  # Fixed: Use correct column name with degree symbol
                'min temp (°c)': temperature - 5,  # Fixed: Use correct column name with degree symbol
                'sunshine hours': 6,
                'phase': 'Vegetative Growth',
                'water requirement (mm)': rainfall * 1.2,
                'oc_(%)': 0.5,
                'p_(%)': 25,
                'k_(%)': 200,
                'ca_(%)': 8,
                'mg_(%)': 50,
                's_(%)': 20,
                'zn_(%)': 5,
                'b_(%)': 2,
                'fe_(%)': 100,
                'cu_(%)': 1,
                'mn_(%)': 1
            }
            
            sample_df = pd.DataFrame([sample_data])
            
            # Encode categorical features
            for col in ['district', 'crop', 'variety', 'soil type', 'phase']:
                if col in label_encoders:
                    sample_df[col] = label_encoders[col].transform(sample_df[col].astype(str))
            
            # Make prediction using the model
            prediction = model.predict(sample_df[feature_columns])[0]
            
            # Add small random variation (2%)
            variation = np.random.normal(1.0, 0.02)
            prediction = prediction * variation
            
            return round(prediction, 0)
            
        except Exception as e:
            print(f"Error using ML model: {e}")
            print("Falling back to rule-based prediction")
            # Fall back to rule-based method if model prediction fails
    
    # Rule-based fallback method (your existing code)
    # Base yields by crop (kg/hectare)
    crop_base_yields = {
        'Paddy': 3000,
        'Maize': 2500,
        'Mustard': 1200,
        'Wheat': 2800,
        'Sugarcane': 80000,
        'Cotton': 500,
        'Groundnut': 1500,
        'Sesame': 800,
        'Sunflower': 2000,
        'Jute': 2000,
        'Turmeric': 15000,
        'Ginger': 20000
    }
    
    # District multipliers (based on typical productivity)
    district_multipliers = {
        'Cuttack': 1.0,
        'Ganjam': 0.95,
        'Puri': 1.05,
        'Bhubaneswar': 1.0,
        'Balasore': 1.1,
        'Bhadrak': 1.0,
        'Jajpur': 0.95,
        'Kendrapada': 1.0,
        'Jagatsinghpur': 0.9,
        'Khordha': 1.0,
        'Nayagarh': 0.95,
        'Gajapati': 0.85,
        'Koraput': 0.8,
        'Rayagada': 0.8,
        'Malkangiri': 0.75,
        'Nabarangpur': 0.8,
        'Nuapada': 0.7,
        'Kalahandi': 0.7,
        'Bargarh': 0.8,
        'Sambalpur': 0.75,
        'Jharsuguda': 0.7,
        'Sundargarh': 0.65,
        'Deogarh': 0.6,
        'Angul': 0.7,
        'Dhenkanal': 0.75,
        'Keonjhar': 0.7,
        'Mayurbhanj': 0.8,
        'Baleswar': 0.9,
        'Kendujhar': 0.7
    }
    
    # Get base yield
    base_yield = crop_base_yields.get(crop, 2000)
    
    # Apply district multiplier
    district_mult = district_multipliers.get(district, 1.0)
    
    # Rainfall factor (optimal around 1000-1200mm)
    if 800 <= rainfall <= 1200:
        rainfall_factor = 1.2
    elif 600 <= rainfall < 800 or 1200 < rainfall <= 1500:
        rainfall_factor = 1.0
    elif rainfall < 600:
        rainfall_factor = 0.7
    else:
        rainfall_factor = 0.8
    
    # Temperature factor (optimal around 25-30C)
    if 25 <= temperature <= 30:
        temp_factor = 1.1
    elif 20 <= temperature < 25 or 30 < temperature <= 35:
        temp_factor = 1.0
    elif temperature < 20:
        temp_factor = 0.8
    else:
        temp_factor = 0.9
    
    # Calculate predicted yield
    predicted_yield = base_yield * district_mult * rainfall_factor * temp_factor
    
    # Add some realistic variation (2% instead of 5% for more consistent results)
    variation = np.random.normal(1.0, 0.02)
    predicted_yield = predicted_yield * variation
    
    # Ensure minimum yield
    predicted_yield = max(predicted_yield, 500)
    
    return round(predicted_yield, 0)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        district = data.get('district')
        crop = data.get('crop')
        rainfall = float(data.get('rainfall', 1200))
        temperature = float(data.get('temperature', 28))
        
        # Get prediction
        predicted_yield = predict_yield(district, crop, rainfall, temperature)
        
        # Calculate average yield for comparison (simplified)
        avg_yield = predicted_yield * (0.8 + np.random.random() * 0.4)
        percentage_diff = round(((predicted_yield - avg_yield) / avg_yield) * 100, 1)
        
        # Confidence range (10%)
        confidence_min = round(predicted_yield * 0.9)
        confidence_max = round(predicted_yield * 1.1)
        
        # Key factors
        key_factors = []
        if rainfall > 1200:
            key_factors.append("Good rainfall levels (+)")
        if temperature < 30:
            key_factors.append("Optimal temperature (+)")
        if rainfall < 800:
            key_factors.append("Low rainfall (-)")
        if temperature > 35:
            key_factors.append("High temperature (-)")
        
        response = {
            'predictedYield': predicted_yield,
            'averageYield': round(avg_yield),
            'percentageDifference': percentage_diff,
            'confidenceRange': {
                'min': confidence_min,
                'max': confidence_max
            },
            'keyFactors': key_factors
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
