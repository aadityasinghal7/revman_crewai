"""
Pricing Analysis Tools for Historical Price Trend Analysis and Forecasting.

This module contains tools for:
1. Analyzing historical price trends
2. Forecasting future prices
3. Detecting anomalies in price changes
"""

import json
import pandas as pd
import numpy as np
from typing import Any
from datetime import datetime, timedelta
from pathlib import Path
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def sanitize_float(value: float) -> float | None:
    """
    Sanitize float values to handle NaN and Inf for JSON serialization.

    Args:
        value: Float value to sanitize

    Returns:
        The value if valid, 0.0 if NaN, None if Inf/-Inf
    """
    if pd.isna(value) or np.isnan(value):
        return 0.0  # Replace NaN with 0.0
    if np.isinf(value):
        return None  # Replace Inf/-Inf with None
    return float(value)


def sanitize_list(values: list) -> list:
    """
    Sanitize a list of float values for JSON serialization.

    Args:
        values: List of float values

    Returns:
        List with NaN/Inf values replaced
    """
    return [sanitize_float(v) if isinstance(v, (float, np.floating)) else v for v in values]


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float, handling strings and None.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    if value is None:
        return default
    try:
        result = float(value)
        # Check for NaN/Inf after conversion
        if np.isnan(result) or np.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


class HistoricalPriceAnalysisInput(BaseModel):
    """Input schema for HistoricalPriceAnalysisTool"""
    file_path: str = Field(..., description="Path to the historical price Excel file")


class HistoricalPriceAnalysisTool(BaseTool):
    name: str = "Historical Price Analyzer"
    description: str = """
    Reads historical price data from Excel file and calculates week-over-week percentage changes
    for each SKU. Returns statistical summary including mean, standard deviation, and all
    week-over-week changes for each SKU.
    """
    args_schema: type[BaseModel] = HistoricalPriceAnalysisInput

    def _run(self, file_path: str) -> str:
        """
        Analyze historical price data and calculate week-over-week changes.

        Args:
            file_path: Path to the Excel file with columns: SKU, BRAND, Pack Size,
                      Pack Volume ml, Pack Type, Week, Price

        Returns:
            JSON string containing:
            - sku_analysis: Dict with SKU as key and statistics as value
            - total_skus: Number of unique SKUs analyzed
        """
        try:
            # Validate file path exists
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Historical price file not found: {file_path}")

            # Read Excel file
            df = pd.read_excel(file_path)

            # Ensure required columns exist
            required_cols = ['SKU', 'BRAND', 'Pack Size', 'Pack Volume ml', 'Pack Type', 'Week', 'Price']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return json.dumps({
                    "error": f"Missing required columns: {missing_cols}",
                    "available_columns": list(df.columns)
                })

            # Convert Week to datetime for proper sorting
            df['Week'] = pd.to_datetime(df['Week'], errors='coerce')

            # Convert Price to numeric, coercing errors (like "Delisted" strings) to NaN
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

            # Remove rows with invalid dates or prices (including string prices now converted to NaN)
            df = df.dropna(subset=['Week', 'Price'])

            # Sort by SKU and Week
            df = df.sort_values(['SKU', 'Week'])

            # Calculate week-over-week price changes
            sku_analysis = {}

            for sku in df['SKU'].unique():
                sku_data = df[df['SKU'] == sku].copy()

                # Calculate percentage change week over week
                sku_data['Price_Change_Pct'] = sku_data['Price'].pct_change() * 100

                # Remove first row (NaN change)
                price_changes = sku_data['Price_Change_Pct'].dropna()

                if len(price_changes) > 0:
                    # Get SKU details (from first row)
                    sku_info = sku_data.iloc[0]

                    sku_analysis[sku] = {
                        'brand': str(sku_info['BRAND']),
                        'pack_size': int(sku_info['Pack Size']) if pd.notna(sku_info['Pack Size']) else None,
                        'pack_volume_ml': float(sku_info['Pack Volume ml']) if pd.notna(sku_info['Pack Volume ml']) else None,
                        'pack_type': str(sku_info['Pack Type']),
                        'total_weeks': int(len(sku_data)),
                        'total_changes': int(len(price_changes)),
                        'mean_change_pct': sanitize_float(price_changes.mean()),
                        'std_change_pct': sanitize_float(price_changes.std()),
                        'min_change_pct': sanitize_float(price_changes.min()),
                        'max_change_pct': sanitize_float(price_changes.max()),
                        'latest_price': sanitize_float(sku_data.iloc[-1]['Price']),
                        'latest_week': sku_data.iloc[-1]['Week'].strftime('%Y-%m-%d'),
                        'all_changes': sanitize_list(price_changes.tolist())
                    }

            result = {
                'sku_analysis': sku_analysis,
                'total_skus': len(sku_analysis),
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Write results to file for next tool to read
            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "historical_analysis_results.json"

            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            # Also return JSON string for backward compatibility
            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error analyzing historical prices: {str(e)}",
                "file_path": file_path
            })

    def tool(self):
        """Return self for CrewAI compatibility"""
        return self


