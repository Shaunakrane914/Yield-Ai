# KrushiBandhu AI - Database Setup Guide

## Phase 1.1: Data Foundation & Automated Engine

This guide will help you set up the MySQL database infrastructure for the KrushiBandhu AI system, replacing the static CSV dependency with a robust, automated data engine.

## 🎯 Overview

The new database schema includes:
- **districts**: All Odisha districts with IMD station IDs
- **soil_data**: Comprehensive soil health information
- **weather_cache**: Real-time weather data and forecasts
- **crop_yield_history**: Historical yield data for ML training
- **api_logs**: API usage tracking
- **system_config**: System configuration and API keys

## 📋 Prerequisites

### 1. MySQL Installation

**Windows:**
```bash
# Download and install MySQL from:
# https://dev.mysql.com/downloads/mysql/
```

**macOS:**
```bash
brew install mysql
brew services start mysql
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

### 2. Python Dependencies

```bash
pip install -r requirements_database.txt
```

## 🚀 Quick Setup

### Option 1: Automated Setup (Recommended)

```bash
# Run the automated setup script
python setup_database.py
```

This script will:
- Check prerequisites
- Create environment configuration
- Set up the database schema
- Migrate existing CSV data
- Verify the installation

### Option 2: Manual Setup

#### Step 1: Configure Environment

```bash
# Copy the environment template
cp config.env.example .env

# Edit .env with your MySQL credentials
nano .env
```

Update these values in `.env`:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=krushibandhu_ai
DB_PORT=3306
```

#### Step 2: Create Database

```bash
# Run the database setup
python database_manager.py
```

#### Step 3: Verify Setup

```bash
# Test the connection
python -c "from database_manager import DatabaseManager; print('✅ Connection successful' if DatabaseManager().test_connection() else '❌ Connection failed')"
```

## 📊 Database Schema

### Districts Table
```sql
CREATE TABLE districts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_name VARCHAR(100) NOT NULL UNIQUE,
    imd_station_id VARCHAR(20) UNIQUE,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    climate_zone ENUM('Coastal', 'Central', 'Northern', 'Southern', 'Western'),
    -- ... more fields
);
```

### Soil Data Table
```sql
CREATE TABLE soil_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    crop_type VARCHAR(100) NOT NULL,
    ph_level DECIMAL(4, 2),
    organic_carbon_percent DECIMAL(5, 2),
    nitrogen_mg_per_kg DECIMAL(8, 2),
    -- ... more soil parameters
    FOREIGN KEY (district_id) REFERENCES districts(id)
);
```

### Weather Cache Table
```sql
CREATE TABLE weather_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    date DATE NOT NULL,
    current_temperature_celsius DECIMAL(5, 2),
    total_rainfall_mm DECIMAL(8, 2),
    forecast_7day JSON,
    weather_warnings JSON,
    -- ... more weather fields
    FOREIGN KEY (district_id) REFERENCES districts(id)
);
```

## 🔧 Usage Examples

### Python Database Operations

```python
from database_manager import DatabaseManager

# Initialize database manager
db = DatabaseManager()

# Get weather data for a district
weather_data = db.get_weather_data('Cuttack', days=7)

# Get soil data for a district and crop
soil_data = db.get_soil_data('Cuttack', 'Paddy')

# Insert new weather data
weather_info = {
    'date': '2024-01-15',
    'current_temperature': 28.5,
    'max_temperature': 32.0,
    'min_temperature': 25.0,
    'rainfall': 15.2,
    'forecast_7day': {...},
    'data_source': 'IMD'
}
db.insert_weather_data('Cuttack', weather_info)
```

### SQL Queries

```sql
-- Get current weather for all districts
SELECT d.district_name, wc.current_temperature_celsius, wc.total_rainfall_mm
FROM weather_cache wc
JOIN districts d ON wc.district_id = d.id
WHERE wc.date = CURDATE();

-- Get soil health summary
SELECT d.district_name, sd.crop_type, sd.soil_health_score, sd.fertility_rating
FROM soil_data sd
JOIN districts d ON sd.district_id = d.id
WHERE sd.sample_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

-- Get districts with weather alerts
SELECT d.district_name, wc.alert_level, wc.weather_warnings
FROM weather_cache wc
JOIN districts d ON wc.district_id = d.id
WHERE wc.alert_level != 'None';
```

## 🔄 Data Migration

The system automatically migrates data from your existing `merged_crop_data.csv`:

1. **Districts**: Extracts unique districts and creates records
2. **Soil Data**: Migrates all soil parameters and crop information
3. **Climate Zones**: Automatically assigns climate zones based on district location

## 📈 Performance Optimization

### Indexes
The schema includes optimized indexes for:
- District lookups
- Date-based queries
- Weather alerts
- Soil health scores

### Caching Strategy
- Weather data cached for 6 hours
- Soil data refreshed monthly
- API logs for monitoring and optimization

## 🔐 Security

### Database User Setup
```sql
-- Create dedicated application user
CREATE USER 'krushibandhu_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON krushibandhu_ai.* TO 'krushibandhu_user'@'localhost';
FLUSH PRIVILEGES;
```

### Configuration Security
- API keys stored in `system_config` table
- Environment variables for sensitive data
- Encrypted configuration options available

## 🐛 Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check if MySQL is running
sudo systemctl status mysql  # Linux
brew services list | grep mysql  # macOS
```

**2. Access Denied**
```bash
# Reset MySQL root password
sudo mysql -u root
ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password';
FLUSH PRIVILEGES;
```

**3. Database Not Found**
```bash
# Create database manually
mysql -u root -p
CREATE DATABASE krushibandhu_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**4. Import Errors**
```bash
# Check file permissions
ls -la database_setup.sql
chmod 644 database_setup.sql
```

### Logs and Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test individual components
from database_manager import DatabaseManager
db = DatabaseManager()
print(db.test_connection())
```

## 📚 Next Steps

After successful database setup:

1. **Configure API Keys**: Update `system_config` table with real API keys
2. **Weather Data Fetcher**: Implement automated weather data collection
3. **Soil Health Sync**: Connect to government soil health databases
4. **ML Model Integration**: Update models to use new database
5. **API Endpoints**: Modify backend to use new data structure

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the logs in your application
3. Verify your MySQL installation and configuration
4. Ensure all Python dependencies are installed correctly

---

**🎉 Congratulations!** You've successfully set up the database foundation for the KrushiBandhu AI system. The static CSV dependency has been replaced with a robust, scalable database infrastructure ready for automated data collection and processing.
