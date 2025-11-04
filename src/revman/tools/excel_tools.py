"""Excel processing tools for parsing TBS Price Change Summary reports"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ExcelReaderInput(BaseModel):
    """Input schema for ExcelReaderTool"""
    file_path: str = Field(..., description="Path to the Excel file to read")
    skip_rows: int = Field(6, description="Number of rows to skip before header (default: 6 for TBS reports)")


class ExcelReaderTool(BaseTool):
    name: str = "Excel File Reader"
    description: str = (
        "Reads Excel files and extracts data. Specifically designed for TBS Price Change Summary reports. "
        "Handles complex headers, skips metadata rows, and returns structured data as a list of dictionaries."
    )
    args_schema: type[BaseModel] = ExcelReaderInput

    def _run(self, file_path: str, skip_rows: int = 6) -> str:
        """
        Read and parse Excel file

        Args:
            file_path: Path to Excel file
            skip_rows: Number of rows to skip (default 6 for TBS reports)

        Returns:
            JSON string with parsed data
        """
        try:
            # Read Excel file
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return f"Error: File not found at {file_path}"

            # Read with pandas, skipping header rows
            df = pd.read_excel(file_path, skiprows=skip_rows)

            # Clean column names (remove whitespace, newlines)
            df.columns = df.columns.str.strip().str.replace('\n', ' ')

            # Remove completely empty rows
            df = df.dropna(how='all')

            # Convert to list of dictionaries
            records = df.to_dict('records')

            # Build response
            result = {
                "success": True,
                "file_path": str(file_path),
                "total_records": len(records),
                "columns": list(df.columns),
                "records": records[:10],  # First 10 for preview
                "full_record_count": len(records),
                "message": f"Successfully parsed {len(records)} records from Excel file"
            }

            import json
            return json.dumps(result, default=str, indent=2)

        except Exception as e:
            return f"Error reading Excel file: {str(e)}"


class DataCleanerInput(BaseModel):
    """Input schema for DataCleanerTool"""
    data: str = Field(..., description="JSON string of data to clean")


class DataCleanerTool(BaseTool):
    name: str = "Data Cleaner"
    description: str = (
        "Cleans and standardizes data. Handles missing values, normalizes text fields, "
        "converts data types, and removes special characters."
    )
    args_schema: type[BaseModel] = DataCleanerInput

    def _run(self, data: str) -> str:
        """
        Clean and standardize data

        Args:
            data: JSON string of data to clean

        Returns:
            JSON string with cleaned data
        """
        try:
            import json

            # Parse input data
            data_dict = json.loads(data)
            records = data_dict.get("records", [])

            cleaned_records = []
            for record in records:
                cleaned = {}
                for key, value in record.items():
                    # Handle None/NaN values
                    if pd.isna(value) or value is None:
                        cleaned[key] = None
                        continue

                    # Clean text fields
                    if isinstance(value, str):
                        # Strip whitespace
                        value = value.strip()
                        # Replace multiple spaces with single space
                        value = ' '.join(value.split())

                    cleaned[key] = value

                cleaned_records.append(cleaned)

            result = {
                "success": True,
                "cleaned_records": cleaned_records,
                "total_cleaned": len(cleaned_records),
                "message": f"Successfully cleaned {len(cleaned_records)} records"
            }

            return json.dumps(result, default=str, indent=2)

        except Exception as e:
            return f"Error cleaning data: {str(e)}"


class PriceCalculatorInput(BaseModel):
    """Input schema for PriceCalculatorTool"""
    old_price: float = Field(..., description="Old price value")
    new_price: float = Field(..., description="New price value")


class PriceCalculatorTool(BaseTool):
    name: str = "Price Calculator"
    description: str = (
        "Calculates price changes, percentage changes, and validates pricing data. "
        "Takes old and new prices and returns change amount, percentage, and direction."
    )
    args_schema: type[BaseModel] = PriceCalculatorInput

    def _run(self, old_price: float, new_price: float) -> str:
        """
        Calculate price change statistics

        Args:
            old_price: Original price
            new_price: New price

        Returns:
            JSON string with price change analysis
        """
        try:
            import json

            # Calculate changes
            change_amount = new_price - old_price

            if old_price != 0:
                change_percent = (change_amount / old_price) * 100
            else:
                change_percent = 0

            # Determine direction and type
            if change_amount < 0:
                direction = "decrease"
                change_type = "Begin LTO"  # Price decreases indicate LTO start
            elif change_amount > 0:
                direction = "increase"
                change_type = "End LTO"  # Price increases indicate LTO end
            else:
                direction = "no change"
                change_type = "No Change"

            # Determine if it's a significant change
            is_significant = abs(change_amount) >= 2.0

            result = {
                "success": True,
                "old_price": old_price,
                "new_price": new_price,
                "change_amount": round(change_amount, 2),
                "change_percent": round(change_percent, 2),
                "direction": direction,
                "suggested_category": change_type,
                "is_significant": is_significant,
                "formatted_change": f"${abs(change_amount):.2f}",
                "sign": "+" if change_amount >= 0 else "-"
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error calculating price change: {str(e)}"
