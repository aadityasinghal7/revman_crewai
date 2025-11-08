# RevMan TBS Price Change Email Automation - Implementation Plan

## Executive Summary

Transform Mark's manual TBS (The Beer Store) price change email workflow into a production-ready automated Revenue Management system. The solution uses CrewAI's multi-crew Flow architecture to process Excel price change reports and generate formatted email summaries automatically.

### Current Manual Process

Mark receives weekly pricing files from TBS via email. His current workflow:
1. Downloads Excel file attachment (TBS Price Change Summary Report)
2. Opens Excel and applies a formula to column N to format price changes
3. Reviews the formula output to identify Begin LTO / End LTO patterns
4. Manually drafts an internal email grouping changes by brewer (LABATT, MOLSON, SLEEMAN)
5. Sends summary to stakeholders

**The Formula Mark Uses:**
```excel
=PROPER($D9)&" "&$H9&$L9&" "&$M9&"$"&ABS($K9)&" to $"&$J9
```
This formula (in column N) combines:
- Product Name (Column D, proper case)
- Pack Size (Column H)
- B/C/TC indicator (Column L)
- Price change direction (Column M: + or -)
- Price change amount (Column K, absolute value)
- New Price (Column J)

**Example Output:** `Budweiser 30C -$5.50 to $45.99`

### Automated Solution

The automated system will:
- **Trigger:** Receive email with subject "TBS process" containing Excel attachment
- **Process:** Parse Excel, apply formula logic, categorize by brewer and change type
- **Generate:** Formatted email content matching Mark's output template
- **Deliver:** Save to output directory (future: auto-send email)

---

## Business Requirements

### Problem Statement

Mark spends 30-45 minutes weekly processing TBS price change files. The process is formulaic and repeatable, making it ideal for automation. The goal is to eliminate manual work while maintaining the same output format stakeholders expect.

### Success Criteria

- ✅ Automatically process TBS Excel files when received via email
- ✅ Apply Mark's formula logic to generate formatted price change lines
- ✅ Categorize changes by brewer (LABATT, MOLSON, SLEEMAN, etc.)
- ✅ Organize by change type (Begin LTO, End LTO, Permanent Changes)
- ✅ Generate email content in exact template format
- ✅ Reduce processing time from 30-45 minutes to < 2 minutes
- ✅ Maintain 100% format consistency with existing emails

### Input Requirements

**Source:** Email from TBS with attachments:
- **TBS Price Change Summary Report** (primary input)

**Email Trigger:**
- **Subject:** "TBS process"
- **Attachments:** Excel file (.xlsx)

**Excel Structure:**
- **Header Rows:** First 6 rows (skip these)
- **Data Start:** Row 7
- **Total Records:** ~150-200 product price changes

**Required Columns:**

| Column | Name | Description |
|--------|------|-------------|
| A | SAP Art. No. | Article Number |
| B | Type of Sale | e.g., "TBS - Retail Price" |
| C | Brewer | LABATT, MOLSON, SLEEMAN, etc. |
| D | Product Name | e.g., "Budweiser", "Corona" |
| E | Pack Type | Bottles, Cans, Tall Cans |
| F | Pack Volume ml | Volume in milliliters |
| G | Package Full Name | Full package description |
| H | Pack Size | e.g., "30C", "24B", "12TC" |
| I | Old Price | Previous price |
| J | New Price | New price |
| K | Increase/(Decrease) | Price change amount |
| L | B/C/TC | Bottle/Can/Tall Can indicator |
| M | Formula | Mark's Excel formula output (Column N in his file) |

### Output Requirements

**Format:** Plain text email content (not HTML)

**Template Structure:**
```
Highlights (Price Before Tax and Deposit)

LABATT
Begin LTO
Budweiser 30C -$5.50 to $45.99
MSO 24C -$4 to $44.99
...

End LTO
Bud Light Lemon Lime 12C +$2 to $29.99
...
...

MOLSON
Begin LTO
...
```

**Line Format:**
```
Product Name PackSize +/-$Amount to $FinalPrice
```

**Categorization Rules:**
- **Begin LTO:** Any price reduction that is a multiple of $0.25, that reduces the total price by more than 5% is a begin LTO
- **End LTO:** Any price increase that is a multiple of $0.25, that increases the total price by more than 5% is an end LTO

