-- =====================================================
-- KrushiBandhu AI - Database Schema Setup
-- Phase 1.1: Data Foundation & Automated Engine
-- =====================================================

-- Create the main database (if not exists)
CREATE DATABASE IF NOT EXISTS krushibandhu_ai 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- Use the database
USE krushibandhu_ai;

-- =====================================================
-- 1. DISTRICTS TABLE
-- Stores all Odisha districts with IMD station information
-- =====================================================

CREATE TABLE IF NOT EXISTS districts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_name VARCHAR(100) NOT NULL UNIQUE,
    state VARCHAR(50) DEFAULT 'Odisha',
    imd_station_id VARCHAR(20) UNIQUE,
    imd_station_name VARCHAR(150),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    elevation_meters INT,
    climate_zone ENUM('Coastal', 'Central', 'Northern', 'Southern', 'Western') NOT NULL,
    soil_type_primary VARCHAR(50),
    soil_type_secondary VARCHAR(50),
    avg_annual_rainfall_mm DECIMAL(8, 2),
    avg_annual_temp_celsius DECIMAL(5, 2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_district_name (district_name),
    INDEX idx_imd_station (imd_station_id),
    INDEX idx_climate_zone (climate_zone),
    INDEX idx_coordinates (latitude, longitude)
);

-- =====================================================
-- 2. SOIL_DATA TABLE
-- Stores comprehensive soil health information
-- =====================================================

CREATE TABLE IF NOT EXISTS soil_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    crop_type VARCHAR(100) NOT NULL,
    variety VARCHAR(100),
    soil_sample_id VARCHAR(50),
    
    -- Basic Soil Properties
    ph_level DECIMAL(4, 2),
    electrical_conductivity DECIMAL(8, 4),
    organic_carbon_percent DECIMAL(5, 2),
    
    -- Macronutrients (Primary)
    nitrogen_mg_per_kg DECIMAL(8, 2),
    phosphorus_mg_per_kg DECIMAL(8, 2),
    potassium_mg_per_kg DECIMAL(8, 2),
    
    -- Secondary Macronutrients
    calcium_percent DECIMAL(5, 2),
    magnesium_percent DECIMAL(5, 2),
    sulfur_percent DECIMAL(5, 2),
    
    -- Micronutrients
    zinc_mg_per_kg DECIMAL(8, 2),
    boron_mg_per_kg DECIMAL(8, 2),
    iron_mg_per_kg DECIMAL(8, 2),
    copper_mg_per_kg DECIMAL(8, 2),
    manganese_mg_per_kg DECIMAL(8, 2),
    
    -- Soil Classification
    acidic_percent DECIMAL(5, 2),
    alkaline_percent DECIMAL(5, 2),
    neutral_percent DECIMAL(5, 2),
    normal_ec_percent DECIMAL(5, 2),
    
    -- Soil Health Metrics
    soil_health_score DECIMAL(4, 2),
    fertility_rating ENUM('Very Low', 'Low', 'Medium', 'High', 'Very High'),
    water_holding_capacity DECIMAL(5, 2),
    
    -- Sample Information
    sample_date DATE,
    sample_depth_cm INT DEFAULT 15,
    number_of_samples INT DEFAULT 1,
    lab_name VARCHAR(200),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    INDEX idx_district_crop (district_id, crop_type),
    INDEX idx_sample_date (sample_date),
    INDEX idx_soil_health (soil_health_score),
    INDEX idx_fertility (fertility_rating)
);

-- =====================================================
-- 3. WEATHER_CACHE TABLE
-- Stores real-time and forecasted weather data
-- =====================================================

