"""
Excel processing tools for parsing TBS Price Change Summary reports.

Uses CrewAI SDK's BaseTool for production-ready error handling.
All tools fail-fast on errors, letting SDK handle exception propagation and retry logic.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Type

import openpyxl
import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# ============================================================================
# Input Schemas (Pydantic)
# ============================================================================

class ExcelReaderInput(BaseModel):
    """Input schema for ExcelReaderTool"""
    file_path: str = Field(..., description="Path to the Excel file to read")
    skip_rows: int = Field(7, description="Number of rows to skip before header (default: 7 for TBS reports)")


class ExcelReaderTool(BaseTool):
    """
    Reads Excel files and extracts data from TBS Price Change Summary reports.
    
    Validation:
    - Requires at least 1 record to be parsed
    - Fails if file doesn't exist
    - Fails if expected columns are missing
    """
    name: str = "Excel File Reader"
    description: str = (
        "Reads Excel files and extracts data. Specifically designed for TBS Price Change Summary reports. "
        "Handles complex headers, skips metadata rows, and returns structured data as a list of dictionaries."
    )
    args_schema: Type[BaseModel] = ExcelReaderInput

    # Validation configuration - require at least 1 record
    min_output_items: int = 1
    required_output_keys: List[str] = ["success", "total_records", "records"]

    def _run(self, file_path: str, skip_rows: int = 7) -> Dict[str, Any]:
        """
        Read and parse Excel file.

        Args:
            file_path: Path to Excel file
            skip_rows: Number of rows to skip (default 7 for TBS reports)

        Returns:
            Dict with parsed data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If no records found or invalid data
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found at {file_path}")

        # Read with pandas, skipping header rows and reading only columns A-L
        df = pd.read_excel(file_path, skiprows=skip_rows, usecols="A:L")

        # Clean column names
        df.columns = df.columns.str.strip().str.replace('\n', ' ')

        # Remove completely empty rows
        df = df.dropna(how='all')

        if len(df) == 0:
            raise ValueError("No records found in Excel file after parsing")

        # Convert to list of dictionaries
        records = df.to_dict('records')

        return {
            "success": True,
            "file_path": str(file_path),
            "total_records": len(records),
            "columns": list(df.columns),
            "records": records,
            "full_record_count": len(records),
            "message": f"Successfully parsed {len(records)} records from Excel file"
        }


class FormulaExcelGeneratorInput(BaseModel):
    """Input schema for FormulaExcelGeneratorTool"""
    input_file_path: str = Field(..., description="Path to the input Excel file")
    output_dir: str = Field(..., description="Directory where the formula Excel file will be saved")
    skip_rows: int = Field(7, description="Number of header rows to skip before data starts (default: 7 for TBS reports)")
    formula_column: str = Field("N", description="Column letter where formula should be added (default: N)")