**Reference Template:**
For detailed examples and exact formatting expectations, refer to:
- **File:** `data/templates/Output format.docx`
- **Purpose:** Contains actual examples of Mark's email format with real product data
- **Usage:** Agents can reference this document to understand the precise output structure and formatting nuances

---

## Architecture Overview

### Flow Structure

```
RevManFlow (CrewAI Flow)
    │
    ├─ FlowState (Pydantic Model)
    │   ├─ Input: excel_file_path, trigger_date, recipients
    │   └─ Output: email_content, email_subject, metadata
    │
    ├─ [@start] trigger_flow()
    │   └─ Triggered by: Email with subject "TBS process"
    │   └─ Validates: Input file exists and is readable
    │
    ├─ [@listen] excel_processing_crew()  ← CREW 1
    │   ├─ excel_parser_agent
    │   │   ├─ Task: parse_excel_file
    │   │   └─ Task: generate_formula_excel
    │   ├─ data_analyst_agent
    │   │   └─ Task: analyze_price_changes
    │   └─ data_validator_agent
    │       └─ Task: validate_data_quality
    │
    ├─ [@listen] email_generation_crew()  ← CREW 2
    │   └─ email_content_writer_agent
    │       └─ Task: write_highlights_content
    │
    ├─ [@listen] validation_step()  ← LIGHT VALIDATION
    │   └─ Basic checks (minimal for now)
    │
    └─ [@listen] save_email_output()
        └─ Saves: .txt, _metadata.json, _validation.json
```

### Flow State Model

```python
class RevManFlowState(BaseModel):
    """State model for RevMan Price Change Flow"""

    # Input
    excel_file_path: str  # Path to TBS Excel file
    trigger_date: datetime  # When flow was triggered
    email_recipients: List[str]  # Who receives the email

    # Output
    email_content: str  # Plain text email in template format
    email_subject: str  # e.g., "TBS Price Change Summary - Nov 7, 2025"
    email_metadata: Dict[str, Any]  # Stats, record count, etc.
```

**Data Flow:**
1. **Input:** Excel file path from trigger
2. **Crew 1 Output:** Categorized price changes (internal variable)
3. **Crew 2 Output:** Formatted email content → FlowState
4. **Validation Output:** Quality checks (internal variable)
5. **Final Output:** Files saved to `data/output/`

---

## Component Details

### Crew 1: Excel Processor Crew

**Purpose:** Parse Excel file, apply formula logic, and categorize price changes

**Location:** `src/revman/crews/excel_processor_crew/`

#### Agents

**1. excel_parser_agent**
- **Role:** Excel Data Parser Specialist
- **Goal:** Parse TBS Excel file starting at row 7, extract all columns
- **Key Skills:**
  - Skip header rows (first 6 rows)
  - Handle data type conversions
  - Clean formatting issues
  - Remove null rows

**2. data_analyst_agent**
- **Role:** Price Change Categorization Specialist
- **Goal:** Apply Mark's formula logic and categorize by brewer/change type
- **Key Skills:**
  - Replicate Excel formula: `PROPER(Product) PackSize +/-$Change to $NewPrice`
  - Categorize: Begin LTO (decreases), End LTO (increases), Permanent Changes
  - Group by brewer (LABATT, MOLSON, SLEEMAN)
  - Filter highlights (significant changes only)

**3. data_validator_agent**
- **Role:** Data Quality Validator
- **Goal:** Ensure calculations are correct and data is complete
- **Key Skills:**
  - Verify: `Old Price - New Price = Change`
  - Check Begin LTO has negative changes
  - Check End LTO has positive changes
  - Flag missing fields or outliers

#### Tasks

**Task 1: parse_excel_file**
```yaml
Agent: excel_parser_agent
Input: {excel_file_path}
Output: List of dictionaries with all product records
Key Actions:
  - Skip rows 1-6
  - Extract columns A-M
  - Clean and convert data types
  - Return structured JSON
```

**Task 2: generate_formula_excel**
```yaml
Agent: excel_parser_agent
Input: {excel_file_path}, {output_dir}
Output: Path to generated Excel file with formulas
Key Actions:
  - Create copy of input Excel file
  - Add formula to column N for each data row
  - Formula: =PROPER($D{row})&" "&$H{row}&$L{row}&" "&$M{row}&"$"&ABS($K{row})
  - Automatically adjust row numbers based on data start position
  - Extract month/date from input filename
  - Save as: "TBS Price Change Summary Report - {Month} {day}th'{YY}_formula.xlsx"
  - Save to output directory
Tools Used:
  - FormulaExcelGeneratorTool
Purpose:
  - Provides Excel version with formulas for Mark to review
  - Matches Mark's manual workflow of adding formulas
  - Allows verification of formula calculations in Excel
```