class PriceForecastingInput(BaseModel):
    """Input schema for PriceForecastingTool"""
    analysis_file_path: str = Field(
        default="data/output/historical_analysis_results.json",
        description="Path to the JSON file containing historical analysis results from HistoricalPriceAnalysisTool"
    )


class PriceForecastingTool(BaseTool):
    name: str = "Price Forecaster"
    description: str = """
    Forecasts next week's price for each SKU using simple trend-based calculation.
    Uses exponential weighted moving average of recent price changes to predict future price.
    Reads analysis results from the JSON file created by HistoricalPriceAnalysisTool.
    """
    args_schema: type[BaseModel] = PriceForecastingInput

    def _run(self, analysis_file_path: str = "data/output/historical_analysis_results.json") -> str:
        """
        Forecast next week's price for all SKUs.

        Args:
            analysis_file_path: Path to JSON file from HistoricalPriceAnalysisTool

        Returns:
            JSON string containing forecasted prices and changes for each SKU
        """
        try:
            # Read analysis results from file
            file_path = Path(analysis_file_path)
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Analysis results file not found: {analysis_file_path}. "
                    "Make sure HistoricalPriceAnalysisTool has been run first."
                )

            with open(file_path, 'r') as f:
                analysis_data = json.load(f)

            if 'error' in analysis_data:
                raise ValueError(f"Received error from previous tool: {analysis_data.get('error', 'Unknown error')}")

            sku_analysis = analysis_data.get('sku_analysis', {})

            forecasts = {}

            for sku, stats in sku_analysis.items():
                # Use safe_float to handle potential string values or None
                latest_price = safe_float(stats.get('latest_price', 0))
                mean_change = safe_float(stats.get('mean_change_pct', 0))
                std_change = safe_float(stats.get('std_change_pct', 0))

                # Safely convert all_changes list, filtering out None values
                all_changes_raw = stats.get('all_changes', [])
                all_changes = [safe_float(c) for c in all_changes_raw if c is not None]

                # Skip if we don't have valid price data
                if latest_price == 0:
                    continue

                # Use exponential weighted moving average of recent changes
                # Give more weight to recent price changes
                if len(all_changes) >= 3:
                    # Use last 8 weeks or all available, whichever is smaller
                    recent_changes = all_changes[-8:]

                    # Calculate exponential weighted average (more weight to recent)
                    weights = np.exp(np.linspace(-1, 0, len(recent_changes)))
                    weights /= weights.sum()

                    forecasted_change_pct = float(np.average(recent_changes, weights=weights))
                else:
                    # If not enough data, use mean
                    forecasted_change_pct = mean_change if len(all_changes) > 0 else 0.0

                # Calculate forecasted price
                forecasted_price = latest_price * (1 + forecasted_change_pct / 100)

                forecasts[sku] = {
                    'brand': stats.get('brand', 'Unknown'),
                    'pack_size': stats.get('pack_size'),
                    'pack_volume_ml': stats.get('pack_volume_ml'),
                    'pack_type': stats.get('pack_type', 'Unknown'),
                    'current_price': round(latest_price, 2),
                    'current_week': stats.get('latest_week', ''),
                    'forecasted_price': round(forecasted_price, 2),
                    'forecasted_change_pct': round(forecasted_change_pct, 2),
                    'historical_mean_change_pct': round(mean_change, 2),
                    'historical_std_change_pct': round(std_change, 2)
                }

            result = {
                'forecasts': forecasts,
                'total_skus_forecasted': len(forecasts),
                'forecast_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'next_week': 'Week of 20th'  # Based on requirement
            }

            # Write results to file for next tool to read
            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "price_forecasts.json"

            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error forecasting prices: {str(e)}"
            })

    def tool(self):
        """Return self for CrewAI compatibility"""
        return self


