import pandas as pd
import numpy as np
import joblib
import json

# Simple prediction function based on the data patterns
def predict_yield(district, crop, rainfall, temperature):
    """Simple yield prediction based on crop, rainfall, and temperature"""
    
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
    
    # Add some realistic variation (10%)
    variation = np.random.normal(1.0, 0.05)
    predicted_yield = predicted_yield * variation
    
    # Ensure minimum yield
    predicted_yield = max(predicted_yield, 500)
    
    return round(predicted_yield, 0)

# Test the function
if __name__ == "__main__":
    # Test predictions
    test_cases = [
        ('Cuttack', 'Paddy', 1200, 28),
        ('Ganjam', 'Maize', 1000, 30),
        ('Puri', 'Mustard', 800, 25),
        ('Balasore', 'Wheat', 1100, 27)
    ]
    
    print("Testing yield predictions:")
    for district, crop, rainfall, temp in test_cases:
        yield_pred = predict_yield(district, crop, rainfall, temp)
        print(f"{crop} in {district}: {yield_pred:.0f} kg/hectare")
    
    print("\nPrediction function ready!")
