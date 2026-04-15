"""
KrushiBandhu AI - Database Manager
Phase 1.1: Data Foundation & Automated Engine

This module provides database connection management, migration utilities,
and data access functions for the KrushiBandhu AI system.
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

class DatabaseManager:
    """
    Database manager for KrushiBandhu AI system.
    Handles connections, migrations, and data operations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize database manager with configuration.
        
        Args:
            config: Database configuration dictionary
        """
        self.config = config or self._get_default_config()
        self.connection = None
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default database configuration."""
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', '16042006'),
            'database': os.getenv('DB_NAME', 'krushibandhu_ai'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'charset': 'utf8mb4',
            'autocommit': True,
            'raise_on_warnings': True
        }
    
    def get_connection(self):
        """
        Get a database connection.
        
        Returns:
            mysql.connector.connection: Database connection
        """
        try:
            connection = mysql.connector.connect(**self.config)
            return connection
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            logger.info("Database connection test successful")
            return True
        except Error as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def create_database(self) -> bool:
        """
        Create the database if it doesn't exist.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Connect without specifying database
            config_without_db = self.config.copy()
            del config_without_db['database']
            
            with mysql.connector.connect(**config_without_db) as conn:
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']} "
                             f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                logger.info(f"Database '{self.config['database']}' created/verified successfully")
                return True
        except Error as e:
            # If database already exists, that's fine
            if e.errno == 1007:  # Database exists error
                logger.info(f"Database '{self.config['database']}' already exists")
                return True
            else:
                logger.error(f"Error creating database: {e}")
                return False
    
    def run_sql_file(self, file_path: str) -> bool:
        """
        Execute SQL commands from a file.
        
        Args:
            file_path: Path to SQL file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(PROJECT_ROOT, file_path)
            with open(file_path, 'r', encoding='utf-8') as file:
                sql_commands = file.read()
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Split commands by semicolon and execute each
            for command in sql_commands.split(';'):
                command = command.strip()
                # Remove comments from the command
                lines = command.split('\n')
                clean_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('--'):
                        clean_lines.append(line)
                clean_command = ' '.join(clean_lines)
                
                if clean_command:
                    try:
                        cursor.execute(clean_command)
                        # If it's a SELECT statement, fetch the result to avoid "Unread result" error
                        if clean_command.strip().upper().startswith('SELECT'):
                            result = cursor.fetchall()
                            logger.info(f"Executed SELECT: {clean_command[:50]}... Result: {result}")
                        else:
                            logger.info(f"Executed: {clean_command[:50]}...")
                    except Error as e:
                        # Skip database creation errors (database already exists)
                        if e.errno == 1007 and 'CREATE DATABASE' in clean_command.upper():
                            logger.info(f"Skipping database creation - already exists")
                            continue
                        # Skip table creation errors (table already exists)
                        elif e.errno == 1050 and 'CREATE TABLE' in clean_command.upper():
                            logger.info(f"Skipping table creation - already exists")
                            continue
                        # Skip duplicate key errors (data already exists)
                        elif e.errno == 1062 and 'INSERT' in clean_command.upper():
                            logger.info(f"Skipping insert - duplicate entry")
                            continue
                        else:
                            logger.error(f"Error executing command: {clean_command[:50]}... Error: {e}")
                            raise e
            
            conn.commit()
            conn.close()
            logger.info(f"SQL file '{file_path}' executed successfully")
            return True
        except Error as e:
            logger.error(f"Error executing SQL file: {e}")
            return False
        except FileNotFoundError:
            logger.error(f"SQL file not found: {file_path}")
            return False
    
    def migrate_csv_data(self, csv_file_path: str) -> bool:
        """
        Migrate data from the existing CSV file to the new database schema.
        
        Args:
            csv_file_path: Path to merged_crop_data.csv
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Read CSV data
            df = pd.read_csv(csv_file_path)
            logger.info(f"Loaded CSV data: {df.shape[0]} rows, {df.shape[1]} columns")
            
            # ------------------------------------------------------------
            # Ensure numeric types and safe values for DECIMAL columns
            # - Create/normalize avg_annual_rainfall_mm and avg_temperature_annual
            # - Coerce errors to NaN, round to 2 decimals
            # ------------------------------------------------------------
            # Rainfall source column in CSV
            rainfall_col = 'rainfall (mm)'
            if rainfall_col in df.columns:
                df['avg_annual_rainfall_mm'] = pd.to_numeric(df[rainfall_col], errors='coerce').round(2)
            else:
                # If not present, create the column as NaN
                df['avg_annual_rainfall_mm'] = pd.to_numeric(pd.Series([], dtype='float64'), errors='coerce')

            # Temperature source columns in CSV
            max_col = 'max temp (°c)'
            min_col = 'min temp (°c)'
            max_series = pd.to_numeric(df[max_col], errors='coerce') if max_col in df.columns else pd.Series([float('nan')] * len(df))
            min_series = pd.to_numeric(df[min_col], errors='coerce') if min_col in df.columns else pd.Series([float('nan')] * len(df))
            df['avg_temperature_annual'] = ((max_series + min_series) / 2).round(2)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Migrate districts data
                self._migrate_districts_data(df, cursor)
                
                # Migrate soil data
                self._migrate_soil_data(df, cursor)
                
                conn.commit()
                logger.info("CSV data migration completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error migrating CSV data: {e}")
            return False
    
    def _migrate_districts_data(self, df: pd.DataFrame, cursor) -> None:
        """Migrate districts data from CSV (aligned with database_setup_simple.sql)."""
        # Get unique districts from CSV
        unique_districts = df['district'].unique()

        # Helper to clean numeric for DECIMAL columns
        def _clean_numeric(val):
            try:
                import math
                if val is None:
                    return None
                if isinstance(val, float) and math.isnan(val):
                    return None
                return round(float(val), 2)
            except Exception:
                return None
        
        for district in unique_districts:
            # Check if district already exists
            cursor.execute("SELECT id FROM districts WHERE district_name = %s", (district,))
            if cursor.fetchone():
                continue
            
            # Sample row for this district
            district_data = df[df['district'] == district].iloc[0]
            
            # Compute values
            climate_zone = self._get_climate_zone(district)
            avg_rain = _clean_numeric(district_data.get('avg_annual_rainfall_mm'))
            avg_temp = _clean_numeric(district_data.get('avg_temperature_annual'))
            soil_type = district_data.get('soil type', 'Unknown')
            imd_station = f"IMD_{str(district).upper().replace(' ', '_')[:45]}"  # keep within VARCHAR(50)

            # Insert using columns that exist in database_setup_simple.sql
            insert_query = """
            INSERT INTO districts (
                district_name, imd_station_id, latitude, longitude, climate_zone,
                avg_rainfall_annual, avg_temperature_annual, predominant_soil_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(
                insert_query,
                (
                    district,
                    imd_station,
                    None,  # latitude unknown
                    None,  # longitude unknown
                    climate_zone,
                    avg_rain,
                    avg_temp,
                    soil_type,
                ),
            )

            logger.info(f"Migrated district: {district}")
    
    def _migrate_soil_data(self, df: pd.DataFrame, cursor) -> None:
        """Migrate soil data from CSV (aligned with database_setup_simple.sql).

        This version ingests extended nutrient columns (Ca, Mg, S, Zn, B, Fe, Cu, Mn)
        and applies safe numeric conversion (coerce, round(2), NaN->None) before insert.
        """
        for _, row in df.iterrows():
            # Get district ID
            cursor.execute("SELECT id FROM districts WHERE district_name = %s", (row['district'],))
            district_result = cursor.fetchone()
            if not district_result:
                continue

            district_id = district_result[0]

            # Extended insert for soil_data including nutrient panel
            insert_query = """
            INSERT INTO soil_data (
                district_id, crop_type, soil_type, ph_level,
                organic_carbon_percent, nitrogen_mg_per_kg,
                phosphorus_mg_per_kg, potassium_mg_per_kg,
                calcium_percent, magnesium_percent,
                sulfur_mg_per_kg, zinc_mg_per_kg, boron_mg_per_kg,
                iron_mg_per_kg, copper_mg_per_kg, manganese_mg_per_kg,
                sample_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Coerce numerics safely with rounding to 2 decimals and NaN->None
            def _dec2(val):
                try:
                    import math
                    if val is None:
                        return None
                    v = float(val)
                    if isinstance(v, float) and math.isnan(v):
                        return None
                    return round(v, 2)
                except Exception:
                    return None

            cursor.execute(
                insert_query,
                (
                    district_id,
                    row.get('crop', 'Unknown'),
                    row.get('soil type', 'Unknown'),
                    None,  # pH not available
                    _dec2(row.get('oc_(%)')),
                    _dec2(row.get('p_(%)')),  # CSV uses percent; mapped as-is (proxy for N as not present)
                    _dec2(row.get('p_(%)')),
                    _dec2(row.get('k_(%)')),
                    _dec2(row.get('ca_(%)')),
                    _dec2(row.get('mg_(%)')),
                    _dec2(row.get('s_(%)')),
                    _dec2(row.get('zn_(%)')),
                    _dec2(row.get('b_(%)')),
                    _dec2(row.get('fe_(%)')),
                    _dec2(row.get('cu_(%)')),
                    _dec2(row.get('mn_(%)')),
                    datetime.now().date(),
                ),
            )
    
    def _get_climate_zone(self, district: str) -> str:
        """Determine climate zone based on district name."""
        coastal_districts = ['Puri', 'Ganjam', 'Balasore', 'Baleswar', 'Kendrapada', 'Jagatsinghpur']
        northern_districts = ['Mayurbhanj', 'Keonjhar']
        western_districts = ['Sundargarh', 'Sambalpur', 'Bargarh', 'Jharsuguda', 'Deogarh']
        southern_districts = ['Kalahandi', 'Koraput', 'Gajapati', 'Rayagada', 'Malkangiri', 'Nabarangpur', 'Nuapada']
        
        if district in coastal_districts:
            return 'Coastal'
        elif district in northern_districts:
            return 'Northern'
        elif district in western_districts:
            return 'Western'
        elif district in southern_districts:
            return 'Southern'
        else:
            return 'Central'
    
    def get_district_id(self, district_name: str) -> Optional[int]:
        """
        Get district ID by name.
        
        Args:
            district_name: Name of the district
            
        Returns:
            int: District ID if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM districts WHERE district_name = %s", (district_name,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Error as e:
            logger.error(f"Error getting district ID: {e}")
            return None
    
    def get_weather_data(self, district_name: str, days: int = 7) -> List[Dict]:
        """
        Get weather data for a district.
        
        Args:
            district_name: Name of the district
            days: Number of days to retrieve
            
        Returns:
            List[Dict]: Weather data records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                SELECT wc.*, d.district_name, d.climate_zone
                FROM weather_cache wc
                JOIN districts d ON wc.district_id = d.id
                WHERE d.district_name = %s
                AND wc.date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                ORDER BY wc.date DESC
                """
                cursor.execute(query, (district_name, days))
                return cursor.fetchall()
        except Error as e:
            logger.error(f"Error getting weather data: {e}")
            return []
    
    def get_soil_data(self, district_name: str, crop_type: str = None) -> List[Dict]:
        """
        Get soil data for a district.
        
        Args:
            district_name: Name of the district
            crop_type: Optional crop type filter
            
        Returns:
            List[Dict]: Soil data records
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if crop_type:
                    query = """
                    SELECT sd.*, d.district_name
                    FROM soil_data sd
                    JOIN districts d ON sd.district_id = d.id
                    WHERE d.district_name = %s AND sd.crop_type = %s
                    ORDER BY sd.sample_date DESC
                    """
                    cursor.execute(query, (district_name, crop_type))
                else:
                    query = """
                    SELECT sd.*, d.district_name
                    FROM soil_data sd
                    JOIN districts d ON sd.district_id = d.id
                    WHERE d.district_name = %s
                    ORDER BY sd.sample_date DESC
                    """
                    cursor.execute(query, (district_name,))
                return cursor.fetchall()
        except Error as e:
            logger.error(f"Error getting soil data: {e}")
            return []
    
    def insert_weather_data(self, district_name: str, weather_data: Dict) -> bool:
        """
        Insert weather data for a district.
        
        Args:
            district_name: Name of the district
            weather_data: Weather data dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            district_id = self.get_district_id(district_name)
            if not district_id:
                logger.error(f"District not found: {district_name}")
                return False
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Use INSERT ... ON DUPLICATE KEY UPDATE for upsert
                query = """
                INSERT INTO weather_cache (
                    district_id, date, current_temperature_celsius, max_temperature_celsius,
                    min_temperature_celsius, total_rainfall_mm, sunshine_hours,
                    forecast_7day, weather_warnings, alert_level, data_source
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON DUPLICATE KEY UPDATE
                    current_temperature_celsius = VALUES(current_temperature_celsius),
                    max_temperature_celsius = VALUES(max_temperature_celsius),
                    min_temperature_celsius = VALUES(min_temperature_celsius),
                    total_rainfall_mm = VALUES(total_rainfall_mm),
                    sunshine_hours = VALUES(sunshine_hours),
                    forecast_7day = VALUES(forecast_7day),
                    weather_warnings = VALUES(weather_warnings),
                    alert_level = VALUES(alert_level),
                    last_updated = CURRENT_TIMESTAMP
                """
                
                cursor.execute(query, (
                    district_id,
                    weather_data.get('date', datetime.now().date()),
                    weather_data.get('current_temperature'),
                    weather_data.get('max_temperature'),
                    weather_data.get('min_temperature'),
                    weather_data.get('rainfall'),
                    weather_data.get('sunshine_hours'),
                    json.dumps(weather_data.get('forecast_7day', {})),
                    json.dumps(weather_data.get('warnings', {})),
                    weather_data.get('alert_level', 'None'),
                    weather_data.get('data_source', 'IMD')
                ))
                
                logger.info(f"Weather data inserted for {district_name}")
                return True
                
        except Error as e:
            logger.error(f"Error inserting weather data: {e}")
            return False
    
    def get_system_config(self, config_key: str) -> Optional[str]:
        """
        Get system configuration value.
        
        Args:
            config_key: Configuration key
            
        Returns:
            str: Configuration value if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT config_value FROM system_config WHERE config_key = %s", (config_key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Error as e:
            logger.error(f"Error getting system config: {e}")
            return None
    
    def update_system_config(self, config_key: str, config_value: str) -> bool:
        """
        Update system configuration value.
        
        Args:
            config_key: Configuration key
            config_value: Configuration value
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                INSERT INTO system_config (config_key, config_value, config_type)
                VALUES (%s, %s, 'SETTING')
                ON DUPLICATE KEY UPDATE
                    config_value = VALUES(config_value),
                    updated_at = CURRENT_TIMESTAMP
                """
                cursor.execute(query, (config_key, config_value))
                logger.info(f"System config updated: {config_key}")
                return True
        except Error as e:
            logger.error(f"Error updating system config: {e}")
            return False


def main():
    """
    Main function for database setup and migration.
    """
    print("KrushiBandhu AI - Database Setup")
    print("=" * 50)
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Test connection
    print("Testing database connection...")
    if not db_manager.test_connection():
        print("❌ Database connection failed!")
        return
    
    print("✅ Database connection successful!")
    
    # Create database
    print("Creating database...")
    if not db_manager.create_database():
        print("❌ Database creation failed!")
        return
    
    print("✅ Database created successfully!")
    
    # Run SQL setup file
    print("Running database schema setup...")
    if not db_manager.run_sql_file(os.path.join('sql', 'database_setup.sql')):
        print("❌ Database schema setup failed!")
        return
    
    print("✅ Database schema setup completed!")
    
    # Migrate CSV data
    print("Migrating CSV data...")
    csv_path = os.path.join(PROJECT_ROOT, 'data', 'merged_crop_data.csv')
    if os.path.exists(csv_path):
        if not db_manager.migrate_csv_data(csv_path):
            print("❌ CSV data migration failed!")
            return
        print("✅ CSV data migration completed!")
    else:
        print("⚠️  CSV file not found, skipping migration")
    
    print("\n🎉 Database setup completed successfully!")
    print("\nNext steps:")
    print("1. Update your API keys in the system_config table")
    print("2. Run the weather data fetcher")
    print("3. Test the new database endpoints")


if __name__ == "__main__":
    main()
