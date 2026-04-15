import pandas as pd
import json
import os

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Load the dataset
df = pd.read_csv(os.path.join(DATA_DIR, "merged_crop_data.csv"))

# Group by district and calculate averages
district_data = {}

for district in df['district'].unique():
    district_df = df[df['district'] == district]
    
    # Calculate averages
    avg_rainfall = district_df['rainfall (mm)'].mean()
    avg_max_temp = district_df['max temp (°c)'].mean()
    avg_min_temp = district_df['min temp (°c)'].mean()
    avg_temp = (avg_max_temp + avg_min_temp) / 2
    
    district_data[district] = {
        "avgRainfall": round(avg_rainfall, 1),
        "avgMaxTemp": round(avg_max_temp, 1),
        "avgMinTemp": round(avg_min_temp, 1),
        "avgTemp": round(avg_temp, 1)
    }

# Save to JSON file
with open(os.path.join(DATA_DIR, "district_historical_data.json"), 'w') as f:
    json.dump(district_data, f, indent=2)

print("Historical data extracted and saved to data/district_historical_data.json")

# Also print the data in TypeScript format for easy copying
print("\nTypeScript format for PredictionPage.tsx:")
print("const districtHistoricalData: Record<string, {")
print("  avgRainfall: number;")
print("  avgMaxTemp: number;")
print("  avgMinTemp: number;")
print("  avgTemp: number;")
print("}> = {")

for district, data in district_data.items():
    print(f'  "{district}": {{ avgRainfall: {data["avgRainfall"]}, avgMaxTemp: {data["avgMaxTemp"]}, avgMinTemp: {data["avgMinTemp"]}, avgTemp: {data["avgTemp"]} }},') 

print("};")