class AnomalyDetectionInput(BaseModel):
    """Input schema for AnomalyDetectionTool"""
    forecasts_file_path: str = Field(
        default="data/output/price_forecasts.json",
        description="Path to the JSON file containing price forecasts from PriceForecastingTool"
    )
    threshold_sigma: float = Field(1.5, description="Number of standard deviations to consider as anomaly (default: 1.5)")


class AnomalyDetectionTool(BaseTool):
    name: str = "Price Anomaly Detector"
    description: str = """
    Identifies the top 10 SKUs with most significant price changes by comparing forecasted change
    against historical volatility. Always returns exactly 10 SKUs ranked by statistical significance
    (measured in standard deviations from historical mean), regardless of threshold.
    Reads forecast results from the JSON file created by PriceForecastingTool.
    """
    args_schema: type[BaseModel] = AnomalyDetectionInput

    def _run(self, forecasts_file_path: str = "data/output/price_forecasts.json", threshold_sigma: float = 1.5) -> str:
        """
        Detect the top 10 SKUs with most significant forecasted price changes.

        Args:
            forecasts_file_path: Path to JSON file from PriceForecastingTool
            threshold_sigma: (Deprecated - no longer used for filtering) Previously used as minimum threshold

        Returns:
            JSON string with top 10 SKUs ranked by statistical significance (z-score).
            Always returns exactly 10 SKUs regardless of threshold value.
        """
        try:
            # Read forecast results from file
            file_path = Path(forecasts_file_path)
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Forecast results file not found: {forecasts_file_path}. "
                    "Make sure PriceForecastingTool has been run first."
                )

            with open(file_path, 'r') as f:
                forecast_data = json.load(f)

            if 'error' in forecast_data:
                raise ValueError(f"Received error from previous tool: {forecast_data.get('error', 'Unknown error')}")

            forecasts = forecast_data.get('forecasts', {})

            anomalies = []

            for sku, forecast in forecasts.items():
                # Use safe_float to handle potential string values or None
                forecasted_change = safe_float(forecast.get('forecasted_change_pct', 0))
                historical_mean = safe_float(forecast.get('historical_mean_change_pct', 0))
                historical_std = safe_float(forecast.get('historical_std_change_pct', 0))
                current_price = safe_float(forecast.get('current_price', 0))
                forecasted_price = safe_float(forecast.get('forecasted_price', 0))

                # Avoid division by zero
                if historical_std > 0:
                    # Calculate z-score (number of standard deviations from mean)
                    z_score = abs((forecasted_change - historical_mean) / historical_std)

                    # Add all SKUs with valid z-scores (no threshold filtering)
                    anomalies.append({
                        'sku': sku,
                        'brand': forecast.get('brand', 'Unknown'),
                        'pack_size': forecast.get('pack_size'),
                        'pack_volume_ml': forecast.get('pack_volume_ml'),
                        'pack_type': forecast.get('pack_type', 'Unknown'),
                        'current_price': round(current_price, 2),
                        'forecasted_price': round(forecasted_price, 2),
                        'price_change_dollars': round(forecasted_price - current_price, 2),
                        'forecasted_change_pct': round(forecasted_change, 2),
                        'historical_mean_change_pct': round(historical_mean, 2),
                        'historical_std_change_pct': round(historical_std, 2),
                        'z_score': round(z_score, 2),
                        'significance': f"{z_score:.1f}σ"
                    })

            # Sort by z-score (most significant first) and take top 10
            anomalies.sort(key=lambda x: x['z_score'], reverse=True)
            top_10_anomalies = anomalies[:10]

            result = {
                'top_10_notable_changes': top_10_anomalies,
                'total_anomalies_detected': len(anomalies),
                'threshold_used': threshold_sigma,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Write results to file for main.py to read
            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "pricing_anomalies.json"

            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error detecting anomalies: {str(e)}"
            })

    def tool(self):
        """Return self for CrewAI compatibility"""
        return self