**Task 3: analyze_price_changes**
```yaml
Agent: data_analyst_agent
Input: Parsed data from Task 1
Output: Categorized changes grouped by brewer and type
Key Actions:
  - Apply formula logic: PROPER(Product) + PackSize + +/-$Amount + to $NewPrice
  - Categorize by change direction (Begin/End LTO)
  - Group by brewer
  - Filter significant changes (highlights only - 5% + $0.25 multiples)
Format:
  {
    "LABATT": {
      "Begin LTO": ["Budweiser 30C -$5.50 to $45.99", ...],
      "End LTO": ["Bud Light 12C +$2 to $29.99", ...]
    },
    "MOLSON": {...},
    "SLEEMAN": {...}
  }
```

**Task 4: validate_data_quality**
```yaml
Agent: data_validator_agent
Input: Parsed data + Categorized data
Output: Validation report + Categorized data (passthrough)
Key Actions:
  - Check calculation accuracy
  - Verify categorization logic
  - Flag outliers (> $20 changes)
  - Return BOTH validation report AND categorized data
Critical: Must output categorized_data for next crew
```

---

### Crew 2: Email Builder Crew

**Purpose:** Transform categorized data into formatted email template

**Location:** `src/revman/crews/email_builder_crew/`

#### Agent

**email_content_writer_agent**
- **Role:** Price Change Highlights Writer
- **Goal:** Generate email content in exact template format
- **Key Skills:**
  - Follow template structure precisely
  - Title: "Highlights (Price Before Tax and Deposit)"
  - Group by brewer → categorize by change type
  - Format lines correctly

#### Task

**Task: write_highlights_content**
```yaml
Agent: email_content_writer_agent
Input: {price_changes_categorized}
Output: Plain text email content

Structure:
  1. Title: "Highlights (Price Before Tax and Deposit)"
  2. For each brewer (LABATT, MOLSON, SLEEMAN):
     - Brewer name as header
     - Begin LTO section
     - End LTO section
     - Blank line between brewers

Format: Plain text, NOT HTML

Reference: If needed, agent can read data/templates/Output format.docx for detailed
formatting examples and additional context on expected output structure
```

---

### Light Validation Agent

**Purpose:** Final quality checks before saving

**Location:** Inline in `main.py` (not a full crew)

**Current Implementation:** Minimal validation
- Check for required title: "Highlights (Price Before Tax and Deposit)"
- Verify at least one brewer section exists
- Check for change type sections (Begin LTO, End LTO)

**Status:** ✅ Basic validation implemented, more comprehensive checks deferred to future phase

---

## File Structure

### Project Layout

```
revman/                                  # Project root
├── src/revman/
│   ├── main.py                          # Main Flow definition
│   ├── crews/
│   │   ├── excel_processor_crew/        # Crew 1
│   │   │   ├── excel_processor_crew.py
│   │   │   └── config/
│   │   │       ├── agents.yaml
│   │   │       └── tasks.yaml
│   │   └── email_builder_crew/          # Crew 2
│   │       ├── email_builder_crew.py
│   │       └── config/
│   │           ├── agents.yaml
│   │           └── tasks.yaml
│   └── tools/
│       ├── excel_tools.py               # (Future: Custom Excel tools)
│       └── email_tools.py               # (Future: Email validation tools)
├── data/
│   ├── input/                           # Incoming Excel files
│   │   └── TBS Price Change Summary Report - October 13th'25.xlsx
│   ├── templates/                       # Reference templates
│   │   ├── Output format.docx
│   │   └── plan_md_template.md
│   └── output/                          # Generated emails
│       ├── price_change_email_2025-11-07.txt
│       ├── price_change_email_2025-11-07_metadata.json
│       └── price_change_email_2025-11-07_validation.json
├── tests/                               # (Future: Test suite)
├── .env                                 # Environment configuration
└── pyproject.toml                       # Dependencies
```

### File Path Configuration

**In `main.py`:**
```python
# Define file paths using relative path from main.py
# main.py is at: revman/src/revman/main.py
# project_root is at: revman/

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv('REVMAN_DATA_DIR', PROJECT_ROOT / "data"))
INPUT_DIR = Path(os.getenv('REVMAN_INPUT_DIR', DATA_DIR / "input"))
OUTPUT_DIR = Path(os.getenv('REVMAN_OUTPUT_DIR', DATA_DIR / "output"))
TEMPLATE_DIR = Path(os.getenv('REVMAN_TEMPLATE_DIR', DATA_DIR / "templates"))
```

