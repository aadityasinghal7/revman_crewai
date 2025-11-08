#!/usr/bin/env python
"""
RevMan Price Change Email Flow
Processes Excel price change reports and generates plain text email content in template format
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from crewai.flow import Flow, listen, start
from crewai import Agent

from revman.crews.excel_processor_crew import ExcelProcessorCrew
from revman.crews.email_builder_crew import EmailBuilderCrew
from revman.tools import EmailValidatorTool


# Define file paths using relative path from main.py
# main.py is at: revman/src/revman/main.py
# project_root is at: revman/
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv('REVMAN_DATA_DIR', PROJECT_ROOT / "data"))
INPUT_DIR = Path(os.getenv('REVMAN_INPUT_DIR', DATA_DIR / "input"))
OUTPUT_DIR = Path(os.getenv('REVMAN_OUTPUT_DIR', DATA_DIR / "output"))
TEMPLATE_DIR = Path(os.getenv('REVMAN_TEMPLATE_DIR', DATA_DIR / "templates"))


class RevManFlowState(BaseModel):
    """State model for RevMan Price Change Flow - Only user-provided inputs"""

    # User input - the only field required at kickoff
    excel_file_path: str = str(INPUT_DIR / "TBS Price Change Summary Report - October 13th'25.xlsx")


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
        super().__init__()
        # Timing tracking
        self._flow_start_time = None
        self._step_times = {}

        # Internal state - auto-generated, not from kickoff
        self._trigger_date: datetime = None  # Will be set to datetime.now() in trigger_flow
        self._email_recipients: List[str] = None  # Will load from env in trigger_flow
        self._email_content: str = ""
        self._email_subject: str = ""
        self._email_metadata: Dict[str, Any] = {}

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"

    def _print_performance_summary(self):
        """Print performance summary with timing breakdown"""
        if not self._flow_start_time:
            return

        total_time = time.time() - self._flow_start_time

        print("\n" + "=" * 60)
        print("[PERFORMANCE SUMMARY]")
        print("=" * 60)

        # Sort by duration (longest first)
        sorted_steps = sorted(self._step_times.items(), key=lambda x: x[1], reverse=True)

        for step_name, duration in sorted_steps:
            percentage = (duration / total_time) * 100
            formatted_name = step_name.replace('_', ' ').title()
            print(f"  {formatted_name:25s}: {self._format_duration(duration):>8s} ({percentage:5.1f}%)")

        print("-" * 60)
        print(f"  {'TOTAL EXECUTION TIME':25s}: {self._format_duration(total_time):>8s} (100.0%)")
        print("=" * 60)

    @start()
    def trigger_flow(self, crewai_trigger_payload: dict = None):
        """
        Initialize flow from trigger

        For POC: Accept file path as parameter (manual trigger)
        For Phase 2: Extract Excel from email (automatic trigger)
        """
        self._flow_start_time = time.time()
        step_start = time.time()

        # Auto-generate internal state
        self._trigger_date = datetime.now()
        self._email_recipients = os.getenv(
            "REVMAN_EMAIL_RECIPIENTS",
            "aaditya.singhal@anheuser-busch.com"
        ).split(",")  # Support comma-separated list

        print("\n" + "=" * 60)
        print("[START] RevMan Price Change Flow Started")
        print("=" * 60)

        if crewai_trigger_payload:
            print(f"[OK] Using trigger payload")
            print(f"  File: {self.state.excel_file_path}")
        else:
            print(f"[OK] Using default configuration")
            print(f"  File: {self.state.excel_file_path}")

        print(f"  Date: {self._trigger_date}")
        print(f"  Recipients: {', '.join(self._email_recipients)}")

        # Validate input file exists
        if not Path(self.state.excel_file_path).exists():
            raise FileNotFoundError(f"Excel file not found: {self.state.excel_file_path}")

        print(f"[OK] Input file validated")

        # Record timing
        step_duration = time.time() - step_start
        self._step_times['trigger_validation'] = step_duration
        print(f"[TIMING] Trigger validation: {self._format_duration(step_duration)}\n")

    @listen(trigger_flow)
    def excel_processing_step(self):
        """
        Run Excel Processor Crew (Crew 1)
        - Parse Excel file
        - Analyze and categorize price changes
        - Validate data quality
        """
        step_start = time.time()

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
                    "output_dir": str(OUTPUT_DIR),
                    "raw_data": {},  # Will be populated by parse task
                })
            )

            step_duration = time.time() - step_start
            self._step_times['excel_processing'] = step_duration
            print(f"[OK] Excel processing completed")
            print(f"[TIMING] Excel processing: {self._format_duration(step_duration)}")

            # Parse the result
            # The last task (validate_data_quality) should output both validation and categorized data
            result_str = result.raw if hasattr(result, 'raw') else str(result)

            # Try to parse as JSON if possible
            try:
                if isinstance(result_str, str) and (result_str.startswith('{') or result_str.startswith('[')):
                    result_data = json.loads(result_str)

                    # Extract categorized_data from the validation output
                    if isinstance(result_data, dict) and "categorized_data" in result_data:
                        self._price_changes_categorized = result_data["categorized_data"]
                        print(f"[OK] Price changes categorized and extracted")

                        # Also store validation results if present
                        if "validation" in result_data:
                            self._validation_info = result_data["validation"]
                            print(f"[OK] Validation info: {result_data['validation'].get('status', 'UNKNOWN')}")
                    else:
                        # Fallback: use entire result if structure is different
                        self._price_changes_categorized = result_data
                        print(f"[OK] Price changes categorized (using full result)")
                else:
                    # If not JSON, store as-is
                    result_data = {"categorized_output": result_str}
                    self._price_changes_categorized = result_data
                    print(f"[WARNING] Result is not JSON format")

            except json.JSONDecodeError:
                # If parsing fails, store the raw output
                print(f"[WARNING] Could not parse result as JSON, storing raw output")
                self._price_changes_categorized = {"raw_output": result_str}

        except Exception as e:
            error_msg = f"Error in Excel processing: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(excel_processing_step)
    def email_generation_step(self):
        """
        Run Email Builder Crew (Crew 2)
        - Generate highlights content in plain text template format
        """
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EMAIL] Step 2: Email Content Generation")
        print("-" * 60)

        try:
            # Kick off Email Builder Crew
            result = (
                EmailBuilderCrew()
                .crew()
                .kickoff(inputs={
                    "price_changes_categorized": self._price_changes_categorized,
                })
            )

            step_duration = time.time() - step_start
            self._step_times['email_generation'] = step_duration
            print(f"[OK] Email content generation completed")
            print(f"[TIMING] Email generation: {self._format_duration(step_duration)}")

            # Extract email content from result
            result_str = result.raw if hasattr(result, 'raw') else str(result)

            # The result should be plain text content in template format
            self._email_content = result_str
            self._email_subject = f"TBS Price Change Summary - {self._trigger_date.strftime('%B %d, %Y')}"

            print(f"[OK] Email content generated in template format")
            print(f"  Subject: {self._email_subject}")

        except Exception as e:
            error_msg = f"Error in email generation: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(email_generation_step)
    def validation_step(self):
        """
        Validate email output
        - Check content completeness
        - Verify template format structure
        - Check for required sections
        """
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[VALIDATION] Step 3: Content Validation")
        print("-" * 60)

        try:
            # Basic validation for plain text template format
            content = self._email_content

            validation_data = {
                "validation_status": "PASS",
                "quality_score": 100,
                "critical_issues": [],
                "warnings": []
            }

            # Check for required elements
            if "Highlights (Price Before Tax and Deposit)" not in content:
                validation_data["critical_issues"].append("Missing required title: 'Highlights (Price Before Tax and Deposit)'")

            # Check for at least one brewer section
            brewers = ["LABATT", "MOLSON", "SLEEMAN"]
            has_brewer = any(brewer in content for brewer in brewers)
            if not has_brewer:
                validation_data["critical_issues"].append("No brewer sections found (LABATT, MOLSON, SLEEMAN)")

            # Check for at least one change type section
            sections = ["Begin LTO", "End LTO"]
            has_section = any(section in content for section in sections)
            if not has_section:
                validation_data["warnings"].append("No change type sections found (Begin LTO, End LTO)")

            # Check for deprecated sections that should NOT exist
            if "Permanent Changes" in content or "End LTO & Perm Change" in content:
                validation_data["warnings"].append(
                    "Found deprecated section: 'Permanent Changes' or 'End LTO & Perm Change'. "
                    "Only 'Begin LTO' and 'End LTO' sections should exist per plan.md."
                )

            # Update validation status based on issues
            if validation_data["critical_issues"]:
                validation_data["validation_status"] = "FAIL"
                validation_data["quality_score"] = 0
            elif validation_data["warnings"]:
                validation_data["validation_status"] = "PASS WITH WARNINGS"
                validation_data["quality_score"] = 80

            # Store in instance variables instead of state
            self._validation_report = validation_data
            status = validation_data.get("validation_status", "FAIL")
            self._validation_passed = status in ["PASS", "PASS WITH WARNINGS"]

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

            step_duration = time.time() - step_start
            self._step_times['validation'] = step_duration
            print(f"[TIMING] Validation: {self._format_duration(step_duration)}")

        except Exception as e:
            error_msg = f"Error in validation: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(validation_step)
    def save_email_output(self):
        """
        Save generated email to output directory
        - Save plain text email in template format
        - Save metadata
        - Save validation report
        """
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[SAVE] Step 4: Save Output")
        print("-" * 60)

        try:
            # Get output directory
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = self._trigger_date.strftime("%Y-%m-%d")
            base_filename = f"price_change_email_{timestamp}"

            # Save plain text email
            txt_path = OUTPUT_DIR / f"{base_filename}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(self._email_content)
            print(f"[OK] Saved email content: {txt_path}")

            # Save metadata
            metadata = {
                "subject": self._email_subject,
                "generated_at": datetime.now().isoformat(),
                "trigger_date": self._trigger_date.isoformat(),
                "input_file": self.state.excel_file_path,
                "validation_passed": self._validation_passed,
                "recipients": self._email_recipients,
            }
            metadata_path = OUTPUT_DIR / f"{base_filename}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Saved metadata: {metadata_path}")

            # Save validation report
            report_path = OUTPUT_DIR / f"{base_filename}_validation.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self._validation_report, f, indent=2)
            print(f"[OK] Saved validation report: {report_path}")

            step_duration = time.time() - step_start
            self._step_times['save_output'] = step_duration
            print(f"[TIMING] Save output: {self._format_duration(step_duration)}")

            # Print performance summary
            self._print_performance_summary()

            print("\n" + "=" * 60)
            print("[SUCCESS] RevMan Flow Completed Successfully!")
            print("=" * 60)
            print(f"Output: {txt_path}")
            print(f"Subject: {self._email_subject}")
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