CREATE TABLE IF NOT EXISTS weather_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    date DATE NOT NULL,
    
    -- Current Weather Data
    current_temperature_celsius DECIMAL(5, 2),
    current_humidity_percent DECIMAL(5, 2),
    current_pressure_hpa DECIMAL(7, 2),
    current_wind_speed_kmh DECIMAL(5, 2),
    current_wind_direction_degrees INT,
    current_visibility_km DECIMAL(5, 2),
    
    -- Daily Aggregates
    max_temperature_celsius DECIMAL(5, 2),
    min_temperature_celsius DECIMAL(5, 2),
    avg_temperature_celsius DECIMAL(5, 2),
    total_rainfall_mm DECIMAL(8, 2),
    sunshine_hours DECIMAL(4, 2),
    uv_index DECIMAL(4, 2),
    
    -- 7-Day Forecast (stored as JSON)
    forecast_7day JSON,
    
    -- Weather Warnings and Alerts
    weather_warnings JSON,
    alert_level ENUM('None', 'Yellow', 'Orange', 'Red') DEFAULT 'None',
    
    -- Agricultural Impact Metrics
    heat_stress_index DECIMAL(4, 2),
    drought_index DECIMAL(4, 2),
    flood_risk_percent DECIMAL(5, 2),
    pest_risk_score DECIMAL(4, 2),
    
    -- Data Source and Quality
    data_source ENUM('IMD', 'WeatherAPI', 'OpenWeatherMap', 'Manual') DEFAULT 'IMD',
    data_quality_score DECIMAL(3, 2) DEFAULT 1.00,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_district_date (district_id, date),
    INDEX idx_date (date),
    INDEX idx_alert_level (alert_level),
    INDEX idx_data_source (data_source),
    INDEX idx_last_updated (last_updated)
);

-- =====================================================
-- 4. CROP_YIELD_HISTORY TABLE
-- Stores historical yield data for model training
-- =====================================================

CREATE TABLE IF NOT EXISTS crop_yield_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    crop_type VARCHAR(100) NOT NULL,
    variety VARCHAR(100),
    season ENUM('Kharif', 'Rabi', 'Zaid') NOT NULL,
    year YEAR NOT NULL,
    
    -- Yield Data
    actual_yield_kg_per_hectare DECIMAL(10, 2),
    estimated_yield_kg_per_hectare DECIMAL(10, 2),
    yield_variance_percent DECIMAL(5, 2),
    
    -- Growing Conditions
    planting_date DATE,
    harvesting_date DATE,
    duration_days INT,
    irrigation_type ENUM('Rainfed', 'Irrigated', 'Mixed'),
    
    -- Input Data
    fertilizer_used_kg_per_hectare DECIMAL(8, 2),
    pesticide_used_kg_per_hectare DECIMAL(8, 2),
    seed_rate_kg_per_hectare DECIMAL(6, 2),
    
    -- Quality Metrics
    data_source ENUM('Government', 'Farmer_Report', 'Research_Station', 'Estimated') NOT NULL,
    confidence_score DECIMAL(3, 2) DEFAULT 0.50,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_district_crop_season_year (district_id, crop_type, season, year),
    INDEX idx_crop_season (crop_type, season),
    INDEX idx_year (year),
    INDEX idx_data_source (data_source)
);

-- =====================================================
-- 5. API_LOGS TABLE
-- Track API usage and data fetching
-- =====================================================

CREATE TABLE IF NOT EXISTS api_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(200),
    district_id INT,
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_status_code INT,
    response_time_ms INT,
    data_points_fetched INT,
    error_message TEXT,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE SET NULL,
    INDEX idx_api_name (api_name),
    INDEX idx_request_timestamp (request_timestamp),
    INDEX idx_response_status (response_status_code)
);

-- =====================================================
-- 6. SYSTEM_CONFIG TABLE
-- Store system configuration and API keys
-- =====================================================

CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    config_type ENUM('API_KEY', 'URL', 'THRESHOLD', 'SETTING', 'CREDENTIAL') NOT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_config_key (config_key),
    INDEX idx_config_type (config_type)
);

-- =====================================================
-- INSERT INITIAL DATA
-- =====================================================

