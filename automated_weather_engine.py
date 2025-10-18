#!/usr/bin/env python3
"""
Automated Weather Engine for KrushiBandhu AI
============================================

This script automates the collection of weather data from IMD (India Meteorological Department)
APIs and stores it in the MySQL database for real-time crop yield predictions.

Features:
- Fetches rainfall data for all districts
- Gets 7-day weather forecasts
- Retrieves active weather warnings
- Processes and stores data in weather_cache table
- Handles API rate limiting and error recovery

Author: KrushiBandhu AI Team
Date: 2024
"""

import os
import sys
import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from database_manager import DatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_engine.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class WeatherDataFetcher:
    """Handles fetching weather data from IMD APIs."""
    
    def __init__(self):
        self.base_url = "https://mausam.imd.gov.in/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KrushiBandhu-AI/1.0 (Weather Data Fetcher)',
            'Accept': 'application/json'
        })
        
    def get_district_rainfall(self, district_name: str, imd_station_id: str) -> Dict:
        """
        Fetch rainfall data for a specific district.
        
        Args:
            district_name: Name of the district
            imd_station_id: IMD station ID for the district
            
        Returns:
            Dict containing rainfall data
        """
        try:
            # Simulate API call with realistic data
            # In production, replace with actual IMD API endpoint
            rainfall_data = {
                'district': district_name,
                'station_id': imd_station_id,
                'current_rainfall_mm': round(random.uniform(0, 50), 1),
                'last_24h_rainfall_mm': round(random.uniform(0, 100), 1),
                'last_7d_rainfall_mm': round(random.uniform(0, 300), 1),
                'last_30d_rainfall_mm': round(random.uniform(0, 800), 1),
                'data_timestamp': datetime.now().isoformat(),
                'data_source': 'IMD_API_SIMULATED'
            }
            
            logger.info(f"Fetched rainfall data for {district_name}: {rainfall_data['current_rainfall_mm']}mm")
            return rainfall_data
            
        except Exception as e:
            logger.error(f"Error fetching rainfall data for {district_name}: {e}")
            return {
                'district': district_name,
                'station_id': imd_station_id,
                'current_rainfall_mm': 0.0,
                'last_24h_rainfall_mm': 0.0,
                'last_7d_rainfall_mm': 0.0,
                'last_30d_rainfall_mm': 0.0,
                'data_timestamp': datetime.now().isoformat(),
                'data_source': 'IMD_API_ERROR',
                'error': str(e)
            }
    
    def get_7day_forecast(self, district_name: str, imd_station_id: str) -> Dict:
        """
        Fetch 7-day weather forecast for a specific district.
        
        Args:
            district_name: Name of the district
            imd_station_id: IMD station ID for the district
            
        Returns:
            Dict containing 7-day forecast data
        """
        try:
            # Simulate 7-day forecast data
            forecast_data = {
                'district': district_name,
                'station_id': imd_station_id,
                'forecast_days': []
            }
            
            for i in range(7):
                date = datetime.now() + timedelta(days=i)
                day_forecast = {
                    'date': date.strftime('%Y-%m-%d'),
                    'min_temp_celsius': round(random.uniform(15, 25), 1),
                    'max_temp_celsius': round(random.uniform(25, 40), 1),
                    'avg_temp_celsius': round(random.uniform(20, 32), 1),
                    'humidity_percent': round(random.uniform(40, 90), 1),
                    'wind_speed_kmph': round(random.uniform(5, 25), 1),
                    'weather_condition': random.choice(['Clear', 'Partly Cloudy', 'Cloudy', 'Light Rain', 'Heavy Rain']),
                    'rainfall_probability_percent': round(random.uniform(0, 80), 1),
                    'expected_rainfall_mm': round(random.uniform(0, 30), 1)
                }
                forecast_data['forecast_days'].append(day_forecast)
            
            logger.info(f"Fetched 7-day forecast for {district_name}")
            return forecast_data
            
        except Exception as e:
            logger.error(f"Error fetching forecast for {district_name}: {e}")
            return {
                'district': district_name,
                'station_id': imd_station_id,
                'forecast_days': [],
                'error': str(e)
            }
    
    def get_weather_warnings(self, district_name: str, imd_station_id: str) -> Dict:
        """
        Fetch active weather warnings for a specific district.
        
        Args:
            district_name: Name of the district
            imd_station_id: IMD station ID for the district
            
        Returns:
            Dict containing active warnings
        """
        try:
            # Simulate weather warnings
            warnings = []
            warning_types = ['Heavy Rain', 'Heat Wave', 'Cold Wave', 'Thunderstorm', 'Cyclone']
            
            # Randomly generate 0-2 warnings
            num_warnings = random.randint(0, 2)
            for _ in range(num_warnings):
                warning = {
                    'type': random.choice(warning_types),
                    'severity': random.choice(['Yellow', 'Orange', 'Red']),
                    'description': f"{random.choice(warning_types)} warning for {district_name}",
                    'valid_from': datetime.now().isoformat(),
                    'valid_until': (datetime.now() + timedelta(hours=random.randint(6, 48))).isoformat(),
                    'affected_areas': [district_name],
                    'recommendations': [
                        "Avoid outdoor activities",
                        "Stay updated with weather reports",
                        "Take necessary precautions"
                    ]
                }
                warnings.append(warning)
            
            warnings_data = {
                'district': district_name,
                'station_id': imd_station_id,
                'active_warnings': warnings,
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"Fetched {len(warnings)} warnings for {district_name}")
            return warnings_data
            
        except Exception as e:
            logger.error(f"Error fetching warnings for {district_name}: {e}")
            return {
                'district': district_name,
                'station_id': imd_station_id,
                'active_warnings': [],
                'error': str(e)
            }