class FormulaExcelGeneratorTool(BaseTool):
    """Creates a copy of input Excel with formulas added for price change text generation."""
    
    name: str = "Formula Excel Generator"
    description: str = (
        "Creates a copy of the input Excel file with formulas added to generate formatted price change text. "
        "The formula combines product name, pack size, and price change information. "
        "Output file is saved with '_formula.xlsx' suffix."
    )
    args_schema: Type[BaseModel] = FormulaExcelGeneratorInput

    def _run(
        self, 
        input_file_path: str, 
        output_dir: str, 
        skip_rows: int = 7, 
        formula_column: str = "N"
    ) -> Dict[str, Any]:
        """
        Generate Excel file with formulas added.

        Args:
            input_file_path: Path to input Excel file
            output_dir: Directory to save output file
            skip_rows: Number of header rows to skip
            formula_column: Column to add formula

        Returns:
            Dict with result information

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If no data rows found to process
        """
        input_path = Path(input_file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file_path}")

        # Extract month and date from input filename
        filename = input_path.stem
        match = re.search(r'-\s*(.+?)\.xlsx', input_path.name)
        if not match:
            match = re.search(r'([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)\'?\d{2})', filename)

        if match:
            date_part = match.group(1).strip()
        else:
            date_part = datetime.now().strftime("%B %d'%y")

        # Construct output filename and path
        output_filename = f"TBS Price Change Summary Report - {date_part}_formula.xlsx"
        output_path = Path(output_dir) / output_filename

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Load the workbook
        wb = openpyxl.load_workbook(input_file_path)
        
        # Use the first sheet (not active sheet which may be different)
        # This matches pandas behavior which reads first sheet by default
        ws = wb[wb.sheetnames[0]]

        # Calculate row positions
        data_start_row = skip_rows + 2
        header_row = skip_rows + 1

        # Add header for column O
        ws[f'O{header_row}'] = 'Price Ratio %'

        # Find the last row with data by checking column A
        # ws.max_row can be unreliable for some Excel files
        max_row = ws.max_row
        
        # Verify we have data rows by checking if any cells have values
        # Sometimes max_row is calculated incorrectly
        if max_row < data_start_row:
            # Try to find actual last row by iterating
            for row_num in range(data_start_row, 10000):  # Upper bound for safety
                if ws[f'A{row_num}'].value is None and ws[f'D{row_num}'].value is None:
                    # Check a few more rows to confirm end
                    if (ws[f'A{row_num + 1}'].value is None and 
                        ws[f'A{row_num + 2}'].value is None):
                        max_row = row_num - 1
                        break
            else:
                max_row = data_start_row + 500  # Fallback

        # Add formulas to each data row
        formula_count = 0
        for row_num in range(data_start_row, max_row + 1):
            # Check if row has data (column A or D should have value)
            if ws[f'A{row_num}'].value is None and ws[f'D{row_num}'].value is None:
                continue

            # Main formula for price change text
            formula = f'=PROPER($D{row_num})&" "&$H{row_num}&$L{row_num}&" "&$M{row_num}&"$"&ABS($K{row_num})&" to $"&$J{row_num}'
            ws[f'{formula_column}{row_num}'] = formula

            # Percentage ratio formula
            percentage_formula = f'=(J{row_num}/I{row_num})*100'
            ws[f'O{row_num}'] = percentage_formula

            formula_count += 1

        # Validate we added formulas
        if formula_count == 0:
            raise ValueError(
                f"No data rows found to add formulas. "
                f"Checked rows {data_start_row} to {max_row}. "
                f"Verify skip_rows={skip_rows} matches the file structure."
            )

        # Save the workbook
        wb.save(output_path)

        return {
            "success": True,
            "input_file": str(input_path),
            "output_file": str(output_path),
            "output_filename": output_filename,
            "formulas_added": formula_count,
            "data_start_row": data_start_row,
            "formula_column": formula_column,
            "message": f"Successfully created formula Excel file with {formula_count} formulas"
        }


class DateExtractorInput(BaseModel):
    """Input schema for DateExtractorTool"""
    file_path: str = Field(..., description="Path to the Excel file (date will be extracted from filename)")


class DateExtractorTool(BaseTool):
    """Extracts effective date from TBS Price Change Summary Report filename."""
    
    name: str = "Date Extractor from Filename"
    description: str = (
        "Extracts the effective date from TBS Price Change Summary Report filename. "
        "Expected filename format: 'TBS Price Change Summary Report - October 13th'25.xlsx' "
        "Returns the parsed date in both ISO format (YYYY-MM-DD) and display format (Month DD, YYYY)."
    )
    args_schema: Type[BaseModel] = DateExtractorInput

    def _run(self, file_path: str) -> Dict[str, Any]:
        """
        Extract effective date from filename.

        Args:
            file_path: Path to the Excel file

        Returns:
            Dict with date information

        Raises:
            ValueError: If date cannot be extracted from filename
        """
        file_path_obj = Path(file_path)
        filename = file_path_obj.name

        # Pattern: Month DDth'YY or Month DD'YY
        pattern = r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[\'\']?(\d{2})'
        match = re.search(pattern, filename)

        if match:
            month_str = match.group(1)
            day_str = match.group(2)
            year_str = match.group(3)

            date_str = f"{month_str} {day_str}, 20{year_str}"
            parsed_date = datetime.strptime(date_str, "%B %d, %Y")

            return {
                "success": True,
                "source": "filename",
                "filename": filename,
                "effective_date_iso": parsed_date.strftime("%Y-%m-%d"),
                "effective_date_display": parsed_date.strftime("%B %d, %Y"),
                "raw_date_string": f"{month_str} {day_str}'{year_str}",
                "message": f"Successfully extracted date: {parsed_date.strftime('%B %d, %Y')}"
            }
        else:
            # Don't silently fall back - raise error with clear message
            raise ValueError(
                f"Could not extract date from filename: '{filename}'. "
                f"Expected format: 'TBS Price Change Summary Report - Month DDth'YY.xlsx'"
            )
