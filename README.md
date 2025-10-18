# Odisha Crop Yield Forecaster

A simple, user-friendly web application that helps Odisha farmers predict crop yields based on location and weather conditions.

## Features

- **Simple Interface**: Clean, intuitive design perfect for farmers who may not be tech-savvy
- **District Selection**: Choose from all major Odisha districts
- **Crop Selection**: Support for common crops like Paddy, Maize, Mustard, Wheat, etc.
- **Weather Input**: Interactive sliders for rainfall and temperature
- **Yield Prediction**: AI-powered predictions with confidence ranges
- **Mobile-Friendly**: Responsive design that works on all devices

## How It Works

1. **Select Your District**: Choose your farming location from the dropdown
2. **Choose Your Crop**: Select the crop you're planning to grow
3. **Set Weather Conditions**: Adjust expected rainfall and temperature using sliders
4. **Get Prediction**: Click "Predict My Yield" to get your crop yield forecast

## Prediction Results

The app provides:
- **Predicted Yield**: Main prediction in kg/hectare
- **Historical Comparison**: How your prediction compares to district averages
- **Confidence Range**: Likely yield range based on model confidence
- **Key Factors**: Important factors influencing the prediction

## Technology Stack

- **Frontend**: React + TypeScript + Vite
- **UI Components**: Radix UI + Tailwind CSS
- **Icons**: Lucide React
- **Styling**: Tailwind CSS with custom gradients

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open your browser and visit `http://localhost:5173`

## Future Enhancements

- Integration with real ML model (currently uses mock predictions)
- Historical data visualization
- Weather API integration
- Multi-language support (Odia, Hindi, English)
- Export predictions to PDF

## For Farmers

This tool is designed to help you make informed decisions about your crops. The predictions are based on historical data and weather patterns, but actual yields may vary due to many factors including soil quality, farming practices, and unexpected weather events.

Always consult with local agricultural experts for the best farming advice.
