**Executive Summary**

Transform the existing code/ worflow into a production-ready Revenue Management system that processes Excel price change reports and generates formatted text email templates using a multi-crew CrewAI Flow architecture.

**Detailed process report**

- Mark receives weekly pricing files from TBS (The Beer Store). As soon as the file is received the process (flow) gets triggered
- Mark takes the Excel file, applies a pre-existing formula to track price changes, and summarizes these changes for an internal email.
- The formula he uses in excel that gives him the context to draft that mail is

\=PROPER(\$D9)&" "&\$H9&\$L9&" "&\$M9&"\$"&ABS(\$K9)&" to \$"&\$J9. This is in column "N" in the input template file (TBS Price Change Summary Report - October 13th'25_template.xlsx)

**Requirements**
4
- Ability to interpret and process Excel files from TBS
- Use of formulas to automate identification of price changes etc. and draft an email

**Inputs data format**

- Historical price tracker spreadsheet with following columns:
  - The columns are: "SAP
  - Art. No."
  - Type of Sale
  - Brewer
  - Product Name
  - Pack Type
  - Pack Volume ml
  - Package Full Name
  - Pack Size
  - Old Price
  - New Price
  - Increase (Decrease)
  - B/C/TC
  - Formula

**Outputs**

- Internal summary emails for TBS: Lists of SKUs with begin/end LTOs grouped by competitor as shown in the template (Output format)
- Output template:

\### Example Format (from actual template):

\`\`\`

Highlights (Price Before Tax and Deposit)

LABATT

Begin LTO

Budweiser 30C -\$5.50 to \$45.99

MSO 24C -\$4 to \$44.99

...

End LTO

Bud Light Lemon Lime 12C +\$2 to \$29.99

...

MOLSON

Begin LTO

\`\`\`

**Additional context**

- **Input Format & Accessibility**
  - TBS sends an email with attachments (retail price list, licensees price list, price change summary report), making it straightforward to access and process.
- **Data Structure & Clarity**
  - TBS files are well-structured, allowing easy identification of brewers, SKUs, and price changes.
- **Processing Steps**
  - Mark uses a fixed formula from previous files to summarize changes and draft the email. The process is mostly formulaic and repeatable.

**Flow Structure**

\`\`\`

FlowState (Pydantic Model)

&nbsp;   ↓

\[@start\] trigger_flow()  ← Triggered by email with title "TBS process"

&nbsp;   ↓

\[@listen\] excel_processing_crew()  ← Crew 1: Excel Parser

&nbsp;   ↓

\[@listen\] email_generation_crew()  ← Crew 2: Email Builder

&nbsp;   ↓

\[@listen\] validation_agent()       ← Light Agent: Validator 🡨 keep this empty for now. We will use this later

**File saving methods**:

\# Define file paths using relative path from main.py

\# main.py is at: revman/src/revman/main.py

\# project_root is at: revman/

PROJECT_ROOT = Path(\__file_\_).parent.parent.parent

DATA_DIR = Path(os.getenv('REVMAN_DATA_DIR', PROJECT_ROOT / "data"))

INPUT_DIR = Path(os.getenv('REVMAN_INPUT_DIR', DATA_DIR / "input"))

OUTPUT_DIR = Path(os.getenv('REVMAN_OUTPUT_DIR', DATA_DIR / "output"))

TEMPLATE_DIR = Path(os.getenv('REVMAN_TEMPLATE_DIR', DATA_DIR / "templates"))