"""
Pydantic models for Pricing Analysis data structures.

These models define the data contracts between:
- HistoricalPriceAnalysisTool → PriceForecastingTool → AnomalyDetectionTool

Using Pydantic ensures:
- Type safety and validation
- Clean serialization to/from JSON
- Self-documenting data structures
- IDE autocomplete and type hints
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Historical Analysis Models
# =============================================================================

class SKUAnalysis(BaseModel):
    """Analysis results for a single SKU's historical price data."""
    
    brand: str = Field(..., description="Brand name")
    pack_size: Optional[int] = Field(None, description="Pack size (number of units)")
    pack_volume_ml: Optional[float] = Field(None, description="Volume per unit in mL")
    pack_type: str = Field(..., description="Package type (Cans, Bottles, etc.)")
    total_weeks: int = Field(..., description="Total weeks of data available")
    total_changes: int = Field(..., description="Number of week-over-week changes calculated")
    mean_change_pct: Optional[float] = Field(0.0, description="Mean week-over-week change percentage")
    std_change_pct: Optional[float] = Field(0.0, description="Standard deviation of changes")
    min_change_pct: Optional[float] = Field(0.0, description="Minimum change percentage observed")
    max_change_pct: Optional[float] = Field(0.0, description="Maximum change percentage observed")
    latest_price: Optional[float] = Field(0.0, description="Most recent price")
    latest_week: str = Field(..., description="Date of most recent price (YYYY-MM-DD)")
    all_changes: List[Optional[float]] = Field(default_factory=list, description="All historical changes")
    
    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class HistoricalAnalysisResult(BaseModel):
    """Complete result from HistoricalPriceAnalysisTool."""
    
    sku_analysis: Dict[str, SKUAnalysis] = Field(
        ..., 
        description="SKU name → analysis results mapping"
    )
    total_skus: int = Field(..., description="Total number of SKUs analyzed")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        description="Timestamp of analysis"
    )
    output_file: Optional[str] = Field(None, description="Path to saved output file (if any)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool compatibility."""
        return {
            "sku_analysis": {k: v.model_dump() for k, v in self.sku_analysis.items()},
            "total_skus": self.total_skus,
            "analysis_date": self.analysis_date,
            "output_file": self.output_file,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoricalAnalysisResult":
        """Create from dictionary (tool output)."""
        sku_analysis = {}
        for sku_name, sku_data in data.get("sku_analysis", {}).items():
            if isinstance(sku_data, SKUAnalysis):
                sku_analysis[sku_name] = sku_data
            else:
                # Sanitize data before creating model
                # Filter out None values from all_changes list
                if 'all_changes' in sku_data and sku_data['all_changes']:
                    sku_data['all_changes'] = [
                        x if x is not None else 0.0 
                        for x in sku_data['all_changes']
                    ]
                # Replace None with 0.0 for numeric fields
                for field in ['mean_change_pct', 'std_change_pct', 'min_change_pct', 
                              'max_change_pct', 'latest_price']:
                    if field in sku_data and sku_data[field] is None:
                        sku_data[field] = 0.0
                sku_analysis[sku_name] = SKUAnalysis(**sku_data)
        
        return cls(
            sku_analysis=sku_analysis,
            total_skus=data.get("total_skus", len(sku_analysis)),
            analysis_date=data.get("analysis_date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            output_file=data.get("output_file"),
        )


# =============================================================================
# Price Forecasting Models
# =============================================================================

class SKUForecast(BaseModel):
    """Forecast results for a single SKU."""
    
    brand: str = Field(..., description="Brand name")
    pack_size: Optional[int] = Field(None, description="Pack size")
    pack_volume_ml: Optional[float] = Field(None, description="Volume in mL")
    pack_type: str = Field(..., description="Package type")
    current_price: float = Field(..., description="Current price")
    current_week: str = Field(..., description="Current week date")
    forecasted_price: float = Field(..., description="Predicted price for next week")
    forecasted_change_pct: float = Field(..., description="Predicted change percentage")
    historical_mean_change_pct: float = Field(..., description="Historical mean change")
    historical_std_change_pct: float = Field(..., description="Historical standard deviation")
    
    class Config:
        extra = "allow"


class ForecastResult(BaseModel):
    """Complete result from PriceForecastingTool."""
    
    forecasts: Dict[str, SKUForecast] = Field(
        ..., 
        description="SKU name → forecast results mapping"
    )
    total_skus_forecasted: int = Field(..., description="Number of SKUs forecasted")
    forecast_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        description="Timestamp of forecast"
    )
    next_week: str = Field(default="", description="Target week for forecast")
    output_file: Optional[str] = Field(None, description="Path to saved output file (if any)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for tool compatibility."""
        return {
            "forecasts": {k: v.model_dump() for k, v in self.forecasts.items()},
            "total_skus_forecasted": self.total_skus_forecasted,
            "forecast_date": self.forecast_date,
            "next_week": self.next_week,
            "output_file": self.output_file,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastResult":
        """Create from dictionary (tool output)."""
        forecasts = {}
        for sku_name, forecast_data in data.get("forecasts", {}).items():
            if isinstance(forecast_data, SKUForecast):
                forecasts[sku_name] = forecast_data
            else:
                forecasts[sku_name] = SKUForecast(**forecast_data)
        
        return cls(
            forecasts=forecasts,
            total_skus_forecasted=data.get("total_skus_forecasted", len(forecasts)),
            forecast_date=data.get("forecast_date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            next_week=data.get("next_week", ""),
            output_file=data.get("output_file"),
        )


# =============================================================================
# Anomaly Detection Models
# =============================================================================

class NotableChange(BaseModel):
    """A single notable/anomalous price change."""
    
    sku: str = Field(..., description="SKU identifier")
    brand: str = Field(..., description="Brand name")
    pack_size: Optional[int] = Field(None, description="Pack size")
    pack_volume_ml: Optional[float] = Field(None, description="Volume in mL")
    pack_type: str = Field(..., description="Package type")
    current_price: float = Field(..., description="Current price")
    forecasted_price: float = Field(..., description="Forecasted price")
    price_change_dollars: float = Field(..., description="Change in dollars")
    forecasted_change_pct: float = Field(..., description="Change percentage")
    historical_mean_change_pct: float = Field(..., description="Historical mean")
    historical_std_change_pct: float = Field(..., description="Historical std dev")
    z_score: float = Field(..., description="Statistical significance (z-score)")
    significance: str = Field(..., description="Human-readable significance (e.g., '2.3σ')")
    
    class Config:
        extra = "allow"


class AnomalyDetectionResult(BaseModel):
    """Complete result from AnomalyDetectionTool."""
    
    top_10_notable_changes: List[NotableChange] = Field(
        ..., 
        description="Top 10 most statistically significant changes"
    )
    total_anomalies_detected: int = Field(..., description="Total anomalies found")
    threshold_used: float = Field(default=1.5, description="Sigma threshold used")
    analysis_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        description="Timestamp of analysis"
    )
    output_file: Optional[str] = Field(None, description="Path to saved output file (if any)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "top_10_notable_changes": [c.model_dump() for c in self.top_10_notable_changes],
            "total_anomalies_detected": self.total_anomalies_detected,
            "threshold_used": self.threshold_used,
            "analysis_date": self.analysis_date,
            "output_file": self.output_file,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnomalyDetectionResult":
        """Create from dictionary (tool output or JSON)."""
        changes = []
        for change_data in data.get("top_10_notable_changes", []):
            if isinstance(change_data, NotableChange):
                changes.append(change_data)
            else:
                changes.append(NotableChange(**change_data))
        
        return cls(
            top_10_notable_changes=changes,
            total_anomalies_detected=data.get("total_anomalies_detected", len(changes)),
            threshold_used=data.get("threshold_used", 1.5),
            analysis_date=data.get("analysis_date", datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            output_file=data.get("output_file"),
        )