---

## Configuration

### Environment Variables (.env)

```bash
# API Key
ANTHROPIC_API_KEY=your_anthropic_key_here

# Data Directories (relative to project root: revman/)
REVMAN_DATA_DIR=./data
REVMAN_INPUT_DIR=./data/input
REVMAN_OUTPUT_DIR=./data/output
REVMAN_TEMPLATE_DIR=./data/templates

# Email Trigger Configuration (Future Phase)
# EMAIL_TRIGGER_ENABLED=false
# EMAIL_TRIGGER_SUBJECT=TBS process
# EMAIL_TRIGGER_MAILBOX=mark@abi.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/revman.log
```

### Dependencies (pyproject.toml)

```toml
dependencies = [
    "crewai[tools]>=0.86.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "python-docx>=1.0.0",
]
```

---

## Execution

### Running the Flow

**Manual Trigger (Current POC):**
```bash
# From project root: revman/
crewai run
```

This uses the default file path configured in `RevManFlowState`:
```python
excel_file_path: str = r"C:\Users\...\data\input\TBS Price Change Summary Report - October 13th'25.xlsx"
```

**With Custom Trigger Payload:**
```bash
crewai run_with_trigger '{"excel_file_path": "./data/input/file.xlsx", "trigger_date": "2025-11-07T00:00:00Z"}'
```

### Email Trigger (Future Phase)

**Trigger Specification:**
- **Subject:** "TBS process"
- **Sender:** TBS (any email containing Excel attachment)
- **Attachment:** Excel file (.xlsx)
- **Action:** Automatically extract Excel, save to `data/input/`, trigger flow

**Implementation Options:**
1. IMAP email polling
2. Microsoft Graph API (recommended for ABI Office 365)
3. Email service webhook

---

## Output

### Generated Files

When the flow completes, it saves four files to `data/output/`:

**1. Email Content (.txt)**
```
price_change_email_2025-11-07.txt
```
Plain text email in template format, ready to copy/paste into email client.

**2. Formula Excel File (.xlsx)**
```
TBS Price Change Summary Report - October 13th'25_formula.xlsx
```
A copy of the input Excel file with formulas added to column N. The formula combines product information to create formatted price change text:
- Formula: `=PROPER($D{row})&" "&$H{row}&$L{row}&" "&$M{row}&"$"&ABS($K{row})`
- Automatically adjusts row numbers based on where data starts
- Matches Mark's manual workflow of adding formulas in Excel
- Can be opened directly in Excel to view calculated values

**3. Metadata (.json)**
```json
{
  "subject": "TBS Price Change Summary - November 07, 2025",
  "generated_at": "2025-11-07T14:23:45",
  "trigger_date": "2025-11-07T00:00:00",
  "input_file": "C:\\...\\data\\input\\TBS Price Change Summary Report - October 13th'25.xlsx",
  "validation_passed": true,
  "recipients": ["aaditya.singhal@anheuser-busch.com"]
}
```

**4. Validation Report (.json)**
```json
{
  "validation_status": "PASS",
  "quality_score": 100,
  "critical_issues": [],
  "warnings": []
}
```

### Sample Output

```
Highlights (Price Before Tax and Deposit)

LABATT
Begin LTO
Budweiser 30C -$5.50 to $45.99
MSO 24C -$4 to $44.99
Bud Light Lime 12C -$3 to $27.49

End LTO
Bud Light Lemon Lime 12C +$2 to $29.99
Michelob Ultra 24B +$2.50 to $58.99

Permanent Changes
Bud Light 28B -$0.50 to $43.49

MOLSON
Begin LTO
Coors Light 30C -$4 to $45.49
Molson Canadian 24C -$3.50 to $42.99
...
```

---

## Testing & Validation

### Testing Approach

**Unit Testing (Future):**
- Test Excel parser with sample files
- Test formula logic accuracy
- Test categorization rules
- Test email formatting

**Integration Testing (Current):**
- End-to-end flow execution with real TBS file
- Manual review of generated email content
- Verify format matches Mark's template
- Check calculations against Excel formula

### Validation Checks