class WeatherDataProcessor:
    """Processes and stores weather data in the database."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    def process_and_store_weather_data(self, district_id: int, district_name: str, 
                                     imd_station_id: str, weather_fetcher: WeatherDataFetcher) -> bool:
        """
        Process and store weather data for a district.
        
        Args:
            district_id: Database ID of the district
            district_name: Name of the district
            imd_station_id: IMD station ID
            weather_fetcher: WeatherDataFetcher instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Fetch all weather data
            rainfall_data = weather_fetcher.get_district_rainfall(district_name, imd_station_id)
            forecast_data = weather_fetcher.get_7day_forecast(district_name, imd_station_id)
            warnings_data = weather_fetcher.get_weather_warnings(district_name, imd_station_id)
            
            # Process the data
            today = datetime.now().date()
            
            # Calculate average temperature from forecast
            if forecast_data['forecast_days']:
                today_forecast = forecast_data['forecast_days'][0]
                avg_temp = today_forecast['avg_temp_celsius']
                min_temp = today_forecast['min_temp_celsius']
                max_temp = today_forecast['max_temp_celsius']
                humidity = today_forecast['humidity_percent']
                wind_speed = today_forecast['wind_speed_kmph']
                weather_condition = today_forecast['weather_condition']
            else:
                # Fallback values
                avg_temp = 28.0
                min_temp = 22.0
                max_temp = 35.0
                humidity = 65.0
                wind_speed = 10.0
                weather_condition = 'Clear'
            
            # Prepare data for database
            weather_record = {
                'district_id': district_id,
                'date': today,
                'predicted_rainfall': rainfall_data['current_rainfall_mm'],
                'avg_temperature': avg_temp,
                'min_temperature': min_temp,
                'max_temperature': max_temp,
                'humidity_percent': humidity,
                'wind_speed_kmph': wind_speed,
                'weather_condition': weather_condition,
                'seven_day_forecast': json.dumps(forecast_data),
                'active_warnings': json.dumps(warnings_data['active_warnings']),
                'data_source': 'IMD_API_SIMULATED',
                'confidence_score': 0.85  # Simulated confidence score
            }
            
            # Store in database
            return self._store_weather_record(weather_record)
            
        except Exception as e:
            logger.error(f"Error processing weather data for {district_name}: {e}")
            return False
    
    def _store_weather_record(self, weather_record: Dict) -> bool:
        """
        Store weather record in the database.
        
        Args:
            weather_record: Dictionary containing weather data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Use INSERT ... ON DUPLICATE KEY UPDATE for upsert operation
            insert_query = """
            INSERT INTO weather_cache (
                district_id, date, predicted_rainfall, avg_temperature, 
                min_temperature, max_temperature, humidity_percent, 
                wind_speed_kmph, weather_condition, seven_day_forecast, 
                active_warnings, data_source, confidence_score
            ) VALUES (
                %(district_id)s, %(date)s, %(predicted_rainfall)s, %(avg_temperature)s,
                %(min_temperature)s, %(max_temperature)s, %(humidity_percent)s,
                %(wind_speed_kmph)s, %(weather_condition)s, %(seven_day_forecast)s,
                %(active_warnings)s, %(data_source)s, %(confidence_score)s
            ) AS new_weather ON DUPLICATE KEY UPDATE
                predicted_rainfall = new_weather.predicted_rainfall,
                avg_temperature = new_weather.avg_temperature,
                min_temperature = new_weather.min_temperature,
                max_temperature = new_weather.max_temperature,
                humidity_percent = new_weather.humidity_percent,
                wind_speed_kmph = new_weather.wind_speed_kmph,
                weather_condition = new_weather.weather_condition,
                seven_day_forecast = new_weather.seven_day_forecast,
                active_warnings = new_weather.active_warnings,
                data_source = new_weather.data_source,
                confidence_score = new_weather.confidence_score,
                last_updated = CURRENT_TIMESTAMP
            """
            
            cursor.execute(insert_query, weather_record)
            conn.commit()
            conn.close()
            
            logger.info(f"Stored weather data for district_id {weather_record['district_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing weather record: {e}")
            return False

class AutomatedWeatherEngine:
    """Main class for the automated weather data collection system."""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.weather_fetcher = WeatherDataFetcher()
        self.weather_processor = WeatherDataProcessor(self.db_manager)
        
    def get_all_districts(self) -> List[Tuple[int, str, str]]:
        """
        Get all districts from the database.
        
        Returns:
            List of tuples (district_id, district_name, imd_station_id)
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, district_name, imd_station_id 
                FROM districts 
                ORDER BY district_name
            """)
            
            districts = cursor.fetchall()
            conn.close()
            
            logger.info(f"Retrieved {len(districts)} districts from database")
            return districts
            
        except Exception as e:
            logger.error(f"Error retrieving districts: {e}")
            return []
    
    def run_weather_collection(self) -> Dict[str, int]:
        """
        Run the complete weather data collection process.
        
        Returns:
            Dict with collection statistics
        """
        logger.info("🌤️  Starting automated weather data collection...")
        
        # Get all districts
        districts = self.get_all_districts()
        if not districts:
            logger.error("No districts found in database")
            return {'total': 0, 'success': 0, 'failed': 0}
        
        stats = {'total': len(districts), 'success': 0, 'failed': 0}
        
        for district_id, district_name, imd_station_id in districts:
            try:
                logger.info(f"Processing weather data for {district_name}...")
                
                # Process and store weather data
                success = self.weather_processor.process_and_store_weather_data(
                    district_id, district_name, imd_station_id, self.weather_fetcher
                )
                
                if success:
                    stats['success'] += 1
                    logger.info(f"✅ Successfully processed {district_name}")
                else:
                    stats['failed'] += 1
                    logger.error(f"❌ Failed to process {district_name}")
                
                # Add delay to avoid overwhelming APIs
                time.sleep(1)
                
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"❌ Error processing {district_name}: {e}")
        
        logger.info(f"🌤️  Weather collection completed: {stats['success']}/{stats['total']} successful")
        return stats
    
    def verify_data_integrity(self) -> Dict[str, int]:
        """
        Verify the integrity of collected weather data.
        
        Returns:
            Dict with verification statistics
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Check today's weather data
            today = datetime.now().date()
            cursor.execute("""
                SELECT COUNT(*) FROM weather_cache 
                WHERE date = %s
            """, (today,))
            
            today_count = cursor.fetchone()[0]
            
            # Check total weather records
            cursor.execute("SELECT COUNT(*) FROM weather_cache")
            total_count = cursor.fetchone()[0]
            
            # Check districts with weather data
            cursor.execute("""
                SELECT COUNT(DISTINCT district_id) FROM weather_cache 
                WHERE date = %s
            """, (today,))
            
            districts_with_data = cursor.fetchone()[0]
            
            conn.close()
            
            verification_stats = {
                'today_records': today_count,
                'total_records': total_count,
                'districts_with_data': districts_with_data
            }
            
            logger.info(f"📊 Data verification: {today_count} today's records, {total_count} total records")
            return verification_stats
            
        except Exception as e:
            logger.error(f"Error verifying data integrity: {e}")
            return {}

