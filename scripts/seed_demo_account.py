#!/usr/bin/env python3
"""
Demo Account Seeder for KrushiBandhu SIH Presentation
====================================================

This script creates a comprehensive demo account with realistic farming data
including user registration, farm setup, calendar events, predictions, and harvest logs.

Usage: python seed_demo_account.py
"""

import mysql.connector
from mysql.connector import Error
import bcrypt
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
# Support both DB_PASSWORD and DB_PASS env names
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', os.getenv('MYSQL_DATABASE', 'krushi_bandhu'))
DB_USER = os.getenv('DB_USER', os.getenv('MYSQL_USER', 'root'))
DB_PASSWORD = os.getenv('DB_PASSWORD', os.getenv('DB_PASS', os.getenv('MYSQL_PASSWORD', '')))
DB_PORT = int(os.getenv('DB_PORT', os.getenv('MYSQL_PORT', 3306)))

DB_CONFIG = {
    'host': DB_HOST,
    'database': DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'port': DB_PORT,
}

# Demo user configuration
DEMO_USER = {
    'username': 'demofarmer',
    'email': 'demo@farmer.com',
    'password': 'password123'
}

# Sample farm boundary coordinates for Cuttack district
CUTTACK_FARM_BOUNDARY = [
    [20.4625, 85.8830],  # Northwest corner
    [20.4620, 85.8845],  # Northeast corner
    [20.4610, 85.8840],  # Southeast corner
    [20.4615, 85.8825]   # Southwest corner
]

