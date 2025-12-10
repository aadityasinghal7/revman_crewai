"""
Pricing Analysis Tools for Historical Price Trend Analysis and Forecasting.

Migrated to ValidatedBaseTool for production-ready error handling and output validation.
All tools now fail-fast on errors instead of swallowing them.

This module contains tools for:
1. Analyzing historical price trends
2. Forecasting future prices
3. Detecting anomalies in price changes
4. Categorizing price changes

Data Flow:
- Tools accept both raw dicts AND Pydantic models for flexibility
- Pydantic models (from revman.models.pricing) are preferred for type safety
- File writes are OPTIONAL - data should flow through main.py orchestration
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from revman.tools.base_tool import ValidatedBaseTool, ToolValidationError
from revman.models.pricing import (
    HistoricalAnalysisResult,
    ForecastResult,
    AnomalyDetectionResult,
)

logger = logging.getLogger(__name__)


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
    file_path: str = Field(
        default="data/input/Historical_price_change_summary_report_vF.xlsx",
        description="Path to the historical price Excel file. Uses default historical file if not specified."
    )
    output_dir: Optional[str] = Field(
        default=None, 
        description="Directory to save analysis results. If None, no file is written."
    )
    save_to_file: bool = Field(
        default=False,
        description="Whether to save results to file. Set True for debugging/fallback."
    )


class HistoricalPriceAnalysisTool(ValidatedBaseTool):
    """
    Analyzes historical price data and calculates week-over-week changes.
    
    Validation:
    - Requires at least 1 SKU to be analyzed
    - Fails if required columns are missing
    """
    name: str = "Historical Price Analyzer"
    description: str = """
    Reads historical price data from Excel file and calculates week-over-week percentage changes
    for each SKU. Returns statistical summary including mean, standard deviation, and all
    week-over-week changes for each SKU.
    
    IMPORTANT: If you provide a file_path that doesn't exist, the tool will automatically try
    the default historical file at 'data/input/Historical_price_change_summary_report_vF.xlsx'.
    """
    args_schema: Type[BaseModel] = HistoricalPriceAnalysisInput

    # Validation configuration
    min_output_items: int = 1
    required_output_keys: List[str] = ["sku_analysis", "total_skus"]
    
    # Default file path for fallback
    DEFAULT_HISTORICAL_FILE: str = "data/input/Historical_price_change_summary_report_vF.xlsx"

    def _execute(
        self, 
        file_path: str, 
        output_dir: Optional[str] = None,
        save_to_file: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze historical price data and calculate week-over-week changes.

        Args:
            file_path: Path to the Excel file
            output_dir: Optional directory to save results (only used if save_to_file=True)
            save_to_file: Whether to write results to disk

        Returns:
            Dict with analysis results (compatible with HistoricalAnalysisResult)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns missing or no data
        """
        # Try the provided path first, fall back to default if not found
        path_to_use = Path(file_path)
        if not path_to_use.exists():
            # Try default path as fallback
            default_path = Path(self.DEFAULT_HISTORICAL_FILE)
            if default_path.exists():
                import logging
                logging.getLogger(__name__).warning(
                    f"Provided path '{file_path}' not found, using default: {default_path}"
                )
                path_to_use = default_path
            else:
                raise FileNotFoundError(
                    f"Historical price file not found: {file_path}. "
                    f"Default file also not found: {self.DEFAULT_HISTORICAL_FILE}"
                )

        df = pd.read_excel(path_to_use)

        # Validate required columns
        required_cols = ['SKU', 'BRAND', 'Pack Size', 'Pack Volume ml', 'Pack Type', 'Week', 'Price']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}. Available: {list(df.columns)}")

        # Parse and clean data
        df['Week'] = pd.to_datetime(df['Week'], errors='coerce')
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        df = df.dropna(subset=['Week', 'Price'])

        if len(df) == 0:
            raise ValueError("No valid data rows after cleaning")

        df = df.sort_values(['SKU', 'Week'])

        # Analyze each SKU
        sku_analysis = {}

        for sku in df['SKU'].unique():
            sku_data = df[df['SKU'] == sku].copy()
            sku_data['Price_Change_Pct'] = sku_data['Price'].pct_change() * 100
            price_changes = sku_data['Price_Change_Pct'].dropna()

            if len(price_changes) > 0:
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

        if len(sku_analysis) == 0:
            raise ValueError("No SKUs had sufficient data for analysis")

        result = {
            'sku_analysis': sku_analysis,
            'total_skus': len(sku_analysis),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Only write to file if explicitly requested (for debugging/fallback)
        if save_to_file:
            save_dir = Path(output_dir) if output_dir else Path("data/output")
            save_dir.mkdir(parents=True, exist_ok=True)
            output_file = save_dir / "historical_analysis_results.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            result['output_file'] = str(output_file)
            logger.info(f"Saved historical analysis to {output_file}")

        return result

    def _count_items(self, result: Dict[str, Any]) -> int:
        """Count SKUs analyzed."""
        return result.get("total_skus", 0)


class PriceForecastingInput(BaseModel):
    """Input schema for PriceForecastingTool"""
    analysis_file_path: Optional[str] = Field(
        default=None,
        description="Path to JSON file with historical analysis (fallback if sku_analysis not provided)"
    )
    sku_analysis: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="SKU analysis data directly - PREFERRED over file path"
    )
    output_dir: Optional[str] = Field(
        default=None, 
        description="Directory to save results. If None, no file is written."
    )
    save_to_file: bool = Field(
        default=False,
        description="Whether to save results to file. Set True for debugging/fallback."
    )