def main():
    """Main function to run the automated weather engine."""
    print("🌤️  KrushiBandhu AI - Automated Weather Engine")
    print("=" * 50)
    
    try:
        # Initialize the weather engine
        weather_engine = AutomatedWeatherEngine()
        
        # Test database connection
        if not weather_engine.db_manager.test_connection():
            logger.error("❌ Database connection failed")
            return False
        
        logger.info("✅ Database connection successful")
        
        # Run weather data collection
        collection_stats = weather_engine.run_weather_collection()
        
        # Verify data integrity
        verification_stats = weather_engine.verify_data_integrity()
        
        # Print summary
        print("\n📊 Collection Summary:")
        print(f"   Total districts: {collection_stats['total']}")
        print(f"   Successful: {collection_stats['success']}")
        print(f"   Failed: {collection_stats['failed']}")
        
        print("\n📈 Data Verification:")
        print(f"   Today's records: {verification_stats.get('today_records', 0)}")
        print(f"   Total records: {verification_stats.get('total_records', 0)}")
        print(f"   Districts with data: {verification_stats.get('districts_with_data', 0)}")
        
        if collection_stats['success'] > 0:
            print("\n🎉 Weather data collection completed successfully!")
            return True
        else:
            print("\n❌ Weather data collection failed!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Fatal error in weather engine: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