-- Insert Odisha districts with IMD station information
INSERT INTO districts (district_name, imd_station_id, imd_station_name, latitude, longitude, climate_zone, soil_type_primary, avg_annual_rainfall_mm, avg_annual_temp_celsius) VALUES
('Cuttack', 'IMD_CTK_001', 'Cuttack Weather Station', 20.4625, 85.8828, 'Central', 'Sandy Loam', 1500.00, 28.50),
('Ganjam', 'IMD_GJM_001', 'Berhampur Weather Station', 19.3167, 84.7833, 'Coastal', 'Clay Loam', 1400.00, 28.00),
('Puri', 'IMD_PRI_001', 'Puri Weather Station', 19.8000, 85.8500, 'Coastal', 'Sandy Loam', 1450.00, 28.20),
('Balasore', 'IMD_BLS_001', 'Balasore Weather Station', 21.4942, 86.9336, 'Coastal', 'Sandy Loam', 1600.00, 28.30),
('Mayurbhanj', 'IMD_MYB_001', 'Baripada Weather Station', 21.9333, 86.7333, 'Northern', 'Red Sandy Loam', 1550.00, 27.80),
('Keonjhar', 'IMD_KNJ_001', 'Keonjhar Weather Station', 21.6333, 85.5833, 'Northern', 'Laterite', 1500.00, 27.50),
('Sundargarh', 'IMD_SDG_001', 'Sundargarh Weather Station', 22.1167, 84.0333, 'Western', 'Red Sandy Loam', 1450.00, 27.20),
('Sambalpur', 'IMD_SBP_001', 'Sambalpur Weather Station', 21.4667, 83.9667, 'Western', 'Clay Loam', 1400.00, 28.00),
('Kalahandi', 'IMD_KLH_001', 'Bhawanipatna Weather Station', 19.9000, 83.1667, 'Southern', 'Red Sandy Loam', 1400.00, 28.50),
('Koraput', 'IMD_KPT_001', 'Koraput Weather Station', 18.8167, 82.7167, 'Southern', 'Laterite', 1400.00, 28.00),
('Gajapati', 'IMD_GJP_001', 'Paralakhemundi Weather Station', 18.7833, 84.1167, 'Southern', 'Red Sandy Loam', 1400.00, 28.20),
('Rayagada', 'IMD_RGD_001', 'Rayagada Weather Station', 19.1667, 83.4167, 'Southern', 'Laterite', 1400.00, 28.30),
('Malkangiri', 'IMD_MKG_001', 'Malkangiri Weather Station', 18.3500, 81.9000, 'Southern', 'Red Sandy Loam', 1400.00, 28.50),
('Nabarangpur', 'IMD_NBR_001', 'Nabarangpur Weather Station', 19.2333, 82.5500, 'Southern', 'Red Sandy Loam', 1400.00, 28.40),
('Nuapada', 'IMD_NPD_001', 'Nuapada Weather Station', 20.1167, 82.5500, 'Southern', 'Red Sandy Loam', 1400.00, 28.60),
('Bargarh', 'IMD_BRG_001', 'Bargarh Weather Station', 21.3333, 83.6167, 'Western', 'Clay Loam', 1400.00, 28.20),
('Jharsuguda', 'IMD_JSG_001', 'Jharsuguda Weather Station', 21.8500, 84.0333, 'Western', 'Clay Loam', 1400.00, 28.00),
('Deogarh', 'IMD_DEG_001', 'Deogarh Weather Station', 21.5333, 84.7333, 'Western', 'Red Sandy Loam', 1400.00, 27.80),
('Angul', 'IMD_ANL_001', 'Angul Weather Station', 20.8333, 85.1000, 'Central', 'Clay Loam', 1400.00, 28.50),
('Dhenkanal', 'IMD_DNK_001', 'Dhenkanal Weather Station', 20.6667, 85.6000, 'Central', 'Clay Loam', 1400.00, 28.40),
('Nayagarh', 'IMD_NYG_001', 'Nayagarh Weather Station', 20.1167, 85.1000, 'Central', 'Sandy Loam', 1400.00, 28.60),
('Khordha', 'IMD_KHD_001', 'Bhubaneswar Weather Station', 20.2961, 85.8245, 'Central', 'Sandy Loam', 1400.00, 28.80),
('Jagatsinghpur', 'IMD_JSP_001', 'Jagatsinghpur Weather Station', 20.2667, 86.1667, 'Central', 'Sandy Loam', 1400.00, 28.70),
('Kendrapada', 'IMD_KDP_001', 'Kendrapada Weather Station', 20.5000, 86.4167, 'Central', 'Sandy Loam', 1400.00, 28.60),
('Bhadrak', 'IMD_BDR_001', 'Bhadrak Weather Station', 21.0667, 86.5000, 'Central', 'Sandy Loam', 1400.00, 28.50),
('Jajpur', 'IMD_JJP_001', 'Jajpur Weather Station', 20.8500, 86.3333, 'Central', 'Sandy Loam', 1400.00, 28.40),
('Baleswar', 'IMD_BLW_001', 'Baleswar Weather Station', 21.5000, 86.9167, 'Coastal', 'Sandy Loam', 1600.00, 28.20);