class PriceForecastingTool(ValidatedBaseTool):
    """
    Forecasts next week's price for each SKU using trend-based calculation.
    
    Uses exponential weighted moving average of recent price changes.
    Accepts either file path or direct data input.
    
    Validation:
    - Requires at least 1 SKU forecast
    """
    name: str = "Price Forecaster"
    description: str = """
    Forecasts next week's price for each SKU using simple trend-based calculation.
    Uses exponential weighted moving average of recent price changes to predict future price.
    Can read from a JSON file path OR accept SKU analysis data directly.
    """
    args_schema: Type[BaseModel] = PriceForecastingInput

    # Validation configuration
    min_output_items: int = 1
    required_output_keys: List[str] = ["forecasts", "total_skus_forecasted"]

    def _execute(
        self, 
        analysis_file_path: Optional[str] = None,
        sku_analysis: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        save_to_file: bool = False
    ) -> Dict[str, Any]:
        """
        Forecast next week's price for all SKUs.

        Args:
            analysis_file_path: Path to JSON file (fallback if sku_analysis not provided)
            sku_analysis: Dict with SKU analysis - PREFERRED input method
            output_dir: Optional directory to save results (only used if save_to_file=True)
            save_to_file: Whether to write results to disk

        Returns:
            Dict with forecasts (compatible with ForecastResult)

        Raises:
            FileNotFoundError: If file path needed but doesn't exist
            ValueError: If no valid data to forecast
        """
        # PREFER direct data over file path
        if sku_analysis is None:
            # Fall back to file if no direct data provided
            if analysis_file_path is None:
                analysis_file_path = "data/output/historical_analysis_results.json"
            
            file_path = Path(analysis_file_path)
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Analysis results file not found: {analysis_file_path}. "
                    "Either provide sku_analysis directly or ensure file exists."
                )
            
            logger.info(f"Loading historical analysis from file: {analysis_file_path}")
            with open(file_path, 'r') as f:
                analysis_data = json.load(f)
            
            if 'error' in analysis_data:
                raise ValueError(f"Error in analysis data: {analysis_data.get('error')}")
            
            sku_analysis = analysis_data.get('sku_analysis', {})

        if not sku_analysis:
            raise ValueError("No SKU analysis data available")

        forecasts = {}

        for sku, stats in sku_analysis.items():
            latest_price = safe_float(stats.get('latest_price', 0))
            mean_change = safe_float(stats.get('mean_change_pct', 0))
            std_change = safe_float(stats.get('std_change_pct', 0))

            all_changes_raw = stats.get('all_changes', [])
            all_changes = [safe_float(c) for c in all_changes_raw if c is not None]

            if latest_price == 0:
                continue

            # Calculate forecasted change using exponential weighted moving average
            if len(all_changes) >= 3:
                recent_changes = all_changes[-8:]
                weights = np.exp(np.linspace(-1, 0, len(recent_changes)))
                weights /= weights.sum()
                forecasted_change_pct = float(np.average(recent_changes, weights=weights))
            else:
                forecasted_change_pct = mean_change if len(all_changes) > 0 else 0.0

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

        if len(forecasts) == 0:
            raise ValueError("No SKUs had valid data for forecasting")

        result = {
            'forecasts': forecasts,
            'total_skus_forecasted': len(forecasts),
            'forecast_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'next_week': 'Week of 20th'
        }

        # Only write to file if explicitly requested (for debugging/fallback)
        if save_to_file:
            save_dir = Path(output_dir) if output_dir else Path("data/output")
            save_dir.mkdir(parents=True, exist_ok=True)
            output_file = save_dir / "price_forecasts.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            result['output_file'] = str(output_file)
            logger.info(f"Saved price forecasts to {output_file}")

        return result

    def _count_items(self, result: Dict[str, Any]) -> int:
        """Count SKUs forecasted."""
        return result.get("total_skus_forecasted", 0)