**Data Quality:**
- ✅ All required columns present
- ✅ No missing product names, prices, or brewers
- ✅ Price calculations are correct (Old - New = Change)

**Categorization:**
- ✅ Begin LTO entries have negative changes
- ✅ End LTO entries have positive changes
- ✅ Products grouped correctly by brewer

**Output Format:**
- ✅ Title present: "Highlights (Price Before Tax and Deposit)"
- ✅ Brewer sections exist (LABATT, MOLSON, SLEEMAN)
- ✅ Change type sections present (Begin LTO, End LTO, etc.)
- ✅ Line format matches: `Product PackSize +/-$X to $Y`

---

## Implementation Status

### ✅ Completed (POC Phase)

- [x] Flow architecture designed and implemented
- [x] Excel Processor Crew with 3 agents
- [x] Email Builder Crew with 1 agent
- [x] Formula logic replicated in data_analyst_agent
- [x] Plain text email generation
- [x] Basic validation
- [x] File output to data/output/
- [x] Manual trigger via `crewai run`

### 🚧 In Progress

- [ ] Enhanced validation rules
- [ ] Custom Excel tools for complex parsing
- [ ] Error handling improvements

### 📋 Future Enhancements

**Phase 2: Email Integration**
- [ ] Email trigger setup (subject: "TBS process")
- [ ] Automatic Excel attachment extraction
- [ ] Email sending capability
- [ ] Recipient configuration

**Phase 3: Advanced Features**
- [ ] Historical comparison (current vs previous week)
- [ ] Alert system for unusual price changes
- [ ] Multiple output formats (HTML email option)
- [ ] Approval workflow before sending

**Phase 4: Analytics & Monitoring**
- [ ] Dashboard for monitoring flow executions
- [ ] Price change trend analysis
- [ ] Performance metrics tracking
- [ ] Audit logging

---

## Implementation Checklist

This section documents the code changes required to align the current implementation with the plan requirements above.

### Critical Priority (Must Fix - System Won't Run)

#### 1. main.py - Add Missing Path Constants ⚠️ BLOCKING

**File:** `src/revman/main.py`
**Lines:** After line 19 (after imports)
**Issue:** Code references `OUTPUT_DIR` at lines 268, 275, 289, 295 but it's never defined. System will crash when saving output.

**Fix Required:**
```python
# Define file paths using relative path from main.py
# main.py is at: revman/src/revman/main.py
# project_root is at: revman/
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv('REVMAN_DATA_DIR', PROJECT_ROOT / "data"))
INPUT_DIR = Path(os.getenv('REVMAN_INPUT_DIR', DATA_DIR / "input"))
OUTPUT_DIR = Path(os.getenv('REVMAN_OUTPUT_DIR', DATA_DIR / "output"))
TEMPLATE_DIR = Path(os.getenv('REVMAN_TEMPLATE_DIR', DATA_DIR / "templates"))
```

---

### Important Priority (Fix Core Logic/Output)

#### 2. excel_processor_crew/config/tasks.yaml - Fix analyze_price_changes Task

**File:** `src/revman/crews/excel_processor_crew/config/tasks.yaml`
**Lines:** 35-97

**Issues:**
- ❌ Missing precise categorization rules (5% threshold, $0.25 multiples)
- ❌ Includes "Permanent Changes" category (should be removed)
- ❌ Instructs agent to add business context (should NOT add context)
- ❌ Has "INTELLIGENT FILTERING" section (should use only categorization rules)

**Required Changes:**

**Lines 42-45** - Fix categorization logic:
```yaml
# OLD (WRONG):
2. Within each brewer, categorize changes by type:
   - "Begin LTO" - Price DECREASES indicating start of Limited Time Offers
   - "End LTO" - Price INCREASES indicating end of Limited Time Offers
   - "Permanent Changes" - Ongoing price adjustments (small changes, typically < $1)

# NEW (CORRECT):
2. Within each brewer, categorize changes using PRECISE rules:
   - "Begin LTO" - Price DECREASES that are multiples of $0.25 AND reduce price by >5%
   - "End LTO" - Price INCREASES that are multiples of $0.25 AND increase price by >5%
   NOTE: These are the ONLY two categories. No other categories exist.
```

