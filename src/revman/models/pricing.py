"""
Pydantic models for Pricing Analysis data structures.

These models define the data contracts between:
- HistoricalPriceAnalysisTool → PriceForecastingTool → AnomalyDetectionTool

Using Pydantic ensures:
- Type safety and validation
- Clean serialization to/from JSON  
- Self-documenting data structures
- IDE autocomplete and type hints

Note: `output_pydantic` on Tasks uses these models for validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Simplified Model for output_json (SDK-optimized)
# =============================================================================

class PricingAnalysisOutput(BaseModel):
    """
    Simplified flat model for output_json parameter.
    Uses Dict instead of nested Pydantic models for better LLM reliability.

    Note: This is an alternative to AnomalyDetectionResult for testing LLM consistency.
    If LLMs handle AnomalyDetectionResult well, this may not be needed.
    """
    top_10_notable_changes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Top 10 notable price changes. Each dict contains: "
            "sku (str), brand (str), pack_size (int), pack_type (str), "
            "current_price (float), forecasted_price (float), "
            "price_change_dollars (float), forecasted_change_pct (float), "
            "z_score (float), significance (str like '2.3σ')"
        )
    )
    total_anomalies_detected: int = Field(
        description="Total number of anomalies found above threshold"
    )
    threshold_used: float = Field(
        default=1.5,
        description="Sigma threshold used for anomaly detection"
    )
    analysis_date: str = Field(
        description="ISO timestamp of analysis"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "top_10_notable_changes": [
                    {
                        "sku": "Budweiser 24B",
                        "brand": "Budweiser",
                        "pack_size": 24,
                        "pack_type": "Bottles",
                        "current_price": 45.99,
                        "forecasted_price": 48.50,
                        "price_change_dollars": 2.51,
                        "forecasted_change_pct": 5.46,
                        "z_score": 2.3,
                        "significance": "2.3σ"
                    }
                ],
                "total_anomalies_detected": 15,
                "threshold_used": 1.5,
                "analysis_date": "2025-10-13T14:30:00"
            }
        }
    }