class AnomalyDetectionInput(BaseModel):
    """Input schema for AnomalyDetectionTool"""
    forecasts_file_path: Optional[str] = Field(
        default=None,
        description="Path to JSON file with forecasts (fallback if forecasts not provided)"
    )
    forecasts: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Forecasts data directly - PREFERRED over file path"
    )
    threshold_sigma: float = Field(
        default=1.5, 
        description="Number of standard deviations for anomaly threshold"
    )
    output_dir: Optional[str] = Field(
        default=None, 
        description="Directory to save results. If None, no file is written."
    )
    save_to_file: bool = Field(
        default=False,
        description="Whether to save results to file. Set True for debugging/fallback."
    )


class AnomalyDetectionTool(ValidatedBaseTool):
    """
    Identifies SKUs with most significant price changes.
    
    Returns top 10 SKUs ranked by statistical significance (z-score).
    Accepts either file path or direct data input (direct data preferred).
    
    Validation:
    - Requires at least 1 anomaly detected (or valid analysis)
    """
    name: str = "Price Anomaly Detector"
    description: str = """
    Identifies the top 10 SKUs with most significant price changes by comparing forecasted change
    against historical volatility. Always returns exactly 10 SKUs ranked by statistical significance
    (measured in standard deviations from historical mean), regardless of threshold.
    Can read from a JSON file path OR accept forecast data directly.
    """
    args_schema: Type[BaseModel] = AnomalyDetectionInput

    # Validation configuration
    required_output_keys: List[str] = ["top_10_notable_changes", "total_anomalies_detected"]

    def _execute(
        self, 
        forecasts_file_path: Optional[str] = None,
        forecasts: Optional[Dict[str, Any]] = None,
        threshold_sigma: float = 1.5,
        output_dir: Optional[str] = None,
        save_to_file: bool = False
    ) -> Dict[str, Any]:
        """
        Detect the top 10 SKUs with most significant forecasted price changes.

        Args:
            forecasts_file_path: Path to JSON file (fallback if forecasts not provided)
            forecasts: Dict with forecast data - PREFERRED input method
            threshold_sigma: Standard deviation threshold
            output_dir: Optional directory to save results (only used if save_to_file=True)
            save_to_file: Whether to write results to disk

        Returns:
            Dict with top 10 notable changes (compatible with AnomalyDetectionResult)

        Raises:
            FileNotFoundError: If file path needed but doesn't exist
            ValueError: If no valid forecast data
        """
        # PREFER direct data over file path
        if forecasts is None:
            if forecasts_file_path is None:
                forecasts_file_path = "data/output/price_forecasts.json"
            
            file_path = Path(forecasts_file_path)
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Forecast results file not found: {forecasts_file_path}. "
                    "Either provide forecasts directly or ensure file exists."
                )
            
            logger.info(f"Loading forecasts from file: {forecasts_file_path}")
            with open(file_path, 'r') as f:
                forecast_data = json.load(f)
            
            if 'error' in forecast_data:
                raise ValueError(f"Error in forecast data: {forecast_data.get('error')}")
            
            forecasts = forecast_data.get('forecasts', {})

        if not forecasts:
            raise ValueError("No forecast data available")

        anomalies = []

        for sku, forecast in forecasts.items():
            forecasted_change = safe_float(forecast.get('forecasted_change_pct', 0))
            historical_mean = safe_float(forecast.get('historical_mean_change_pct', 0))
            historical_std = safe_float(forecast.get('historical_std_change_pct', 0))
            current_price = safe_float(forecast.get('current_price', 0))
            forecasted_price = safe_float(forecast.get('forecasted_price', 0))

            if historical_std > 0:
                z_score = abs((forecasted_change - historical_mean) / historical_std)

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

        # Sort by z-score and take top 10
        anomalies.sort(key=lambda x: x['z_score'], reverse=True)
        top_10_anomalies = anomalies[:10]

        result = {
            'top_10_notable_changes': top_10_anomalies,
            'total_anomalies_detected': len(anomalies),
            'threshold_used': threshold_sigma,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Only write to file if explicitly requested (for debugging/fallback)
        if save_to_file:
            save_dir = Path(output_dir) if output_dir else Path("data/output")
            save_dir.mkdir(parents=True, exist_ok=True)
            output_file = save_dir / "pricing_anomalies.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            result['output_file'] = str(output_file)
            logger.info(f"Saved pricing anomalies to {output_file}")

        return result

    def _count_items(self, result: Dict[str, Any]) -> int:
        """Count anomalies detected."""
        return result.get("total_anomalies_detected", 0)


class PriceCategorizationInput(BaseModel):
    """Input schema for PriceCategorizationTool"""
    file_path: str = Field(..., description="Path to the price change Excel file (formula Excel) with columns: Product Name, Pack Size, Type of Sale, Old Price, New Price")


class PriceCategorizationTool(ValidatedBaseTool):
    """
    Categorizes all products into 5 categories based on Type of Sale and price ratios.
    
    Categories:
    1. Licensee Changes (Type of Sale = "TBS - Licensee")
    2. New SKUs (Type of Sale = "New SKU")
    3. Permanent Changes (TBS - Retail Price with 96% <= price_ratio <= 104%)
    4. Begin LTO (TBS - Retail Price with price_ratio < 96%)
    5. End LTO (TBS - Retail Price with price_ratio > 104%)
    
    Validation:
    - Requires at least 1 product to be categorized
    """
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
    args_schema: Type[BaseModel] = PriceCategorizationInput

    # Validation configuration
    min_output_items: int = 1
    required_output_keys: List[str] = ["total_products", "categorization_summary"]

    def _execute(self, file_path: str) -> Dict[str, Any]:
        """
        Categorize all price changes based on Type of Sale and price ratios.

        Args:
            file_path: Path to the Excel file with price change data

        Returns:
            Dict with products organized by category

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required columns missing or no data
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Price change file not found: {file_path}")

        # Read Excel file - skip first 7 rows (TBS report structure)
        df = pd.read_excel(file_path, skiprows=7)

        # Clean column names
        df.columns = df.columns.str.strip().str.replace('\n', ' ')

        # Remove completely empty rows
        df = df.dropna(how='all')

        if len(df) == 0:
            raise ValueError("No data rows found in Excel file")

        # Ensure required columns exist
        required_cols = ['Product Name', 'Pack Size', 'Type of Sale', 'Old Price', 'New Price']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}. Available: {list(df.columns)}")

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
                if old_price > 0:
                    price_ratio = (new_price / old_price) * 100
                    product_entry['price_ratio_pct'] = round(price_ratio, 2)

                    if price_ratio < 96:
                        begin_lto.append(product_entry)
                    elif price_ratio > 104:
                        end_lto.append(product_entry)
                    else:
                        permanent_changes.append(product_entry)
                else:
                    product_entry['price_ratio_pct'] = 0
                    product_entry['note'] = 'Zero old price - categorized as permanent change'
                    permanent_changes.append(product_entry)

        total_categorized = (
            len(licensee_changes) + len(new_skus) + len(permanent_changes) +
            len(begin_lto) + len(end_lto)
        )

        if total_categorized == 0:
            raise ValueError(
                f"No products could be categorized. Processed {len(df)} rows but "
                f"none matched expected Type of Sale values."
            )

        return {
            'licensee_changes': licensee_changes,
            'new_skus': new_skus,
            'permanent_changes': permanent_changes,
            'begin_lto': begin_lto,
            'end_lto': end_lto,
            'total_products': total_categorized,
            'categorization_summary': {
                'licensee_changes_count': len(licensee_changes),
                'new_skus_count': len(new_skus),
                'permanent_changes_count': len(permanent_changes),
                'begin_lto_count': len(begin_lto),
                'end_lto_count': len(end_lto)
            },
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _count_items(self, result: Dict[str, Any]) -> int:
        """Count total products categorized."""
        return result.get("total_products", 0)