class DemoAccountSeeder:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.demo_user_id = None
        self.demo_farm_id = None
        
    def create_missing_tables(self):
        """Create tables that don't exist for demo functionality"""
        try:
            print("🔧 Creating missing tables for demo functionality...")
            
            # Calendar Events table
            calendar_table = """
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    event_date DATE NOT NULL,
                    event_type ENUM('AI_Suggestion', 'Farmer_Log', 'Reminder') DEFAULT 'Farmer_Log',
                    priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            
            # Farm Diary Entries table
            diary_table = """
                CREATE TABLE IF NOT EXISTS farm_diary_entries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    entry_date DATE NOT NULL,
                    entry_type ENUM('Farmer_Log', 'AI_Insight', 'Weather_Update') DEFAULT 'Farmer_Log',
                    activity_type ENUM('Planting', 'Irrigation', 'Fertilizing', 'Pest_Control', 'Disease_Management', 'Harvesting', 'General') DEFAULT 'General',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            
            # User Predictions table
            predictions_table = """
                CREATE TABLE IF NOT EXISTS user_predictions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    district VARCHAR(100) NOT NULL,
                    crop VARCHAR(100) NOT NULL,
                    season ENUM('Kharif', 'Rabi', 'Summer') NOT NULL,
                    variety VARCHAR(100),
                    predicted_yield DECIMAL(10,2) NOT NULL,
                    confidence_score DECIMAL(3,2) DEFAULT 0.00,
                    prediction_factors JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """
            
            # Harvest Logs table
            harvest_table = """
                CREATE TABLE IF NOT EXISTS harvest_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    farm_id INT,
                    crop VARCHAR(100) NOT NULL,
                    season ENUM('Kharif', 'Rabi', 'Summer') NOT NULL,
                    variety VARCHAR(100),
                    actual_yield DECIMAL(10,2) NOT NULL,
                    harvest_date DATE NOT NULL,
                    quality_grade ENUM('A', 'B', 'C', 'D') DEFAULT 'B',
                    market_price_per_kg DECIMAL(8,2),
                    total_income DECIMAL(12,2),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE SET NULL
                )
            """
            
            tables = [
                ("calendar_events", calendar_table),
                ("farm_diary_entries", diary_table),
                ("user_predictions", predictions_table),
                ("harvest_logs", harvest_table)
            ]
            
            for table_name, create_sql in tables:
                try:
                    self.cursor.execute(create_sql)
                    print(f"  ✅ Created/verified table: {table_name}")
                except Error as e:
                    print(f"  ⚠️  Error creating {table_name}: {e}")
            
            self.connection.commit()
            print("✅ All demo tables created successfully!")
            
        except Error as e:
            print(f"❌ Error creating tables: {e}")
            self.connection.rollback()
            # Don't raise - continue even if table creation fails
        
    def connect_to_database(self):
        """Establish connection to MySQL database"""
        try:
            # Helpful log (without password)
            print("Attempting DB connection with:")
            print(f"  Host: {DB_CONFIG['host']}")
            print(f"  Port: {DB_CONFIG['port']}")
            print(f"  User: {DB_CONFIG['user']}")
            print(f"  Database: {DB_CONFIG['database']}")

            if not DB_CONFIG['password']:
                print("⚠️  No DB password detected from environment (DB_PASSWORD/DB_PASS).")

            self.connection = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.connection.cursor()
            print("✅ Successfully connected to MySQL database")
            return True
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return False
    
    def clean_existing_demo_data(self):
        """Remove any existing demo user and associated data"""
        try:
            print("🧹 Cleaning existing demo data...")
            
            # Get existing demo user ID if exists
            self.cursor.execute("SELECT id FROM users WHERE email = %s", (DEMO_USER['email'],))
            result = self.cursor.fetchone()
            
            if result:
                existing_user_id = result[0]
                print(f"Found existing demo user with ID: {existing_user_id}")
                
                # Delete in correct order to handle foreign key constraints
                # Only delete from tables that exist
                tables_to_clean = [
                    ('harvest_logs', 'user_id'),
                    ('user_predictions', 'user_id'),
                    ('calendar_events', 'user_id'),
                    ('farm_diary_entries', 'user_id'),
                    ('farms', 'user_id'),
                    ('users', 'id')
                ]
                
                for table, column in tables_to_clean:
                    try:
                        # Check if table exists first
                        self.cursor.execute(f"SHOW TABLES LIKE '{table}'")
                        if self.cursor.fetchone():
                            self.cursor.execute(f"DELETE FROM {table} WHERE {column} = %s", (existing_user_id,))
                            deleted_count = self.cursor.rowcount
                            if deleted_count > 0:
                                print(f"  Deleted {deleted_count} records from {table}")
                        else:
                            print(f"  Skipped {table} (table doesn't exist)")
                    except Error as e:
                        print(f"  Skipped {table} (error: {e})")
                        continue
                
                self.connection.commit()
                print("✅ Successfully cleaned existing demo data")
            else:
                print("No existing demo user found")
                
        except Error as e:
            print(f"❌ Error cleaning demo data: {e}")
            self.connection.rollback()
            # Don't raise - continue with creation even if cleanup fails
            print("⚠️  Continuing with demo creation despite cleanup issues...")
    
    def create_demo_user(self):
        """Create the demo user account"""
        try:
            print("👤 Creating demo user account...")
            
            # Hash the password
            password_hash = bcrypt.hashpw(DEMO_USER['password'].encode('utf-8'), bcrypt.gensalt())
            
            # Detect users table columns for compatibility
            self.cursor.execute("SHOW COLUMNS FROM users")
            user_columns = {row[0] for row in self.cursor.fetchall()}

            now = datetime.now()

            # Determine column names
            username_col = 'username' if 'username' in user_columns else ('name' if 'name' in user_columns else None)
            email_col = 'email' if 'email' in user_columns else ('email_address' if 'email_address' in user_columns else None)
            password_col = 'password_hash' if 'password_hash' in user_columns else ('password' if 'password' in user_columns else None)
            created_col = 'created_at' if 'created_at' in user_columns else ('createdOn' if 'createdOn' in user_columns else None)
            updated_col = 'updated_at' if 'updated_at' in user_columns else ('updatedOn' if 'updatedOn' in user_columns else None)

            if not all([username_col, email_col, password_col]):
                raise RuntimeError(
                    f"Unsupported users schema. Columns found: {sorted(user_columns)}. "
                    "Expected username/name, email/email_address, and password_hash/password."
                )

            fields = [username_col, email_col, password_col]
            values = [DEMO_USER['username'], DEMO_USER['email'], password_hash.decode('utf-8')]

            if created_col:
                fields.append(created_col)
                values.append(now)
            if updated_col:
                fields.append(updated_col)
                values.append(now)

            placeholders = ", ".join(["%s"] * len(values))
            columns_sql = ", ".join(fields)
            user_query = f"INSERT INTO users ({columns_sql}) VALUES ({placeholders})"

            self.cursor.execute(user_query, tuple(values))
            
            self.demo_user_id = self.cursor.lastrowid
            self.connection.commit()
            
            print(f"✅ Created demo user with ID: {self.demo_user_id}")
            
        except Error as e:
            print(f"❌ Error creating demo user: {e}")
            self.connection.rollback()
            raise
    
    def create_demo_farm(self):
        """Create a demo farm in Cuttack district"""
        try:
            print("🚜 Creating demo farm...")
            # Inspect farms table for compatible columns
            self.cursor.execute("SHOW COLUMNS FROM farms")
            farm_columns = {row[0] for row in self.cursor.fetchall()}

            now = datetime.now()
            boundary_json = json.dumps(CUTTACK_FARM_BOUNDARY)

            # Determine column names (best-effort)
            user_col = 'user_id' if 'user_id' in farm_columns else ('owner_id' if 'owner_id' in farm_columns else None)
            name_col = 'name' if 'name' in farm_columns else ('farm_name' if 'farm_name' in farm_columns else ('title' if 'title' in farm_columns else None))
            district_col = 'district' if 'district' in farm_columns else ('location_district' if 'location_district' in farm_columns else None)
            state_col = 'state' if 'state' in farm_columns else ('location_state' if 'location_state' in farm_columns else None)
            boundary_col = (
                'boundary_coordinates' if 'boundary_coordinates' in farm_columns else
                ('boundary' if 'boundary' in farm_columns else
                 ('boundary_json' if 'boundary_json' in farm_columns else
                  ('coordinates' if 'coordinates' in farm_columns else
                   ('geo_json' if 'geo_json' in farm_columns else
                    ('plot_boundary' if 'plot_boundary' in farm_columns else None)))))
            )
            area_col = 'area_hectares' if 'area_hectares' in farm_columns else ('area' if 'area' in farm_columns else None)
            soil_col = 'soil_type' if 'soil_type' in farm_columns else None
            crop_col = 'primary_crop' if 'primary_crop' in farm_columns else ('crop' if 'crop' in farm_columns else None)
            created_col = 'created_at' if 'created_at' in farm_columns else ('createdOn' if 'createdOn' in farm_columns else None)
            updated_col = 'updated_at' if 'updated_at' in farm_columns else ('updatedOn' if 'updatedOn' in farm_columns else None)

            # Minimal required
            minimal_missing = []
            if not user_col: minimal_missing.append('user_id/owner_id')
            if not name_col: minimal_missing.append('name/farm_name/title')
            if not boundary_col: minimal_missing.append('boundary_coordinates/boundary/boundary_json/coordinates/geo_json/plot_boundary')
            if minimal_missing:
                raise RuntimeError(
                    f"Unsupported farms schema. Missing essential columns: {', '.join(minimal_missing)}. Found: {sorted(farm_columns)}"
                )

            fields = [user_col, name_col, boundary_col]
            values = [self.demo_user_id, "SIH Demo Farm", boundary_json]

            if district_col:
                fields.append(district_col)
                values.append("Cuttack")
            if state_col:
                fields.append(state_col)
                values.append("Odisha")
            if area_col:
                fields.append(area_col)
                values.append(2.5)
            if soil_col:
                fields.append(soil_col)
                values.append("Alluvial")
            if crop_col:
                fields.append(crop_col)
                values.append("Paddy")
            if created_col:
                fields.append(created_col)
                values.append(now)
            if updated_col:
                fields.append(updated_col)
                values.append(now)

            placeholders = ", ".join(["%s"] * len(values))
            columns_sql = ", ".join(fields)
            farm_query = f"INSERT INTO farms ({columns_sql}) VALUES ({placeholders})"

            self.cursor.execute(farm_query, tuple(values))

            self.demo_farm_id = self.cursor.lastrowid
            self.connection.commit()
            
            print(f"✅ Created demo farm with ID: {self.demo_farm_id}")
            
        except Error as e:
            print(f"❌ Error creating demo farm: {e}")
            self.connection.rollback()
            raise
    
    def populate_calendar_events(self):
        """Add AI suggestions and farmer activities to calendar"""
        try:
            print("📅 Populating calendar events...")
            
            now = datetime.now()
            
            # AI Suggestion events
            ai_events = [
                {
                    'title': 'Optimal Sowing Window',
                    'description': 'AI analysis suggests this is the optimal time for sowing based on weather patterns and soil conditions.',
                    'event_type': 'AI_Suggestion',
                    'date': now - timedelta(days=21),
                    'priority': 'high'
                },
                {
                    'title': 'Time for Nutrient Top-dressing',
                    'description': 'Based on crop growth stage analysis, apply nitrogen fertilizer for optimal yield.',
                    'event_type': 'AI_Suggestion',
                    'date': now - timedelta(days=7),
                    'priority': 'medium'
                }
            ]
            
            # Insert calendar events
            event_query = """
                INSERT INTO calendar_events (user_id, title, description, event_date, event_type, priority)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            for event in ai_events:
                self.cursor.execute(event_query, (
                    self.demo_user_id,
                    event['title'],
                    event['description'],
                    event['date'],
                    event['event_type'],
                    event['priority']
                ))
            
            self.connection.commit()
            print(f"✅ Added {len(ai_events)} AI suggestion events")
            
        except Error as e:
            print(f"❌ Error populating calendar events: {e}")
            self.connection.rollback()
    
    def populate_farm_diary(self):
        """Add farmer log entries to show app usage"""
        try:
            print("📔 Populating farm diary entries...")
            
            now = datetime.now()
            
            diary_entries = [
                {
                    'title': 'Sowing Day',
                    'content': 'Sowed Paddy seeds today. Used high-quality seeds from the cooperative.',
                    'entry_type': 'Farmer_Log',
                    'date': now - timedelta(days=20),
                    'activity_type': 'Planting'
                },
                {
                    'title': 'Fertilizer Application',
                    'content': 'Applied 2 bags of Urea as suggested by the AI system.',
                    'entry_type': 'Farmer_Log',
                    'date': now - timedelta(days=7),
                    'activity_type': 'Fertilizing'
                }
            ]
            
            # Insert diary entries
            diary_query = """
                INSERT INTO farm_diary_entries (user_id, title, content, entry_date, entry_type, activity_type)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            for entry in diary_entries:
                self.cursor.execute(diary_query, (
                    self.demo_user_id,
                    entry['title'],
                    entry['content'],
                    entry['date'],
                    entry['entry_type'],
                    entry['activity_type']
                ))
            
            self.connection.commit()
            print(f"✅ Added {len(diary_entries)} farm diary entries")
            
        except Error as e:
            print(f"❌ Error populating farm diary: {e}")
            self.connection.rollback()
    
    def populate_prediction_history(self):
        """Add prediction history showing improvement over time"""
        try:
            print("📊 Populating prediction history...")
            
            now = datetime.now()
            
            predictions = [
                {
                    'district': 'Cuttack',
                    'crop': 'Paddy',
                    'season': 'Kharif',
                    'variety': 'Swarna',
                    'predicted_yield': 3200.0,
                    'confidence_score': 0.85,
                    'date': now - timedelta(days=14)
                },
                {
                    'district': 'Cuttack',
                    'crop': 'Paddy',
                    'season': 'Kharif',
                    'variety': 'Swarna',
                    'predicted_yield': 3500.0,
                    'confidence_score': 0.92,
                    'date': now - timedelta(days=1)
                }
            ]
            
            # Insert predictions
            prediction_query = """
                INSERT INTO user_predictions (user_id, district, crop, season, variety, predicted_yield, confidence_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            for pred in predictions:
                self.cursor.execute(prediction_query, (
                    self.demo_user_id,
                    pred['district'],
                    pred['crop'],
                    pred['season'],
                    pred['variety'],
                    pred['predicted_yield'],
                    pred['confidence_score']
                ))
            
            self.connection.commit()
            print(f"✅ Added {len(predictions)} prediction records")
            
        except Error as e:
            print(f"❌ Error populating prediction history: {e}")
            self.connection.rollback()
    
    def add_harvest_log(self):
        """Add a harvest log from previous season to show completed cycle"""
        try:
            print("🌾 Adding harvest log from previous season...")
            
            # Previous Rabi season (harvested ~4 months ago)
            harvest_date = datetime.now() - timedelta(days=120)
            actual_yield = 3100.0  # kg/ha
            area_hectares = 2.5
            total_production = actual_yield * area_hectares
            market_price = 22.50  # Rs per kg
            total_income = total_production * market_price
            
            # Insert harvest log
            harvest_query = """
                INSERT INTO harvest_logs (user_id, farm_id, crop, season, variety, actual_yield, harvest_date, quality_grade, market_price_per_kg, total_income, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            self.cursor.execute(harvest_query, (
                self.demo_user_id,
                self.demo_farm_id,
                'Wheat',
                'Rabi',
                'HD-2967',
                actual_yield,
                harvest_date,
                'A',
                market_price,
                total_income,
                'Excellent harvest quality. Following AI recommendations resulted in 15% higher yield than previous year.'
            ))
            
            self.connection.commit()
            print(f"✅ Added harvest log: {actual_yield} kg/ha, Total income: ₹{total_income:,.2f}")
            
        except Error as e:
            print(f"❌ Error adding harvest log: {e}")
            self.connection.rollback()
    
    def create_demo_account(self):
        """Main method to create complete demo account"""
        try:
            if not self.connect_to_database():
                return False
            
            print("🚀 Starting demo account creation process...\n")
            
            # Step 1: Create missing tables first
            self.create_missing_tables()
            
            # Step 2: Clean existing data
            self.clean_existing_demo_data()
            
            # Step 3: Create demo user
            self.create_demo_user()
            
            # Step 4: Create demo farm
            self.create_demo_farm()
            
            # Step 5: Populate calendar with AI suggestions
            self.populate_calendar_events()
            
            # Step 6: Add farm diary entries
            self.populate_farm_diary()
            
            # Step 7: Add prediction history
            self.populate_prediction_history()
            
            # Step 8: Add harvest log from previous season
            self.add_harvest_log()
            
            print("\n🎉 Demo account creation completed successfully!")
            print(f"📧 Email: {DEMO_USER['email']}")
            print(f"🔑 Password: {DEMO_USER['password']}")
            print(f"👤 Username: {DEMO_USER['username']}")
            print(f"🚜 Farm: SIH Demo Farm (Cuttack)")
            print("\nThe demo account is ready for presentation! 🌾")
            
            return True
            
        except Exception as e:
            print(f"❌ Fatal error during demo account creation: {e}")
            return False
        
        finally:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            print("🔌 Database connection closed")

def main():
    """Main function to run the demo account seeder"""
    print("=" * 60)
    print("🌾 KrushiBandhu Demo Account Seeder")
    print("   SIH 2024 Presentation Setup")
    print("=" * 60)
    print()
    
    seeder = DemoAccountSeeder()
    success = seeder.create_demo_account()
    
    if success:
        print("\n✅ Demo account setup completed successfully!")
        print("You can now use the demo account for your presentation.")
    else:
        print("\n❌ Demo account setup failed!")
        print("Please check the error messages above and try again.")

if __name__ == "__main__":
    main()
