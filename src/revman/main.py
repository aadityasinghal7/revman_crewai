#!/usr/bin/env python
"""
RevMan Price Change Email Flow
Processes Excel price change reports and generates plain text email content in template format.

Refactored to use CrewAI SDK features:
- Task chaining via context parameter
- output_pydantic for type-safe outputs
- Crew kickoff instead of direct tool invocation
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from crewai.flow import Flow, listen, start, persist

from revman.crews.excel_processor_crew import ExcelProcessorCrew
from revman.crews.email_builder_crew import EmailBuilderCrew
from revman.crews.pricing_analysis_crew import PricingAnalysisCrew

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Validate required API keys are properly configured
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    raise ValueError(
        "ANTHROPIC_API_KEY not found in environment. "
        "Please add it to your .env file. "
        "Get your API key from: https://console.anthropic.com/settings/keys"
    )

# Warn if API key has quotes (common .env configuration mistake)
if anthropic_key.startswith('"') or anthropic_key.startswith("'"):
    raise ValueError(
        f"ANTHROPIC_API_KEY appears to have quotes around it: {anthropic_key[:30]}... "
        "Remove quotes from the API key value in your .env file. "
        "API keys should NOT be enclosed in quotes."
    )

# Define file paths using relative path from main.py
# main.py is at: revman/src/revman/main.py
# project_root is at: revman/
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv('REVMAN_DATA_DIR', PROJECT_ROOT / "data"))
INPUT_DIR = Path(os.getenv('REVMAN_INPUT_DIR', DATA_DIR / "input"))
OUTPUT_DIR = Path(os.getenv('REVMAN_OUTPUT_DIR', DATA_DIR / "output"))
TEMPLATE_DIR = Path(os.getenv('REVMAN_TEMPLATE_DIR', DATA_DIR / "templates"))


class RevManFlowState(BaseModel):
    """State model for RevMan Price Change Flow
    
    Consolidated state using Pydantic for type safety and validation.
    All processing results are stored here instead of instance variables.
    """

    # User input - the only field required at kickoff
    excel_file_path: str = "TBS Price Change Summary Report - October 13th'25.xlsx"
    
    # Auto-generated timestamps (stored as ISO strings for JSON serialization)
    trigger_date: Optional[str] = None  # ISO format string
    effective_date: Optional[str] = None  # ISO format string
    
    # Configuration
    email_recipients: Optional[str] = None
    
    # Processing results (populated by flow steps)
    price_changes_categorized: Optional[str] = Field(default_factory=dict)
    pricing_forecast_analysis: Optional[str] = Field(default_factory=dict)
    email_content: Optional[str] = None
    email_subject: Optional[str] = None


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
        # Note: All state is now stored in self.state (RevManFlowState)
        # Instance variables removed - using consolidated Pydantic state

    @start()
    def trigger(self, crewai_trigger_payload: dict = None):
        """
        Initialize flow from trigger

        For POC: Accept file path as parameter (manual trigger)
        For Phase 2: Extract Excel from email (automatic trigger)
        """
        # Initialize state using consolidated Pydantic model
        self.state.trigger_date = datetime.now().isoformat()
        self.state.email_recipients = os.getenv(
            "REVMAN_EMAIL_RECIPIENTS",
            "aaditya.singhal@anheuser-busch.com"
        ).split(",")

        print("\n" + "=" * 60)
        print("[START] RevMan Price Change Flow Started")
        print("=" * 60)

        if crewai_trigger_payload:
            print(f"[OK] Using trigger payload")
        else:
            print(f"[OK] Using default configuration")
        
        # Validate input file exists
        # Initialize excel_path FIRST before any checks
        excel_path = Path(self.state.excel_file_path)

        # Resolve relative paths to absolute using INPUT_DIR
        if not excel_path.is_absolute():
            excel_path = INPUT_DIR / excel_path

        # Additional check: if file doesn't exist and path looks absolute,
        # try extracting just the filename and looking in INPUT_DIR
        # This handles app.crewai.com cloud paths that may not exist but filename does
        if not excel_path.exists() and self.state.excel_file_path.startswith('/'):
            filename = Path(self.state.excel_file_path).name
            excel_path = INPUT_DIR / filename
            print(f"[INFO] Absolute path not found, trying filename in INPUT_DIR: {excel_path}")

        print(f"  File: {self.state.excel_file_path}")
        print(f"  Date: {self.state.trigger_date}")
        print(f"  Recipients: {', '.join(self.state.email_recipients)}")

        # Final validation - raise error if file still doesn't exist
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        # Update state with resolved absolute path
        self.state.excel_file_path = str(excel_path)
        print(f"[OK] Input file validated: {excel_path}\n")

    @listen(trigger)
    def pricing_trend_analysis(self):
        """
        Run Pricing Analysis Crew with SDK task chaining.
        
        - Tasks chain data via context parameter
        - output_pydantic ensures type-safe results
        """
        print("\n" + "-" * 60)
        print("[PRICING] Step 2A: Pricing Trend Analysis (SDK Crew)")
        print("-" * 60)

        try:
            # Build path to historical data file
            historical_file_path = INPUT_DIR / "Historical_price_change_summary_report_vF.xlsx"

            if not historical_file_path.exists():
                print(f"[WARNING] Historical file not found: {historical_file_path}")
                print("[INFO] Skipping pricing trend analysis")
                self.state.pricing_forecast_analysis = {}
                return

            print(f"[INFO] Analyzing historical data via PricingAnalysisCrew")
            print(f"[INFO] Using SDK task chaining (context parameter)")

            # Run PricingAnalysisCrew with SDK task chaining
            # Tasks chain: analyze_historical_trends -> forecast_next_week_prices -> identify_notable_changes
            result = (
                PricingAnalysisCrew()
                .crew()
                .kickoff(inputs={
                    "historical_file_path": str(historical_file_path),
                })
            )

            # Extract result using CrewAI's output_json (SDK-native)
            # With output_json=PricingAnalysisOutput set, CrewAI handles JSON parsing automatically
            if hasattr(result, 'json_dict') and result.json_dict:
                self.state.pricing_forecast_analysis = result.json_dict
            else:
                logger.warning("PricingAnalysisCrew did not return json_dict. Using fallback.")
                self.state.pricing_forecast_analysis = {}

            num_changes = len(self.state.pricing_forecast_analysis.get('top_10_notable_changes', []))

            print(f"[OK] Identified {num_changes} notable price changes")
            if num_changes > 0:
                first_change = self.state.pricing_forecast_analysis.get('top_10_notable_changes', [{}])[0]
                print(f"[DEBUG] Top anomaly: {first_change.get('sku', 'N/A')}")
            print(f"[OK] Pricing trend analysis complete (SDK task chaining)")
            print(f"\n[OK] [STEP 2A COMPLETE] Proceeding to Excel processing...\n")
            import sys
            sys.stdout.flush()

        except Exception as e:
            print(f"[ERROR] Error in pricing trend analysis: {str(e)}")
            print("[INFO] Continuing without pricing forecast data")
            self.state.pricing_forecast_analysis = {}
            import traceback
            traceback.print_exc()

    @listen(pricing_trend_analysis)
    def process_excel(self):
        """
        Process Excel file using ExcelProcessorCrew with SDK task chaining.
        
        - SDK task chaining via context parameter
        - output_pydantic for type-safe results
        - Consolidated state instead of instance variables
        """
        print("\n" + "-" * 60)
        print("[EXCEL] Step 2B: Process Excel File (SDK Crew)")
        print("-" * 60)
        print("[INFO] Running ExcelProcessorCrew with SDK task chaining")
        print("-" * 60)

        try:
            # Run Excel processor crew with SDK task chaining
            result = (
                ExcelProcessorCrew()
                .crew()
                .kickoff(inputs={
                    "excel_file_path": self.state.excel_file_path,
                    "output_dir": str(OUTPUT_DIR),
                })
            )

            # With output_json=PriceCategorizationOutput set, CrewAI handles JSON parsing automatically
            if hasattr(result, 'json_dict') and result.json_dict:
                self.state.price_changes_categorized = result.json_dict
                effective_date_from_result = result.json_dict.get('effective_date_iso')

                # Validate and set effective date
                if effective_date_from_result and effective_date_from_result != '<UNKNOWN>':
                    try:
                        # Validate it's a proper ISO date
                        datetime.fromisoformat(effective_date_from_result)
                        self.state.effective_date = effective_date_from_result
                    except (ValueError, TypeError):
                        # Invalid date format, will use fallback
                        pass

                # Count products for logging
                total_products = result.json_dict.get('total_products', 0)
                print(f"[OK] Price changes categorized: {total_products} products")

                # Display effective date if valid
                if self.state.effective_date:
                    try:
                        print(f"[OK] Effective date: {datetime.fromisoformat(self.state.effective_date).strftime('%B %d, %Y')}")
                    except (ValueError, TypeError):
                        print(f"[WARNING] Could not parse effective date: {self.state.effective_date}")
            else:
                raise ValueError(
                    "ExcelProcessorCrew did not return valid JSON output. "
                    "Check output_json configuration on analyze_price_changes task."
                )

            # Fallback to trigger date if needed
            if not self.state.effective_date or self.state.effective_date == '<UNKNOWN>':
                self.state.effective_date = self.state.trigger_date
                print(f"[WARNING] Using trigger date as fallback: {datetime.fromisoformat(self.state.effective_date).strftime('%B %d, %Y')}")

            print(f"[OK] Excel processing complete")
            print(f"\n[OK] [STEP 2B COMPLETE] Proceeding to email generation...\n")

        except Exception as e:
            print(f"[ERROR] Error in Excel processing: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    @listen(process_excel)
    def email_generation(self):
        """
        Run Email Builder Crew to generate email content.
        Uses consolidated state for all data access.
        """
        print("\n" + "-" * 60)
        print("[EMAIL] Step 3: Email Content Generation")
        print("-" * 60)

        try:
            # Validate categorized data exists
            if not self.state.price_changes_categorized:
                raise ValueError(
                    "No categorized price change data available. Cannot generate email."
                )

            print(f"[OK] Validated categorized data exists")
            effective_dt = datetime.fromisoformat(self.state.effective_date)
            print(f"[INFO] Generating email for: {effective_dt.strftime('%B %d, %Y')}")
            
            # Show pricing forecast status
            if self.state.pricing_forecast_analysis:
                num_changes = len(self.state.pricing_forecast_analysis.get('top_10_notable_changes', []))
                print(f"[INFO] Including {num_changes} notable changes from forecast")
            else:
                print(f"[INFO] No pricing forecast data available")

            # Run Email Builder Crew
            result = (
                EmailBuilderCrew()
                .crew()
                .kickoff(inputs={
                    "price_changes_categorized": self.state.price_changes_categorized,
                    "effective_date": effective_dt.strftime('%B %d, %Y'),
                    "pricing_forecast_analysis": self.state.pricing_forecast_analysis or {},
                })
            )

            # Extract email content
            self.state.email_content = result.raw if hasattr(result, 'raw') else str(result)
            self.state.email_subject = f"TBS Price Change Summary – Effective {effective_dt.strftime('%B %d, %Y')}"

            print(f"[OK] Email content generated")
            print(f"  Subject: {self.state.email_subject}")

        except Exception as e:
            print(f"[ERROR] Error in email generation: {str(e)}")
            raise

    @listen(email_generation)
    def save_output(self):
        """
        Save generated email and metadata to output directory.
        Uses consolidated state for all data access.
        """
        print("\n" + "-" * 60)
        print("[SAVE] Step 4: Save Output")
        print("-" * 60)

        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            trigger_dt = datetime.fromisoformat(self.state.trigger_date)
            timestamp = trigger_dt.strftime("%Y-%m-%d")
            base_filename = f"price_change_email_{timestamp}"

            # Save plain text email
            txt_path = OUTPUT_DIR / f"{base_filename}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(self.state.email_content)
            print(f"[OK] Saved email: {txt_path}")

            # Save metadata
            metadata = {
                "subject": self.state.email_subject,
                "generated_at": datetime.now().isoformat(),
                "trigger_date": self.state.trigger_date,
                "effective_date": self.state.effective_date,
                "input_file": self.state.excel_file_path,
                "recipients": self.state.email_recipients,
            }
            metadata_path = OUTPUT_DIR / f"{base_filename}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"[OK] Saved metadata: {metadata_path}")

            print("\n" + "=" * 60)
            print("[SUCCESS] RevMan Flow Completed Successfully!")
            print("=" * 60)
            print(f"Output: {txt_path}")
            print(f"Subject: {self.state.email_subject}")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"[ERROR] Error saving output: {str(e)}")
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
