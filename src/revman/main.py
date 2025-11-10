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
    excel_file_path: str = "TBS Price Change Summary Report - October 13th'25.xlsx"


class RevManFlow(Flow[RevManFlowState]):
    """
    RevMan Price Change Email Flow

    Flow orchestrates:
    1. Trigger - Input validation
    2a. Parse Excel file
    2b. Extract effective date
    2c. Generate formula Excel
    2d. Analyze price changes
    2e. Validate data quality
    3. Email generation (Crew 2)
    4. Validation (pass-through)
    5. Output saving
    """

    def __init__(self):
        super().__init__()
        # Timing tracking
        self._flow_start_time = None
        self._step_times = {}

        # Internal state - auto-generated, not from kickoff
        self._trigger_date: datetime = None  # Will be set to datetime.now() in trigger_flow
        self._effective_date: datetime = None  # Will be extracted from filename by Excel processor crew
        self._email_recipients: List[str] = None  # Will load from env in trigger_flow
        self._email_content: str = ""
        self._email_subject: str = ""
        self._email_metadata: Dict[str, Any] = {}

        # Excel processing state
        self._raw_data: Dict[str, Any] = {}
        self._price_analysis: Dict[str, Any] = {}
        self._price_changes_categorized: Dict[str, Any] = {}
        self._validation_info: Dict[str, Any] = {}
        self._validation_report: Dict[str, Any] = {}
        self._validation_passed: bool = False

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
    def step_1_trigger(self, crewai_trigger_payload: dict = None):
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
        # Handle both absolute and relative paths
        excel_path = Path(self.state.excel_file_path)
        if not excel_path.is_absolute():
            # If relative path, resolve it relative to INPUT_DIR
            excel_path = INPUT_DIR / excel_path

        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Update state with resolved absolute path
        self.state.excel_file_path = str(excel_path)
        print(f"[OK] Input file validated")

        # Record timing
        step_duration = time.time() - step_start
        self._step_times['trigger_validation'] = step_duration
        print(f"[TIMING] Trigger validation: {self._format_duration(step_duration)}\n")

    @listen(step_1_trigger)
    def step_2a_parse_excel(self):
        """Parse Excel file"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EXCEL] Step 2a: Parse Excel File")
        print("-" * 60)

        try:
            # Create crew with just parse task
            from crewai import Crew, Process
            crew_instance = ExcelProcessorCrew()

            result = (
                Crew(
                    agents=[crew_instance.excel_parser_agent()],
                    tasks=[crew_instance.parse_excel_file()],
                    process=Process.sequential,
                    verbose=True,
                    full_output=True,
                )
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "output_dir": str(OUTPUT_DIR),
                    "raw_data": {},
                })
            )

            # Store raw data for next steps
            result_str = result.raw if hasattr(result, 'raw') else str(result)
            try:
                self._raw_data = json.loads(result_str) if result_str.startswith('{') else {"raw": result_str}
            except:
                self._raw_data = {"raw": result_str}

            step_duration = time.time() - step_start
            self._step_times['parse_excel'] = step_duration
            print(f"[OK] Excel file parsed")
            print(f"[TIMING] Parse excel: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error parsing Excel: {str(e)}")
            raise

    @listen(step_2a_parse_excel)
    def step_2b_extract_date(self):
        """Extract effective date from filename"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EXCEL] Step 2b: Extract Effective Date")
        print("-" * 60)

        try:
            # Create crew with just extract date task
            from crewai import Crew, Process
            crew_instance = ExcelProcessorCrew()

            result = (
                Crew(
                    agents=[crew_instance.excel_parser_agent()],
                    tasks=[crew_instance.extract_effective_date()],
                    process=Process.sequential,
                    verbose=True,
                    full_output=True,
                )
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                })
            )

            # Extract effective date
            result_str = result.raw if hasattr(result, 'raw') else str(result)
            try:
                date_data = json.loads(result_str)
                if date_data.get('success') and date_data.get('effective_date_iso'):
                    self._effective_date = datetime.fromisoformat(date_data['effective_date_iso'])
                    print(f"[OK] Effective date extracted: {date_data.get('effective_date_display')}")
                else:
                    self._effective_date = self._trigger_date
                    print(f"[WARNING] Using trigger date as fallback")
            except:
                self._effective_date = self._trigger_date
                print(f"[WARNING] Using trigger date as fallback")

            step_duration = time.time() - step_start
            self._step_times['extract_date'] = step_duration
            print(f"[TIMING] Extract date: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error extracting date: {str(e)}")
            raise

    @listen(step_2b_extract_date)
    def step_2c_generate_formula(self):
        """Generate formula Excel file"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EXCEL] Step 2c: Generate Formula Excel")
        print("-" * 60)

        try:
            # Create crew with just generate formula task
            from crewai import Crew, Process
            crew_instance = ExcelProcessorCrew()

            result = (
                Crew(
                    agents=[crew_instance.excel_parser_agent()],
                    tasks=[crew_instance.generate_formula_excel()],
                    process=Process.sequential,
                    verbose=True,
                    full_output=True,
                )
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "output_dir": str(OUTPUT_DIR),
                    "raw_data": self._raw_data,
                })
            )

            step_duration = time.time() - step_start
            self._step_times['generate_formula'] = step_duration
            print(f"[OK] Formula Excel generated")
            print(f"[TIMING] Generate formula: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error generating formula Excel: {str(e)}")
            raise

    @listen(step_2c_generate_formula)
    def step_2d_analyze_prices(self):
        """Analyze price changes"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EXCEL] Step 2d: Analyze Price Changes")
        print("-" * 60)

        try:
            # Create crew with just analyze task
            from crewai import Crew, Process
            crew_instance = ExcelProcessorCrew()

            result = (
                Crew(
                    agents=[crew_instance.data_analyst_agent()],
                    tasks=[crew_instance.analyze_price_changes()],
                    process=Process.sequential,
                    verbose=True,
                    full_output=True,
                )
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "raw_data": self._raw_data,
                })
            )

            # Store analysis for next steps
            result_str = result.raw if hasattr(result, 'raw') else str(result)
            try:
                self._price_analysis = json.loads(result_str) if result_str.startswith('{') else {"analysis": result_str}
            except:
                self._price_analysis = {"analysis": result_str}

            step_duration = time.time() - step_start
            self._step_times['analyze_prices'] = step_duration
            print(f"[OK] Price changes analyzed")
            print(f"[TIMING] Analyze prices: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error analyzing prices: {str(e)}")
            raise

    @listen(step_2d_analyze_prices)
    def step_2e_validate_quality(self):
        """Validate data quality"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[EXCEL] Step 2e: Validate Data Quality")
        print("-" * 60)

        try:
            # Create crew with just validate task
            from crewai import Crew, Process
            crew_instance = ExcelProcessorCrew()

            result = (
                Crew(
                    agents=[crew_instance.data_validator_agent()],
                    tasks=[crew_instance.validate_data_quality()],
                    process=Process.sequential,
                    verbose=True,
                    full_output=True,
                )
                .kickoff(inputs={
                    "raw_data": self._raw_data,
                    "price_analysis": self._price_analysis,
                })
            )

            # Store final categorized data
            result_str = result.raw if hasattr(result, 'raw') else str(result)
            try:
                if isinstance(result_str, str) and result_str.startswith('{'):
                    result_data = json.loads(result_str)
                    if isinstance(result_data, dict) and "categorized_data" in result_data:
                        self._price_changes_categorized = result_data["categorized_data"]
                        print(f"[OK] Price changes categorized and extracted")
                        if "validation" in result_data:
                            self._validation_info = result_data["validation"]
                    else:
                        self._price_changes_categorized = result_data
                else:
                    self._price_changes_categorized = {"raw_output": result_str}
            except:
                self._price_changes_categorized = {"raw_output": result_str}

            step_duration = time.time() - step_start
            self._step_times['validate_quality'] = step_duration
            print(f"[OK] Data quality validated")
            print(f"[TIMING] Validate quality: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error validating data quality: {str(e)}")
            raise

    @listen(step_2e_validate_quality)
    def step_3_email_generation(self):
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
                    "effective_date": self._effective_date.strftime('%B %d, %Y'),
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
            self._email_subject = f"TBS Price Change Summary – Effective {self._effective_date.strftime('%B %d, %Y')}"

            print(f"[OK] Email content generated in template format")
            print(f"  Subject: {self._email_subject}")

        except Exception as e:
            error_msg = f"Error in email generation: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise

    @listen(step_3_email_generation)
    def step_4_validation(self):
        """Validation (pass-through for now)"""
        step_start = time.time()

        print("\n" + "-" * 60)
        print("[VALIDATION] Step 4: Validation (Pass-Through)")
        print("-" * 60)

        try:
            # Simple pass-through - store minimal validation data
            self._validation_report = {
                "validation_status": "PASS",
                "quality_score": 100,
                "critical_issues": [],
                "warnings": []
            }
            self._validation_passed = True

            print(f"[OK] Validation PASS (pass-through mode)")

            step_duration = time.time() - step_start
            self._step_times['validation'] = step_duration
            print(f"[TIMING] Validation: {self._format_duration(step_duration)}")

        except Exception as e:
            print(f"[ERROR] Error in validation: {str(e)}")
            raise

    @listen(step_4_validation)
    def step_5_save_output(self):
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
                "effective_date": self._effective_date.isoformat(),
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
