#!/usr/bin/env python3
"""
KrushiBandhu AI - Database Setup Script
Phase 1.1: Data Foundation & Automated Engine

This script sets up the complete database infrastructure for the KrushiBandhu AI system.
Run this script after installing MySQL and setting up your environment.
"""

import os
import sys
import subprocess
import time
import pandas as pd
from pathlib import Path

def check_mysql_installation():
    """Check if MySQL is installed and running."""
    # Common MySQL installation paths on Windows
    mysql_paths = [
        'mysql',
        'C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysql.exe',
        'C:\\Program Files\\MySQL\\MySQL Server 8.1\\bin\\mysql.exe',
        'C:\\Program Files\\MySQL\\MySQL Server 8.2\\bin\\mysql.exe',
        'C:\\Program Files\\MySQL\\MySQL Server 8.3\\bin\\mysql.exe',
        'C:\\Program Files\\MySQL\\MySQL Server 8.4\\bin\\mysql.exe',
        'C:\\Program Files (x86)\\MySQL\\MySQL Server 8.0\\bin\\mysql.exe',
        'C:\\Program Files (x86)\\MySQL\\MySQL Server 8.1\\bin\\mysql.exe',
        'C:\\Program Files (x86)\\MySQL\\MySQL Server 8.2\\bin\\mysql.exe',
        'C:\\Program Files (x86)\\MySQL\\MySQL Server 8.3\\bin\\mysql.exe',
        'C:\\Program Files (x86)\\MySQL\\MySQL Server 8.4\\bin\\mysql.exe',
        'C:\\xampp\\mysql\\bin\\mysql.exe',
        'C:\\wamp64\\bin\\mysql\\mysql8.0.21\\bin\\mysql.exe'
    ]
    
    for mysql_path in mysql_paths:
        try:
            result = subprocess.run([mysql_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ MySQL found: {result.stdout.strip()}")
                print(f"   Path: {mysql_path}")
                return True
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    
    print("❌ MySQL not found in common installation paths")
    print("   Please ensure MySQL is installed and running")
    print("   Common locations:")
    print("   - C:\\Program Files\\MySQL\\MySQL Server X.X\\bin\\")
    print("   - C:\\xampp\\mysql\\bin\\")
    print("   - C:\\wamp64\\bin\\mysql\\")
    return False

def check_python_dependencies():
    """Check if required Python packages are installed."""
    required_packages = [
        ('mysql-connector-python', 'mysql.connector'),
        ('pandas', 'pandas'),
        ('python-dotenv', 'dotenv')
    ]
    
    missing_packages = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✅ {package_name} is installed")
        except ImportError:
            missing_packages.append(package_name)
            print(f"❌ {package_name} is missing")
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def create_env_file():
    """Create .env file from template if it doesn't exist."""
    env_file = Path('.env')
    env_example = Path('config.env.example')
    
    if not env_file.exists() and env_example.exists():
        print("📝 Creating .env file from template...")
        with open(env_example, 'r') as src, open(env_file, 'w') as dst:
            dst.write(src.read())
        print("✅ .env file created. Please update it with your actual values.")
        return True
    elif env_file.exists():
        print("✅ .env file already exists")
        return True
    else:
        print("⚠️  No .env template found, creating basic .env file...")
        with open(env_file, 'w') as f:
            f.write("""# KrushiBandhu AI - Environment Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=16042006
DB_NAME=krushibandhu_ai
DB_PORT=3306
DEBUG=True
""")
        print("✅ Basic .env file created")
        return True

def test_mysql_connection():
    """Test MySQL connection with current configuration."""
    try:
        from database_manager import DatabaseManager
        db_manager = DatabaseManager()
        if db_manager.test_connection():
            print("✅ MySQL connection successful")
            return True
        else:
            print("❌ MySQL connection failed")
            print("   Please check your database credentials in config.env")
            return False
    except Exception as e:
        print(f"❌ MySQL connection error: {e}")
        print("   This might be due to:")
        print("   - MySQL service not running")
        print("   - Wrong credentials in config.env")
        print("   - MySQL not listening on the expected port")
        return False

def migrate_csv_data_simple(db_manager, csv_file_path: str) -> bool:
    """Simple CSV data migration that matches our current schema."""
    try:
        # Load CSV data
        df = pd.read_csv(csv_file_path)
        print(f"📊 Loaded CSV data: {len(df)} rows, {len(df.columns)} columns")
        
        # Get unique districts and insert them
        unique_districts = df['district'].unique()
        print(f"📍 Found {len(unique_districts)} unique districts")
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert districts
            for district in unique_districts:
                # Check if district already exists
                cursor.execute("SELECT id FROM districts WHERE district_name = %s", (district,))
                if cursor.fetchone():
                    continue
                
                # Get sample data for this district
                district_data = df[df['district'] == district].iloc[0]
                
                # Insert district
                rainfall = float(district_data.get('rainfall (mm)', 1400))
                max_temp = float(district_data.get('max temp (°c)', 32))
                min_temp = float(district_data.get('min temp (°c)', 25))
                avg_temp = (max_temp + min_temp) / 2
                
                cursor.execute("""
                    INSERT INTO districts (district_name, imd_station_id, climate_zone, 
                                         avg_rainfall_annual, avg_temperature_annual, predominant_soil_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    district,
                    f"IMD_{district.upper().replace(' ', '_')}",
                    'Tropical',  # Default climate zone
                    rainfall,
                    avg_temp,
                    district_data.get('soil type', 'Unknown')
                ))
            
            # Insert some sample soil data
            sample_data = df.head(10)  # Take first 10 rows as sample
            for _, row in sample_data.iterrows():
                # Get district ID
                cursor.execute("SELECT id FROM districts WHERE district_name = %s", (row['district'],))
                district_result = cursor.fetchone()
                if not district_result:
                    continue
                
                district_id = district_result[0]
                
                # Insert soil data
                cursor.execute("""
                    INSERT INTO soil_data (district_id, crop_type, soil_type, ph_level, 
                                         organic_carbon_percent, nitrogen_mg_per_kg, 
                                         phosphorus_mg_per_kg, potassium_mg_per_kg)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    district_id,
                    row.get('crop', 'Unknown'),
                    row.get('soil type', 'Unknown'),
                    7.0,  # Default pH
                    1.5,  # Default organic carbon
                    100.0,  # Default nitrogen
                    50.0,   # Default phosphorus
                    200.0   # Default potassium
                ))
            
            conn.commit()
            print(f"✅ Migrated {len(unique_districts)} districts and {len(sample_data)} soil samples")
            return True
            
    except Exception as e:
        print(f"❌ CSV migration error: {e}")
        return False

def run_database_setup():
    """Run the complete database setup."""
    try:
        from database_manager import DatabaseManager
        
        print("\n🚀 Starting database setup...")
        db_manager = DatabaseManager()
        
        # Create database (if needed)
        print("📊 Verifying database...")
        if not db_manager.create_database():
            print("❌ Database verification failed!")
            return False
        
        # Run SQL setup
        print("🏗️  Setting up database schema...")
        if not db_manager.run_sql_file('database_setup_simple.sql'):
            print("❌ Database schema setup failed!")
            return False
        
        # Migrate CSV data using the robust DatabaseManager implementation
        print("📋 Migrating CSV data...")
        if os.path.exists('merged_crop_data.csv'):
            if not db_manager.migrate_csv_data('merged_crop_data.csv'):
                print("❌ CSV data migration failed!")
                return False
        else:
            print("⚠️  CSV file not found, skipping migration")
        
        print("✅ Database setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        return False

def verify_setup():
    """Verify the database setup."""
    try:
        from database_manager import DatabaseManager
        db_manager = DatabaseManager()
        
        print("\n🔍 Verifying database setup...")
        
        # Test connection
        if not db_manager.test_connection():
            print("❌ Database connection verification failed")
            return False
        
        # Check tables
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            tables_to_check = ['districts', 'soil_data', 'weather_cache', 'system_config']
            for table in tables_to_check:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ Table '{table}': {count} records")
        
        print("✅ Database verification completed!")
        return True
        
    except Exception as e:
        print(f"❌ Database verification error: {e}")
        return False

def main():
    """Main setup function."""
    print("🌾 KrushiBandhu AI - Database Setup")
    print("=" * 50)
    
    # Check prerequisites
    print("\n📋 Checking prerequisites...")
    
    #if not check_mysql_installation():
       # print("\n❌ Please install MySQL first:")
        #print("   - Windows: Download from https://dev.mysql.com/downloads/mysql/")
        #print("   - macOS: brew install mysql")
        #print("   - Ubuntu: sudo apt-get install mysql-server")
        #return False
    
    if not check_python_dependencies():
        print("\n❌ Please install missing Python packages first")
        return False
    
    # Create environment file
    print("\n📝 Setting up environment...")
    if not create_env_file():
        print("❌ Environment setup failed")
        return False
    
    # Test MySQL connection and create database if needed
    print("\n🔌 Testing MySQL connection...")
    if not test_mysql_connection():
        print("\n⚠️  Database doesn't exist yet, creating it...")
        try:
            from database_manager import DatabaseManager
            db_manager = DatabaseManager()
            if db_manager.create_database():
                print("✅ Database created successfully")
            else:
                print("❌ Failed to create database")
                return False
        except Exception as e:
            print(f"❌ Error creating database: {e}")
            return False
    
    # Run database setup
    print("\n🏗️  Setting up database...")
    if not run_database_setup():
        print("❌ Database setup failed")
        return False
    
    # Verify setup
    if not verify_setup():
        print("❌ Database verification failed")
        return False
    
    print("\n🎉 Database setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Update API keys in the system_config table")
    print("2. Run: python weather_data_fetcher.py")
    print("3. Test the new database endpoints")
    print("4. Start the application with: python api.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