**Lines 50-61** - Remove business context and filtering:
```yaml
# REMOVE these lines entirely:
- Identify business context when applicable:
  * "increased depth as a competitive response" (large decreases)
  * "end SCO mitigation" (price increases after promotion)
  ...
- Format as: "Product Name PackSize +/-$X.XX to $YY.YY (optional context)"

INTELLIGENT FILTERING:
- Focus on highlights only (significant changes, strategic moves)
...

# REPLACE with:
FOR EACH PRODUCT:
- Calculate: price_change_percent = abs((change_amount / old_price) * 100)
- Check: is_quarter_multiple = (abs(change_amount) % 0.25) < 0.01
- Categorize using 5% + $0.25 rules above
- Format as: "Product Name PackSize +/-$X.XX to $YY.YY" (NO context)
```

**Lines 64-87** - Fix expected output format:
```yaml
# Remove all business context examples like:
"Budweiser 30C -$5.50 to $45.99 (increased depth as a competitive response)"

# Replace with simple format:
"Budweiser 30C -$5.50 to $45.99"
```

#### 3. excel_processor_crew/config/agents.yaml - Update data_analyst_agent

**File:** `src/revman/crews/excel_processor_crew/config/agents.yaml`
**Lines:** 11-20

**Issue:** Agent backstory mentions business context inference and vague categorization rules

**Fix Required:**
```yaml
# OLD (Lines 13-20):
goal: Categorize price changes by brewer and change type (LTO vs Permanent) with business context
backstory: >
  ABI pricing strategy expert with deep understanding of Limited Time Offers (LTO),
  competitive responses, and SCO mitigation tactics...
  You can infer business context from competitive positioning...

# NEW:
goal: Apply Mark's formula logic and categorize price changes using precise mathematical rules
backstory: >
  Expert in applying Mark's Excel formula to format price changes. Skilled at precise categorization
  using the 5% threshold rule and $0.25 multiple detection. You understand that:
  - Begin LTO: Price reductions that are multiples of $0.25 AND reduce total price by >5%
  - End LTO: Price increases that are multiples of $0.25 AND increase total price by >5%
  You format output as: PROPER(Product) PackSize +/-$Change to $NewPrice
  You do NOT add business context or strategic commentary.
```

#### 4. email_builder_crew/config/tasks.yaml - Fix write_highlights_content Task

**File:** `src/revman/crews/email_builder_crew/config/tasks.yaml`
**Lines:** 1-62

**Issues:**
- ❌ Lists "Permanent Changes" section (should be removed)
- ❌ Instructs agent to add business context (should NOT)

**Required Changes:**

**Lines 15-17** - Remove deprecated sections:
```yaml
# OLD:
- "End LTO" section with price increases
- "End LTO & Perm Change" section (if applicable)
- "Permanent Changes" section (if applicable)

# NEW:
- "End LTO" section with price increases (>5%, $0.25 multiples)
(Remove the other two lines)
```

**Lines 27-32** - Remove business context instructions:
```yaml
# REMOVE this entire section:
BUSINESS CONTEXT:
Add context where appropriate explaining WHY the change is happening:
- "increased depth as a competitive response"
...

# REPLACE with:
FORMAT RULES:
- Use EXACT format: Product PackSize +/-$Amount to $FinalPrice
- Do NOT add any business context, commentary, or explanatory notes
- Present data cleanly without additional interpretation
```

#### 5. email_builder_crew/config/agents.yaml - Update email_content_writer_agent

**File:** `src/revman/crews/email_builder_crew/config/agents.yaml`
**Lines:** 1-11

**Issue:** Backstory mentions business context and optional context in format

**Fix Required:**
```yaml
# OLD (Lines 5-10):
backstory: >
  Expert in ABI pricing communications with deep understanding of business context
  (LTO strategy, competitive responses, SCO mitigation)...
  "Product PackSize +/-$Amount to $FinalPrice (optional context)".

# NEW:
backstory: >
  Expert in formatting price change data into the standard "Highlights (Price Before Tax and Deposit)"
  template. Skilled at organizing data by Brewer (LABATT, MOLSON, SLEEMAN) with subsections for
  Begin LTO and End LTO. Each line follows the exact format:
  "Product PackSize +/-$Amount to $FinalPrice" with NO additional context or commentary.
```

#### 6. tools/excel_tools.py - Fix PriceCalculatorTool Categorization Logic

**File:** `src/revman/tools/excel_tools.py`
**Lines:** 173-179

**Issue:** Simple logic (just checks if positive/negative) - Missing 5% threshold and $0.25 multiple checks

