-- =====================================================
-- KrushiBandhu AI - Database Schema Setup (Simplified)
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
    district_name VARCHAR(100) UNIQUE NOT NULL,
    imd_station_id VARCHAR(50) UNIQUE,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    climate_zone VARCHAR(50),
    avg_rainfall_annual DECIMAL(10, 2),
    avg_temperature_annual DECIMAL(5, 2),
    predominant_soil_type VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_district_name (district_name),
    INDEX idx_imd_station (imd_station_id),
    INDEX idx_climate_zone (climate_zone)
);

-- =====================================================
-- 2. SOIL DATA TABLE
-- Stores detailed soil health information from Soil Health Cards
-- =====================================================

CREATE TABLE IF NOT EXISTS soil_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    crop_type VARCHAR(100) NOT NULL,
    soil_type VARCHAR(255),
    ph_level DECIMAL(4, 2),
    organic_carbon_percent DECIMAL(5, 2),
    nitrogen_mg_per_kg DECIMAL(10, 2),
    phosphorus_mg_per_kg DECIMAL(10, 2),
    potassium_mg_per_kg DECIMAL(10, 2),
    calcium_percent DECIMAL(5, 2),
    magnesium_percent DECIMAL(5, 2),
    sulfur_mg_per_kg DECIMAL(10, 2),
    zinc_mg_per_kg DECIMAL(10, 2),
    boron_mg_per_kg DECIMAL(10, 2),
    iron_mg_per_kg DECIMAL(10, 2),
    copper_mg_per_kg DECIMAL(10, 2),
    manganese_mg_per_kg DECIMAL(10, 2),
    fertility_rating VARCHAR(50),
    soil_health_score DECIMAL(5, 2),
    sample_date DATE,
    lab_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    INDEX idx_district_crop (district_id, crop_type),
    INDEX idx_sample_date (sample_date),
    INDEX idx_soil_health_score (soil_health_score)
);

-- =====================================================
-- 3. WEATHER CACHE TABLE
-- Stores processed weather data and forecasts
-- =====================================================

CREATE TABLE IF NOT EXISTS weather_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    date DATE NOT NULL,
    predicted_rainfall DECIMAL(10, 2),
    avg_temperature DECIMAL(5, 2),
    min_temperature DECIMAL(5, 2),
    max_temperature DECIMAL(5, 2),
    humidity_percent DECIMAL(5, 2),
    wind_speed_kmph DECIMAL(5, 2),
    weather_condition VARCHAR(100),
    seven_day_forecast JSON,
    active_warnings JSON,
    data_source VARCHAR(100),
    confidence_score DECIMAL(3, 2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    UNIQUE KEY unique_district_date (district_id, date),
    INDEX idx_date (date),
    INDEX idx_weather_condition (weather_condition)
);

-- =====================================================
-- 4. CROP YIELD HISTORY TABLE
-- Stores historical yield data for model training
-- =====================================================

CREATE TABLE IF NOT EXISTS crop_yield_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    district_id INT NOT NULL,
    crop_type VARCHAR(100) NOT NULL,
    variety VARCHAR(100),
    season VARCHAR(50),
    year INT NOT NULL,
    yield_kg_per_hectare DECIMAL(10, 2),
    area_hectares DECIMAL(10, 2),
    total_production_kg DECIMAL(15, 2),
    rainfall_mm DECIMAL(10, 2),
    avg_temperature DECIMAL(5, 2),
    soil_health_score DECIMAL(5, 2),
    farming_practices JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE CASCADE,
    INDEX idx_district_crop_year (district_id, crop_type, year),
    INDEX idx_year (year),
    INDEX idx_yield (yield_kg_per_hectare)
);

-- =====================================================
-- 5. API LOGS TABLE
-- Tracks API usage and performance
-- =====================================================

CREATE TABLE IF NOT EXISTS api_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255),
    request_method VARCHAR(10),
    response_status INT,
    response_time_ms INT,
    request_size_bytes INT,
    response_size_bytes INT,
    error_message TEXT,
    user_agent TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_api_name (api_name),
    INDEX idx_created_at (created_at),
    INDEX idx_response_status (response_status)
);

-- =====================================================
-- 6. SYSTEM CONFIG TABLE
-- Stores system configuration and settings
-- =====================================================

CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    config_type VARCHAR(50) DEFAULT 'string',
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_config_key (config_key),
    INDEX idx_is_active (is_active)
);

-- =====================================================
-- INSERT INITIAL DATA
-- =====================================================

-- Insert some sample districts (you can expand this list)
INSERT IGNORE INTO districts (district_name, imd_station_id, latitude, longitude, climate_zone) VALUES
('Bhubaneswar', 'IMD_BBSR', 20.2961, 85.8245, 'Tropical'),
('Cuttack', 'IMD_CTK', 20.4625, 85.8829, 'Tropical'),
('Puri', 'IMD_PURI', 19.8134, 85.8315, 'Coastal'),
('Balasore', 'IMD_BLS', 21.4942, 86.9336, 'Coastal'),
('Bhadrak', 'IMD_BDR', 21.0544, 86.5156, 'Coastal'),
('Jagatsinghpur', 'IMD_JSP', 20.2557, 86.1669, 'Coastal'),
('Kendrapara', 'IMD_KDP', 20.5014, 86.4186, 'Coastal'),
('Khordha', 'IMD_KHD', 20.1834, 85.6167, 'Tropical'),
('Nayagarh', 'IMD_NYG', 20.1286, 85.0947, 'Tropical'),
('Ganjam', 'IMD_GJM', 19.3870, 85.0500, 'Coastal');

-- Insert some sample system configuration
INSERT IGNORE INTO system_config (config_key, config_value, config_type, description) VALUES
('api_rate_limit', '1000', 'integer', 'Maximum API requests per hour'),
('weather_cache_hours', '6', 'integer', 'Hours to cache weather data'),
('soil_data_cache_days', '30', 'integer', 'Days to cache soil data'),
('model_retrain_days', '7', 'integer', 'Days between model retraining'),
('default_confidence_threshold', '0.7', 'float', 'Default confidence threshold for predictions');

-- =====================================================
-- VERIFICATION
-- =====================================================

SELECT 'Database Setup Complete' as status;

-- =====================================================
-- 7. USERS TABLE
-- Stores user accounts for authentication
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 7. USERS TABLE
-- Stores user accounts for authentication
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 7. USERS TABLE
-- Stores user accounts for authentication
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);