class PriceCategorizationInput(BaseModel):
    """Input schema for PriceCategorizationTool"""
    file_path: str = Field(..., description="Path to the price change Excel file (formula Excel) with columns: Product Name, Pack Size, Type of Sale, Old Price, New Price")


class PriceCategorizationTool(BaseTool):
    name: str = "Price Categorizer"
    description: str = """
    Reads price change data from Excel file and categorizes all products into 5 categories:
    1. Licensee Changes (Type of Sale = "TBS - Licensee")
    2. New SKUs (Type of Sale = "New SKU")
    3. Permanent Changes (TBS - Retail Price with 96% <= price_ratio <= 104%)
    4. Begin LTO (TBS - Retail Price with price_ratio < 96%)
    5. End LTO (TBS - Retail Price with price_ratio > 104%)

    Returns all products pre-categorized in a flat JSON structure.
    """
    args_schema: type[BaseModel] = PriceCategorizationInput

    def _run(self, file_path: str) -> str:
        """
        Categorize all price changes based on Type of Sale and price ratios.

        Args:
            file_path: Path to the Excel file with price change data

        Returns:
            JSON string containing all products organized by category
        """
        try:
            # Validate file path exists
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Price change file not found: {file_path}")

            # Read Excel file - skip first 7 rows (TBS report structure)
            df = pd.read_excel(file_path, skiprows=7)

            # Clean column names (remove whitespace, newlines)
            df.columns = df.columns.str.strip().str.replace('\n', ' ')

            # Remove completely empty rows
            df = df.dropna(how='all')

            # Ensure required columns exist
            required_cols = ['Product Name', 'Pack Size', 'Type of Sale', 'Old Price', 'New Price']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return json.dumps({
                    "error": f"Missing required columns: {missing_cols}",
                    "available_columns": list(df.columns)
                })

            # Initialize category lists
            licensee_changes = []
            new_skus = []
            permanent_changes = []
            begin_lto = []
            end_lto = []

            # Process each row
            for idx, row in df.iterrows():
                product = str(row['Product Name']).strip()
                pack_size = str(row['Pack Size']).strip()
                type_of_sale = str(row['Type of Sale']).strip()
                old_price = safe_float(row['Old Price'])
                new_price = safe_float(row['New Price'])

                # Create product entry
                product_entry = {
                    'product': product,
                    'pack_size': pack_size,
                    'old_price': round(old_price, 2),
                    'new_price': round(new_price, 2),
                    'price_change': round(new_price - old_price, 2)
                }

                # Categorize based on Type of Sale
                if type_of_sale == "TBS - Licensee":
                    licensee_changes.append(product_entry)

                elif type_of_sale == "New SKU":
                    new_skus.append(product_entry)

                elif type_of_sale == "TBS – Retail Price" or type_of_sale == "TBS - Retail Price":
                    # Calculate price ratio percentage: (new_price / old_price) * 100
                    if old_price > 0:
                        price_ratio = (new_price / old_price) * 100
                        product_entry['price_ratio_pct'] = round(price_ratio, 2)

                        # Categorize based on ratio thresholds
                        if price_ratio < 96:
                            begin_lto.append(product_entry)
                        elif price_ratio > 104:
                            end_lto.append(product_entry)
                        else:  # 96 <= price_ratio <= 104
                            permanent_changes.append(product_entry)
                    else:
                        # Handle edge case of zero old price
                        product_entry['price_ratio_pct'] = 0
                        product_entry['note'] = 'Zero old price - categorized as permanent change'
                        permanent_changes.append(product_entry)

            # Build result
            result = {
                'licensee_changes': licensee_changes,
                'new_skus': new_skus,
                'permanent_changes': permanent_changes,
                'begin_lto': begin_lto,
                'end_lto': end_lto,
                'total_products': len(df),
                'categorization_summary': {
                    'licensee_changes_count': len(licensee_changes),
                    'new_skus_count': len(new_skus),
                    'permanent_changes_count': len(permanent_changes),
                    'begin_lto_count': len(begin_lto),
                    'end_lto_count': len(end_lto)
                },
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Write results to file for agent to read
            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "price_categories.json"

            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error categorizing prices: {str(e)}",
                "file_path": file_path
            })

    def tool(self):
        """Return self for CrewAI compatibility"""
        return self
