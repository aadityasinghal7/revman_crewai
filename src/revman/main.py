#!/usr/bin/env python
"""
RevMan Price Change Email Flow
Processes Excel price change reports and generates plain text email content in template format
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from pydantic import BaseModel
from crewai.flow import Flow, listen, start, persist

from revman.crews.excel_processor_crew import ExcelProcessorCrew
from revman.crews.email_builder_crew import EmailBuilderCrew
from revman.crews.pricing_analysis_crew import PricingAnalysisCrew

# Load environment variables from .env file
load_dotenv()

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


@persist()
class RevManFlow(Flow[RevManFlowState]):
    """
    RevMan Price Change Email Flow

    Flow orchestrates:
    1. Trigger - Input processing
    2a. Parse Excel file
    2b. Extract effective date
    2c. Generate formula Excel
    2d. Analyze price changes
    2e. Pricing trend analysis and forecasting
    3. Email generation (Crew 2)
    4. Output saving
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
        self._pricing_forecast_analysis: Dict[str, Any] = {}

    @start()
    def trigger(self, crewai_trigger_payload: dict = None):
        """
        Initialize flow from trigger

        For POC: Accept file path as parameter (manual trigger)
        For Phase 2: Extract Excel from email (automatic trigger)
        """
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
        print(f"[OK] Input file validated\n")

    @listen(trigger)
    def process_excel(self):
        """
        Consolidated Excel Processing Step - Run all Excel tasks in single Crew execution
        This allows proper task context chaining for data flow between tasks
        """
        print("\n" + "-" * 60)
        print("[EXCEL] Step 2: Process Excel File (Consolidated)")
        print("-" * 60)
        print("[INFO] Running all Excel processor tasks in single Crew execution")
        print("[INFO] This enables proper task context chaining for data flow")
        print("-" * 60)

        try:
            # Run Excel processor crew using standard .crew() method
            # This enables proper task tracking on app.crewai.com
            result = (
                ExcelProcessorCrew()
                .crew()
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "output_dir": str(OUTPUT_DIR),
                })
            )

            # Extract results from the final task (analyze_price_changes)
            result_str = result.raw if hasattr(result, 'raw') else str(result)

            # Parse the final output
            try:
                if isinstance(result_str, str) and result_str.startswith('{'):
                    result_data = json.loads(result_str)

                    # Direct extraction - no wrapper needed
                    if isinstance(result_data, dict):
                        self._price_changes_categorized = result_data

                        print(f"[OK] Price changes categorized and extracted")

                        # Validate we actually have data
                        total_products = 0
                        for brewer, categories in self._price_changes_categorized.items():
                            if isinstance(categories, dict):
                                for category, products in categories.items():
                                    if isinstance(products, list):
                                        total_products += len(products)
                            elif isinstance(categories, list):
                                total_products += len(categories)

                        print(f"[OK] Total products categorized: {total_products}")

                        # Validate we have actual data
                        if total_products == 0:
                            raise ValueError(
                                "No products were categorized. This likely means the data parsing or "
                                "categorization failed. Check verbose output above for details."
                            )
                    else:
                        self._price_changes_categorized = {"raw_output": result_str}
                        print(f"[WARNING] Unexpected result format - storing as raw output")
                else:
                    self._price_changes_categorized = {"raw_output": result_str}
                    print(f"[WARNING] Non-JSON result - storing as raw output")

            except json.JSONDecodeError as e:
                print(f"[WARNING] Failed to parse JSON result: {str(e)}")
                self._price_changes_categorized = {"raw_output": result_str}
            except Exception as e:
                print(f"[WARNING] Error processing result: {str(e)}")
                self._price_changes_categorized = {"raw_output": result_str}

            # Extract effective date from task results if available
            # Try to get it from the tasks output
            if hasattr(result, 'tasks_output'):
                for task_output in result.tasks_output:
                    if hasattr(task_output, 'raw'):
                        try:
                            task_data = json.loads(task_output.raw)
                            if isinstance(task_data, dict) and 'effective_date_iso' in task_data:
                                self._effective_date = datetime.fromisoformat(task_data['effective_date_iso'])
                                print(f"[OK] Effective date extracted: {self._effective_date.strftime('%B %d, %Y')}")
                                break
                        except:
                            continue

            # Fallback to trigger date if not extracted
            if not self._effective_date:
                self._effective_date = self._trigger_date
                print(f"[WARNING] Using trigger date as fallback: {self._effective_date.strftime('%B %d, %Y')}")

            print(f"[OK] Excel processing complete")
            print(f"\n[OK] [STEP 2 COMPLETE] Proceeding to Step 2B...\n")
            import sys
            sys.stdout.flush()

        except Exception as e:
            print(f"[ERROR] Error in Excel processing: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    @listen(process_excel)
    def pricing_trend_analysis(self):
        """
        Run Pricing Analysis Crew
        - Analyze historical price trends
        - Forecast next week's prices
        - Identify top 10 statistically significant changes
        """
        print("\n" + "-" * 60)
        print("[PRICING] Step 2B: Pricing Trend Analysis")
        print("-" * 60)

        try:
            # Build path to historical data file
            historical_file_path = INPUT_DIR / "Historical_price_change_summary_report_vF.xlsx"

            if not historical_file_path.exists():
                print(f"[WARNING] Historical file not found: {historical_file_path}")
                print("[INFO] Skipping pricing trend analysis")
                self._pricing_forecast_analysis = {}
                return

            print(f"[INFO] Analyzing historical data: {historical_file_path}")

            # Run Pricing Analysis Crew
            result = (
                PricingAnalysisCrew()
                .crew()
                .kickoff(inputs={
                    "historical_file_path": str(historical_file_path),
                })
            )

            # Read results directly from the file saved by AnomalyDetectionTool
            # This is more reliable than parsing the crew result which may include LLM commentary
            anomalies_file = OUTPUT_DIR / "pricing_anomalies.json"

            if anomalies_file.exists():
                try:
                    with open(anomalies_file, 'r') as f:
                        self._pricing_forecast_analysis = json.load(f)

                    # Validate we have top 10 data
                    if 'top_10_notable_changes' in self._pricing_forecast_analysis:
                        num_changes = len(self._pricing_forecast_analysis['top_10_notable_changes'])
                        print(f"[OK] Identified {num_changes} notable price changes")
                    else:
                        print(f"[WARNING] No notable changes in anomalies file")
                        self._pricing_forecast_analysis = {}
                except (json.JSONDecodeError, IOError) as e:
                    print(f"[WARNING] Failed to read pricing anomalies file: {str(e)}")
                    self._pricing_forecast_analysis = {}
            else:
                print(f"[WARNING] Anomalies file not found: {anomalies_file}")
                self._pricing_forecast_analysis = {}

            print(f"[OK] Pricing trend analysis complete")
            print(f"\n[OK] [STEP 2B COMPLETE] Proceeding to Step 3...\n")
            import sys
            sys.stdout.flush()

        except Exception as e:
            print(f"[ERROR] Error in pricing trend analysis: {str(e)}")
            print("[INFO] Continuing without pricing forecast data")
            self._pricing_forecast_analysis = {}
            import traceback
            traceback.print_exc()

    @listen(pricing_trend_analysis)
    def email_generation(self):
        """
        Run Email Builder Crew (Crew 2)
        - Generate highlights content in plain text template format
        """
        print("\n" + "-" * 60)
        print("[EMAIL] Step 3: Email Content Generation")
        print("-" * 60)

        try:
            # Validate we have categorized data before generating email
            if not self._price_changes_categorized:
                raise ValueError(
                    "No categorized price change data available. Cannot generate email. "
                    "Check Excel processing step for errors."
                )

            print(f"[OK] Validated categorized data exists")
            print(f"[INFO] Generating email for effective date: {self._effective_date.strftime('%B %d, %Y')}")

            # Kick off Email Builder Crew
            result = (
                EmailBuilderCrew()
                .crew()
                .kickoff(inputs={
                    "price_changes_categorized": self._price_changes_categorized,
                    "effective_date": self._effective_date.strftime('%B %d, %Y'),
                    "pricing_forecast_analysis": self._pricing_forecast_analysis,
                })
            )

            print(f"[OK] Email content generation completed")

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

    @listen(email_generation)
    def save_output(self):
        """
        Save generated email to output directory
        - Save plain text email in template format
        - Save metadata
        """
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
                "recipients": self._email_recipients,
            }
            metadata_path = OUTPUT_DIR / f"{base_filename}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Saved metadata: {metadata_path}")

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