-- Insert system configuration
INSERT INTO system_config (config_key, config_value, config_type, description) VALUES
('imd_api_key', 'your_imd_api_key_here', 'API_KEY', 'IMD Weather API Key'),
('imd_base_url', 'https://mausam.imd.gov.in/api', 'URL', 'IMD API Base URL'),
('weather_cache_duration_hours', '6', 'THRESHOLD', 'Weather data cache duration in hours'),
('soil_data_refresh_days', '30', 'THRESHOLD', 'Soil data refresh interval in days'),
('max_api_requests_per_hour', '1000', 'THRESHOLD', 'Maximum API requests per hour'),
('enable_weather_alerts', 'true', 'SETTING', 'Enable weather alert notifications'),
('default_confidence_threshold', '0.75', 'THRESHOLD', 'Default confidence threshold for predictions');

-- =====================================================
-- CREATE VIEWS FOR COMMON QUERIES
-- =====================================================

-- View for current weather with district information
CREATE VIEW current_weather_view AS
SELECT 
    d.district_name,
    d.climate_zone,
    wc.current_temperature_celsius,
    wc.max_temperature_celsius,
    wc.min_temperature_celsius,
    wc.total_rainfall_mm,
    wc.alert_level,
    wc.last_updated
FROM weather_cache wc
JOIN districts d ON wc.district_id = d.id
WHERE wc.date = CURDATE();

-- View for soil health summary
CREATE VIEW soil_health_summary AS
SELECT 
    d.district_name,
    sd.crop_type,
    sd.soil_health_score,
    sd.fertility_rating,
    sd.ph_level,
    sd.organic_carbon_percent,
    sd.nitrogen_mg_per_kg,
    sd.phosphorus_mg_per_kg,
    sd.potassium_mg_per_kg,
    sd.sample_date
FROM soil_data sd
JOIN districts d ON sd.district_id = d.id
WHERE sd.sample_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

-- =====================================================
-- CREATE STORED PROCEDURES
-- =====================================================

DELIMITER //

-- Procedure to get weather data for a district
CREATE PROCEDURE GetDistrictWeather(IN district_name VARCHAR(100))
BEGIN
    SELECT 
        d.district_name,
        wc.*
    FROM weather_cache wc
    JOIN districts d ON wc.district_id = d.id
    WHERE d.district_name = district_name
    AND wc.date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
    ORDER BY wc.date DESC;
END //

-- Procedure to get soil data for a district and crop
CREATE PROCEDURE GetDistrictSoilData(IN district_name VARCHAR(100), IN crop_type VARCHAR(100))
BEGIN
    SELECT 
        d.district_name,
        sd.*
    FROM soil_data sd
    JOIN districts d ON sd.district_id = d.id
    WHERE d.district_name = district_name
    AND sd.crop_type = crop_type
    ORDER BY sd.sample_date DESC
    LIMIT 10;
END //

DELIMITER ;

-- =====================================================
-- CREATE TRIGGERS
-- =====================================================

-- Trigger to update weather cache timestamp
DELIMITER //
CREATE TRIGGER weather_cache_update_trigger
    BEFORE UPDATE ON weather_cache
    FOR EACH ROW
BEGIN
    SET NEW.last_updated = CURRENT_TIMESTAMP;
END //
DELIMITER ;

-- =====================================================
-- GRANT PERMISSIONS (Adjust as needed for your setup)
-- =====================================================

-- Create a dedicated user for the application
-- CREATE USER 'krushibandhu_user'@'localhost' IDENTIFIED BY 'secure_password_here';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON krushibandhu_ai.* TO 'krushibandhu_user'@'localhost';
-- FLUSH PRIVILEGES;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify table creation
SELECT 'Database Setup Complete' as status;
SELECT COUNT(*) as districts_count FROM districts;
SELECT COUNT(*) as soil_data_count FROM soil_data;
SELECT COUNT(*) as weather_cache_count FROM weather_cache;
SELECT COUNT(*) as system_config_count FROM system_config;
