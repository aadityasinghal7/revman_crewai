"""
Pydantic models for Excel Processing data structures.

These models define the data contracts for:
- ExcelProcessorCrew task outputs
- Data flow between Excel processing tasks

Using Pydantic ensures:
- Type safety and validation
- Clean serialization to/from JSON  
- Self-documenting data structures
- SDK output_pydantic compatibility
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Simplified Model for output_json (SDK-optimized)
# =============================================================================

class PriceCategorizationOutput(BaseModel):
    """
    Simplified flat model for output_json parameter.
    LLMs can reliably format this structure.

    Each product entry is a formatted string: "Product PackSize +/-$X.XX to $YY.YY"
    This flat structure is easier for LLMs to generate consistently.
    """
    licensee_changes: List[str] = Field(
        default_factory=list,
        description="Products with Type of Sale = 'TBS - Licensee'. Format: 'Product PackSize +/-$X.XX to $YY.YY'"
    )
    new_skus: List[str] = Field(
        default_factory=list,
        description="Products with Type of Sale = 'New SKU'. Same format as above."
    )
    permanent_changes: List[str] = Field(
        default_factory=list,
        description="Retail products with 96-104% price ratio. Same format."
    )
    begin_lto: List[str] = Field(
        default_factory=list,
        description="Retail products with <96% price ratio (price decrease). Same format."
    )
    end_lto: List[str] = Field(
        default_factory=list,
        description="LTO price products (price increase). Same format."
    )
    total_products: int = Field(
        description="Total number of products categorized"
    )
    effective_date_iso: str = Field(
        description="Effective date in YYYY-MM-DD format"
    )
    effective_date_display: str = Field(
        description="Effective date in 'Month DD, YYYY' format"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "licensee_changes": ["Budweiser 24B -$2.00 to $43.99"],
                "new_skus": ["Corona Light 12C +$0.00 to $28.99"],
                "permanent_changes": ["Bud Light 30C +$1.50 to $47.49"],
                "begin_lto": ["Stella Artois 24B -$5.50 to $40.99"],
                "end_lto": ["Miller Lite 15C +$3.00 to $32.99"],
                "total_products": 108,
                "effective_date_iso": "2025-10-13",
                "effective_date_display": "October 13, 2025"
            }
        }
    }
