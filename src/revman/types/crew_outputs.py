"""
Pydantic Output Models for CrewAI Crews

These models define the structured outputs that crews should return.
They match the data structure that's currently extracted via manual parsing
in main.py lines 183-235 (Excel) and 271-278 (Email).

This ensures type safety and automatic validation of crew outputs.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExcelProcessingOutput(BaseModel):
    """
    Output model for Excel Processor Crew

    Matches the data structure currently parsed in main.py:183-235
    """

    excel_output_path: str = Field(
        ...,
        description="Path to the Excel file with formulas added"
    )

    effective_date_iso: str = Field(
        ...,
        description="Effective date in ISO format (YYYY-MM-DD)"
    )

    effective_date_display: str = Field(
        ...,
        description="Effective date in display format (e.g., 'October 13, 2025')"
    )

    price_changes: Dict[str, Any] = Field(
        ...,
        description="Categorized price change data with structure: {category: [items]}"
    )

    validation_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Initial data quality validation results from Excel processing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "excel_output_path": "/path/to/output_formula.xlsx",
                "effective_date_iso": "2025-10-13",
                "effective_date_display": "October 13, 2025",
                "price_changes": {
                    "increases": [
                        {"sku": "ABC123", "old_price": 10.0, "new_price": 12.0}
                    ],
                    "decreases": [],
                    "no_change": []
                },
                "validation_info": {
                    "total_skus": 50,
                    "valid_skus": 48,
                    "warnings": []
                }
            }
        }


class EmailGenerationOutput(BaseModel):
    """
    Output model for Email Builder Crew

    Matches the data structure currently parsed in main.py:271-278
    """

    email_content: str = Field(
        ...,
        description="Generated email body in plain text format"
    )

    email_subject: str = Field(
        ...,
        description="Generated email subject line"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about email generation (word count, sections, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email_content": "Dear Team,\n\nPlease find the price change summary...",
                "email_subject": "TBS Price Change Summary - Effective October 13, 2025",
                "metadata": {
                    "word_count": 250,
                    "sections": ["highlights", "details", "footer"],
                    "generation_timestamp": "2025-11-09T15:30:00"
                }
            }
        }


class ValidationOutput(BaseModel):
    """
    Output model for validation step

    Provides structured validation results
    """

    status: str = Field(
        ...,
        description="Overall validation status: PASS, FAIL, or PASS WITH WARNINGS"
    )

    score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Validation quality score from 0 to 100"
    )

    issues: List[str] = Field(
        default_factory=list,
        description="List of critical issues found (if any)"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="List of non-critical warnings (if any)"
    )

    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional validation details and metrics"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "PASS WITH WARNINGS",
                "score": 85,
                "issues": [],
                "warnings": [
                    "Email exceeds recommended length (300 words)"
                ],
                "details": {
                    "checks_performed": 10,
                    "checks_passed": 9,
                    "checks_warned": 1,
                    "checks_failed": 0
                }
            }
        }
