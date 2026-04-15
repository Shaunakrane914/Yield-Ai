import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import warnings
import os
warnings.filterwarnings('ignore')

# Project paths
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Load the data
print("Loading crop data...")
df = pd.read_csv(os.path.join(DATA_DIR, "merged_crop_data.csv"))

print(f"Dataset shape: {df.shape}")

# Create a simple yield estimation based on rainfall and temperature
print("\nCreating simple yield estimation...")

# Simple yield calculation based on rainfall and temperature
def simple_yield_estimation(row):
    # Base yield by crop
    crop_yields = {
        'Paddy (Kharif)': 3000,
        'Paddy (Rabi)': 2800,
        'Maize (Kharif)': 2500,
        'Mustard': 1200,
        'Groundnut (Kharif)': 1500,
        'Groundnut (Rabi)': 1500,
        'Mung': 800,
        'Ragi (Kharif)': 2000
    }
    
    base_yield = crop_yields.get(row['crop'], 2000)
    
    # Rainfall impact
    rainfall = row['rainfall (mm)']
    if rainfall > 1000:
        rainfall_factor = 1.2
    elif rainfall > 600:
        rainfall_factor = 1.0
    else:
        rainfall_factor = 0.8
    
    # Temperature impact (using max temp)
    max_temp = row['max temp (°c)']  # Fixed: Use the correct column name with degree symbol
    if 25 <= max_temp <= 32:
        temp_factor = 1.1
    elif 20 <= max_temp < 25 or 32 < max_temp <= 35:
        temp_factor = 1.0
    else:
        temp_factor = 0.9
    
    # Soil impact
    soil_factor = 1.0
    if row['oc_(%)'] > 0.5:
        soil_factor = 1.1
    elif row['oc_(%)'] > 0.3:
        soil_factor = 1.05
    else:
        soil_factor = 0.95
    
    # Add some variation
    variation = np.random.normal(1.0, 0.1)
    
    estimated_yield = base_yield * rainfall_factor * temp_factor * soil_factor * variation
    
    return max(estimated_yield, 500)

# Create target variable
df['estimated_yield'] = df.apply(simple_yield_estimation, axis=1)

print(f"\nYield statistics:")
print(df['estimated_yield'].describe())

# Prepare features
print("\nPreparing features...")

# Convert duration ranges to numerical values (take the average of the range) before creating X
def parse_duration(duration):
    if isinstance(duration, str) and '-' in str(duration):
        try:
            start, end = map(float, str(duration).split('-'))
            return (start + end) / 2
        except (ValueError, AttributeError):
            return float('nan')
    try:
        return float(duration)
    except (ValueError, TypeError):
        return float('nan')

# Process duration column in the original dataframe
if 'duration (days)' in df.columns:
    df['duration (days)'] = df['duration (days)'].apply(parse_duration)
    # Fill any remaining NaN values with the median
    median_duration = df['duration (days)'].median()
    df['duration (days)'] = df['duration (days)'].fillna(median_duration)

# Select features
feature_columns = [
    'district', 'crop', 'variety', 'duration (days)', 'soil type',
    'rainfall (mm)', 'max temp (°c)', 'min temp (°c)', 'sunshine hours',
    'phase', 'water requirement (mm)', 'oc_(%)', 'p_(%)', 'k_(%)',
    'ca_(%)', 'mg_(%)', 's_(%)', 'zn_(%)', 'b_(%)', 'fe_(%)', 'cu_(%)', 'mn_(%)'
]

X = df[feature_columns].copy()
y = df['estimated_yield']

print(f"Feature matrix shape: {X.shape}")
print("\nSample of duration values:", X['duration (days)'].head())

# Handle categorical variables
categorical_columns = ['district', 'crop', 'variety', 'soil type', 'phase']

label_encoders = {}

# Ensure all categorical columns are strings and handle any missing values
for col in categorical_columns:
    if col in X.columns:
        # Convert to string and fill any remaining NaN values with 'unknown'
        X[col] = X[col].astype(str).fillna('unknown')
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        label_encoders[col] = le

# Handle missing values
print("\nHandling missing values...")

