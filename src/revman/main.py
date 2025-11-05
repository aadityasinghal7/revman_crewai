#!/usr/bin/env python
"""
RevMan Price Change Email Flow
Processes Excel price change reports and generates formatted HTML email templates
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from crewai.flow import Flow, listen, start
from crewai import Agent

from revman.crews.excel_processor_crew import ExcelProcessorCrew
from revman.crews.email_builder_crew import EmailBuilderCrew
from revman.tools import EmailValidatorTool


class RevManFlowState(BaseModel):
    """State model for RevMan Price Change Flow"""

    # Input
    excel_file_path: str = ""
    trigger_date: datetime = datetime.now()
    email_recipients: Optional[List[str]] = None

    # Excel Processing Output (Crew 1)
    raw_data: Dict[str, Any] = {}
    price_changes_categorized: Dict[str, Any] = {}
    parsing_errors: List[str] = []

    # Email Generation Output (Crew 2)
    highlights_text: str = ""
    email_html: str = ""
    email_subject: str = ""
    email_metadata: Dict[str, Any] = {}

    # Validation Output
    validation_passed: bool = False
    validation_report: Dict[str, Any] = {}

    # Final Output
    output_file_path: Optional[str] = None


class RevManFlow(Flow[RevManFlowState]):
    """
    RevMan Price Change Email Flow

    Flow orchestrates:
    1. Excel parsing and analysis (Crew 1)
    2. Email generation (Crew 2)
    3. Validation
    4. Output saving
    """

    def __init__(self):
        """Initialize the flow with tracing enabled"""
        super().__init__(tracing=True)

    @start()
    def trigger_flow(self, crewai_trigger_payload: dict = None):
        """
        Initialize flow from trigger

        For POC: Accept file path as parameter (manual trigger)
        For Phase 8: Extract Excel from email (automatic trigger)
        """
        print("\n" + "=" * 60)
        print("[START] RevMan Price Change Flow Started")
        print("=" * 60)

        if crewai_trigger_payload:
            # Use trigger payload
            self.state.excel_file_path = crewai_trigger_payload.get(
                "excel_file_path",
                os.getenv("REVMAN_INPUT_DIR", "./data/input") + "/TBS Price Change Summary Report - October 13th'25.xlsx"
            )
            trigger_date_str = crewai_trigger_payload.get("trigger_date")
            if trigger_date_str:
                self.state.trigger_date = datetime.fromisoformat(trigger_date_str.replace('Z', '+00:00'))

            self.state.email_recipients = crewai_trigger_payload.get("email_recipients", [])

            print(f"[OK] Using trigger payload")
            print(f"  File: {self.state.excel_file_path}")
            print(f"  Date: {self.state.trigger_date}")
        else:
            # Default: use sample file from data/input
            input_dir = os.getenv("REVMAN_INPUT_DIR", "./data/input")
            self.state.excel_file_path = str(Path(input_dir) / "TBS Price Change Summary Report - October 13th'25.xlsx")
            print(f"[OK] Using default file: {self.state.excel_file_path}")

        # Validate input file exists
        if not Path(self.state.excel_file_path).exists():
            raise FileNotFoundError(f"Excel file not found: {self.state.excel_file_path}")

        print(f"[OK] Input file validated\n")

    @listen(trigger_flow)
    def excel_processing_step(self):
        """
        Run Excel Processor Crew (Crew 1)
        - Parse Excel file
        - Analyze and categorize price changes
        - Validate data quality
        """
        print("\n" + "-" * 60)
        print("[EXCEL] Step 1: Excel Processing")
        print("-" * 60)

        try:
            # Kick off Excel Processor Crew
            result = (
                ExcelProcessorCrew()
                .crew()
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "raw_data": {},  # Will be populated by parse task
                })
            )

            print(f"[OK] Excel processing completed")

            # Parse the result
            # The last task (validate_data_quality) output should contain the categorized data
            result_str = result.raw if hasattr(result, 'raw') else str(result)

            # Try to parse as JSON if possible
            try:
                if isinstance(result_str, str) and (result_str.startswith('{') or result_str.startswith('[')):
                    result_data = json.loads(result_str)
                else:
                    # If not JSON, store as-is
                    result_data = {"categorized_output": result_str}

                self.state.price_changes_categorized = result_data
                print(f"[OK] Price changes categorized")

            except json.JSONDecodeError:
                # If parsing fails, store the raw output
                print(f"[WARNING] Could not parse result as JSON, storing raw output")
                self.state.price_changes_categorized = {"raw_output": result_str}

        except Exception as e:
            error_msg = f"Error in Excel processing: {str(e)}"
            print(f"[ERROR] {error_msg}")
            self.state.parsing_errors.append(error_msg)
            raise

    @listen(excel_processing_step)
    def email_generation_step(self):
        """
        Run Email Builder Crew (Crew 2)
        - Generate highlights content
        - Format as HTML email
        """
        print("\n" + "-" * 60)
        print("[EMAIL] Step 2: Email Generation")
        print("-" * 60)

        try:
            # Kick off Email Builder Crew
            result = (
                EmailBuilderCrew()
                .crew()
                .kickoff(inputs={
                    "price_changes_categorized": self.state.price_changes_categorized,
                    "trigger_date": self.state.trigger_date.isoformat(),
                    "highlights_text": "",  # Will be populated by first task
                })
            )

            print(f"[OK] Email generation completed")

            # Extract email content from result
            result_str = result.raw if hasattr(result, 'raw') else str(result)

            # The result should be HTML content from format_as_html_email task
            self.state.email_html = result_str
            self.state.email_subject = f"TBS Price Change Summary - {self.state.trigger_date.strftime('%B %d, %Y')}"

            print(f"[OK] Email HTML generated")
            print(f"  Subject: {self.state.email_subject}")

        except Exception as e:
            error_msg = f"Error in email generation: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(email_generation_step)
    def validation_step(self):
        """
        Validate email output
        - Check data completeness
        - Validate HTML structure
        - Verify formatting
        """
        print("\n" + "-" * 60)
        print("[VALIDATION] Step 3: Validation")
        print("-" * 60)

        try:
            # Use EmailValidatorTool
            validator = EmailValidatorTool()
            validation_result = validator._run(
                html_content=self.state.email_html,
                subject_line=self.state.email_subject
            )

            # Parse validation result
            validation_data = json.loads(validation_result)
            self.state.validation_report = validation_data

            # Check if validation passed
            status = validation_data.get("validation_status", "FAIL")
            self.state.validation_passed = status in ["PASS", "PASS WITH WARNINGS"]

            print(f"[OK] Validation {status}")
            print(f"  Quality Score: {validation_data.get('quality_score', 0)}/100")

            if validation_data.get("critical_issues"):
                print(f"  [WARNING] Critical Issues: {len(validation_data['critical_issues'])}")
                for issue in validation_data['critical_issues']:
                    print(f"    - {issue}")

            if validation_data.get("warnings"):
                print(f"  [WARNING] Warnings: {len(validation_data['warnings'])}")

            # Fail flow if critical issues exist
            if validation_data.get("critical_issues"):
                raise Exception("Validation failed with critical issues")

        except Exception as e:
            error_msg = f"Error in validation: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(validation_step)
    def save_email_output(self):
        """
        Save generated email to output directory
        - Save HTML email
        - Save metadata
        - Save validation report
        """
        print("\n" + "-" * 60)
        print("[SAVE] Step 4: Save Output")
        print("-" * 60)

        try:
            # Get output directory
            output_dir = Path(os.getenv("REVMAN_OUTPUT_DIR", "./data/output"))
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = self.state.trigger_date.strftime("%Y-%m-%d")
            base_filename = f"price_change_email_{timestamp}"

            # Save HTML email
            html_path = output_dir / f"{base_filename}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.state.email_html)
            print(f"[OK] Saved HTML email: {html_path}")

            # Save metadata
            metadata = {
                "subject": self.state.email_subject,
                "generated_at": datetime.now().isoformat(),
                "trigger_date": self.state.trigger_date.isoformat(),
                "input_file": self.state.excel_file_path,
                "validation_passed": self.state.validation_passed,
                "recipients": self.state.email_recipients or [],
            }
            metadata_path = output_dir / f"{base_filename}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Saved metadata: {metadata_path}")

            # Save validation report
            report_path = output_dir / f"{base_filename}_validation.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.state.validation_report, f, indent=2)
            print(f"[OK] Saved validation report: {report_path}")

            self.state.output_file_path = str(html_path)

            print("\n" + "=" * 60)
            print("[SUCCESS] RevMan Flow Completed Successfully!")
            print("=" * 60)
            print(f"Output: {html_path}")
            print(f"Subject: {self.state.email_subject}")
            print("=" * 60 + "\n")

        except Exception as e:
            error_msg = f"Error saving output: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise


def kickoff():
    """Run the RevMan flow"""
    flow = RevManFlow()
    flow.kickoff()


def plot():
    """Generate flow visualization"""
    flow = RevManFlow()
    flow.plot()


def run_with_trigger():
    """
    Run the flow with trigger payload.
    Usage: crewai run_with_trigger '{"excel_file_path": "./data/input/file.xlsx"}'
    """
    import sys

    # Get trigger payload from command line argument
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    # Create flow and kickoff with trigger payload
    flow = RevManFlow()

    try:
        result = flow.kickoff({"crewai_trigger_payload": trigger_payload})
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the flow with trigger: {e}")


if __name__ == "__main__":
    kickoff()