**Fix Required:**
```python
# OLD (Lines 173-179):
if change_amount < 0:
    direction = "decrease"
    change_type = "Begin LTO"  # Price decreases indicate LTO start
elif change_amount > 0:
    direction = "increase"
    change_type = "End LTO"  # Price increases indicate LTO end

# NEW:
# Calculate percentage change
change_percent = abs((change_amount / old_price) * 100) if old_price != 0 else 0

# Check if multiple of $0.25 (with float tolerance)
is_quarter_multiple = (abs(change_amount) % 0.25) < 0.01

# Determine category based on plan.md rules
if change_amount < 0:
    direction = "decrease"
    if is_quarter_multiple and change_percent > 5:
        change_type = "Begin LTO"
    else:
        change_type = "Not Categorized"  # Doesn't meet LTO criteria
elif change_amount > 0:
    direction = "increase"
    if is_quarter_multiple and change_percent > 5:
        change_type = "End LTO"
    else:
        change_type = "Not Categorized"  # Doesn't meet LTO criteria
```

#### 7. tools/email_tools.py - Remove HTML Formatter

**File:** `src/revman/tools/email_tools.py`
**Lines:** Entire file

**Issue:** Contains `TextToHTMLFormatterTool` but plan.md says plain text only

**Plan.md Decision (lines 617-625):**
> Decision: Generate plain text email content, not HTML
> Rationale: Matches Mark's current workflow (copy/paste into email)

**Fix Required:**
- Keep only `EmailValidatorTool`
- Remove entire `TextToHTMLFormatterTool` class (currently ~200+ lines)
- Update `EmailValidatorTool` to validate plain text instead of HTML

#### 8. tools/__init__.py - Remove HTML Tool Export

**File:** `src/revman/tools/__init__.py`
**Lines:** 4

**Issue:** Exports `TextToHTMLFormatterTool` which should be removed

**Fix Required:**
```python
# OLD:
from .email_tools import TextToHTMLFormatterTool, EmailValidatorTool

# NEW:
from .email_tools import EmailValidatorTool

# Update __all__:
__all__ = [
    "ExcelReaderTool",
    "DataCleanerTool",
    "PriceCalculatorTool",
    "EmailValidatorTool",
]
```

#### 9. main.py - Add Validation for Deprecated Sections

**File:** `src/revman/main.py`
**Lines:** After line 219 in validation_step()

**Issue:** Validation doesn't check for deprecated sections

**Fix Required:**
```python
# Add after line 219:

# Check for deprecated sections that should not exist
if "Permanent Changes" in content or "End LTO & Perm Change" in content:
    validation_data["warnings"].append(
        "Found deprecated section: 'Permanent Changes' or 'End LTO & Perm Change'. "
        "Only 'Begin LTO' and 'End LTO' sections should exist per plan.md."
    )
```

---

### Nice-to-Have Priority (Cleanup)

#### 10. main.py - Fix Hardcoded Path

**File:** `src/revman/main.py`
**Line:** 27

**Issue:** Uses absolute hardcoded path instead of INPUT_DIR constant

**Fix Required:**
```python
# OLD:
excel_file_path: str = r"C:\Users\Y946107\OneDrive - Anheuser-Busch InBev\FY25\Personal git repo\RevMan-POC-Crew\revman\data\input\TBS Price Change Summary Report - October 13th'25.xlsx"

# NEW:
excel_file_path: str = str(INPUT_DIR / "TBS Price Change Summary Report - October 13th'25.xlsx")
```

#### 11. main.py - Fix Phase Number Comment

**File:** `src/revman/main.py`
**Line:** 55

**Issue:** Comment says "Phase 8" but plan.md calls it "Phase 2"

**Fix Required:**
```python
# OLD:
For Phase 8: Extract Excel from email (automatic trigger)

# NEW:
For Phase 2: Extract Excel from email (automatic trigger)
```

---

### Implementation Order

Execute changes in this order to avoid breaking the system:

1. ✅ **FIRST** - Fix main.py path constants (item #1) - CRITICAL
2. ✅ Update excel_processor_crew tasks.yaml (item #2)
3. ✅ Update excel_processor_crew agents.yaml (item #3)
4. ✅ Update email_builder_crew tasks.yaml (item #4)
5. ✅ Update email_builder_crew agents.yaml (item #5)
6. ✅ Fix tools/excel_tools.py (item #6)
7. ✅ Cleanup tools/email_tools.py (item #7)
8. ✅ Update tools/__init__.py (item #8)
9. ✅ Update main.py validation (item #9)
10. ✅ Cleanup main.py path and comments (items #10, #11)

---

### Files That Don't Need Changes

✅ **excel_processor_crew/excel_processor_crew.py** - Implementation correct
✅ **email_builder_crew/email_builder_crew.py** - Implementation correct
✅ **data_validator_agent** - Kept as placeholder (minimal validation only, comprehensive validation deferred to future phase)
✅ **.env** - Configuration correct
✅ **Task structure** - Sequential flow correct

---

## Key Design Decisions

### 1. Formula Replication via AI Agents

**Decision:** Use AI agents to replicate Mark's Excel formula logic rather than directly executing Excel formulas

**Rationale:**
- More flexible - can add business context and intelligence
- Easier to maintain and modify logic
- Can handle edge cases better than rigid formulas
- Enables future enhancements (comparative analysis, anomaly detection)

**How It Works:**
The `data_analyst_agent` understands the formula pattern and generates equivalent output:
```
Excel Formula: =PROPER($D9)&" "&$H9&$L9&" "&$M9&"$"&ABS($K9)&" to $"&$J9
Agent Output:  Budweiser 30C -$5.50 to $45.99
```

### 2. Plain Text Email (Not HTML)

**Decision:** Generate plain text email content, not HTML

**Rationale:**
- Matches Mark's current workflow (copy/paste into email)
- Simpler to validate and test
- Easier to modify manually if needed
- Can add HTML formatting in future phase if requested

### 3. Sequential Crew Execution

**Decision:** Crews execute sequentially in order

**Rationale:**
- Clear dependency: Crew 2 needs Crew 1 output
- Easier to debug and monitor
- Matches CrewAI Flow @listen pattern
- Predictable execution flow

### 4. Minimal Validation (Current Phase)

**Decision:** Keep validation simple for POC

**Rationale:**
- Focus on core functionality first
- Can enhance validation incrementally
- Basic checks catch major issues
- Comprehensive validation deferred to Phase 2

### 5. File-Based Output

**Decision:** Save to local files instead of sending email immediately

**Rationale:**
- Safer for POC - human can review before sending
- Enables testing without spam risk
- Easy to integrate email sending later
- Provides audit trail

---

## Success Metrics

### Performance Targets

- **Execution Time:** < 2 minutes (vs 30-45 minutes manual)
- **Accuracy:** 100% (formula output matches Excel)
- **Format Compliance:** 100% (matches template exactly)
- **Automation Rate:** 100% (zero manual intervention)

### Quality Metrics

- ✅ Zero calculation errors
- ✅ All brewers properly categorized
- ✅ Correct Begin/End LTO classification
- ✅ Proper line formatting
- ✅ Complete data coverage (no missing products)

---

## Troubleshooting

### Common Issues

**Issue 1: Excel file not found**
```
Error: FileNotFoundError
Solution: Check excel_file_path in RevManFlowState or trigger payload
```

**Issue 2: Empty email output**
```
Cause: No price changes in data or parsing error
Solution: Check validation report for errors, review Excel structure
```

**Issue 3: Missing brewer sections**
```
Cause: Categorization agent didn't find products for that brewer
Solution: Verify brewer names in Excel match expected values (LABATT, MOLSON, SLEEMAN)
```

**Issue 4: Formula format doesn't match**
```
Cause: data_analyst_agent needs clearer instructions
Solution: Review task description in tasks.yaml, add examples
```

---

## Next Steps

### Immediate Actions

1. **Test with new TBS file** - Validate flow works with latest weekly data
2. **Review output quality** - Compare generated email to Mark's manual version
3. **Gather stakeholder feedback** - Show output to email recipients
4. **Document any edge cases** - Track issues for enhancement

### Phase 2 Planning

1. **Email trigger setup** - Design email monitoring approach
2. **Attachment extraction** - Build logic to extract Excel from email
3. **Auto-send capability** - Configure SMTP or email API
4. **Enhanced validation** - Add comprehensive quality checks

---

## Contact & Support

**Project:** RevMan TBS Price Change Automation
**Owner:** Mark (Revenue Management)
**Technical Contact:** Aaditya Singhal (aaditya.singhal@anheuser-busch.com)

**Documentation:**
- Implementation Plan: `revman/plan.md` (this document)
- Configuration: `revman/.env`
- Crew Definitions: `src/revman/crews/*/config/`

---

**Plan Version:** 2.0
**Date:** November 7, 2025
**Status:** Active - POC Phase Complete