# First, separate numeric and non-numeric columns
num_columns = X.select_dtypes(include=['number']).columns
non_num_columns = X.select_dtypes(exclude=['number']).columns

# Fill numeric columns with their median
for col in num_columns:
    if X[col].isna().any():
        median_val = X[col].median()
        X[col] = X[col].fillna(median_val)
        print(f"Filled {X[col].isna().sum()} missing values in {col} with median: {median_val}")

# Fill non-numeric columns with their mode (most frequent value)
for col in non_num_columns:
    if X[col].isna().any():
        most_frequent = X[col].mode()[0] if not X[col].mode().empty else 'unknown'
        X[col] = X[col].fillna(most_frequent)
        print(f"Filled missing values in {col} with mode: {most_frequent}")

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"\nTraining set: {X_train.shape}")
print(f"Test set: {X_test.shape}")

# Train model
print("\nTraining Random Forest model...")
rf_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
rf_model.fit(X_train, y_train)

# Make predictions
rf_pred = rf_model.predict(X_test)

# Evaluate
rf_mae = mean_absolute_error(y_test, rf_pred)
rf_r2 = r2_score(y_test, rf_pred)

print(f"Random Forest Results:")
print(f"MAE: {rf_mae:.2f}")
print(f"R: {rf_r2:.4f}")

# Save model
print("\nSaving model...")
joblib.dump(rf_model, os.path.join(MODELS_DIR, "rf_model.pkl"))
joblib.dump(label_encoders, os.path.join(MODELS_DIR, "label_encoders.pkl"))
joblib.dump(feature_columns, os.path.join(MODELS_DIR, "feature_columns.pkl"))

print("Model saved successfully!")

# Test prediction function
def predict_yield(district, crop, rainfall, temperature):
    # Parse duration to get the average if it's a range
    def parse_duration(duration):
        if isinstance(duration, str) and '-' in str(duration):
            try:
                start, end = map(float, str(duration).split('-'))
                return (start + end) / 2
            except (ValueError, AttributeError):
                return 132.5  # Default average duration if parsing fails
        try:
            return float(duration)
        except (ValueError, TypeError):
            return 132.5  # Default average duration
    
    sample_data = {
        'district': district,
        'crop': crop,
        'variety': 'Local/Hybrid',
        'duration (days)': 132.5,  # Default average duration
        'soil type': 'Sandy Loam',
        'rainfall (mm)': float(rainfall),
        'max temp (°c)': float(temperature) + 5,
        'min temp (°c)': float(temperature) - 5,
        'sunshine hours': 6.0,
        'phase': 'Vegetative Growth',
        'water requirement (mm)': float(rainfall) * 1.2,
        'oc_(%)': 0.5,
        'p_(%)': 25.0,
        'k_(%)': 200.0,
        'ca_(%)': 8.0,
        'mg_(%)': 50.0,
        's_(%)': 20.0,
        'zn_(%)': 5.0,
        'b_(%)': 2.0,
        'fe_(%)': 100.0,
        'cu_(%)': 1.0,
        'mn_(%)': 1.0
    }
    
    # Create DataFrame and ensure proper data types
    sample_df = pd.DataFrame([sample_data])
    
    # Convert categorical columns using the label encoders
    for col in categorical_columns:
        if col in label_encoders and col in sample_df.columns:
            # Convert to string and handle unknown values
            sample_df[col] = sample_df[col].astype(str)
            # Transform using label encoder, defaulting to 0 for unknown categories
            sample_df[col] = sample_df[col].apply(
                lambda x: label_encoders[col].transform([x])[0] 
                if x in label_encoders[col].classes_ 
                else 0
            )
    
    # Ensure all feature columns are present and in the correct order
    for col in feature_columns:
        if col not in sample_df.columns:
            sample_df[col] = 0  # Default value for missing columns
    
    # Make prediction
    prediction = rf_model.predict(sample_df[feature_columns])[0]
    return prediction

# Test
print("\nTesting prediction function:")
test_prediction = predict_yield('Cuttack', 'Paddy (Kharif)', 1200, 28)
print(f"Predicted yield for Paddy in Cuttack: {test_prediction:.2f} kg/hectare")

print("\nModel training completed successfully!")
