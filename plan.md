# RevMan TBS Price Change Email Automation - Implementation Plan

## Executive Summary

Automated Revenue Management system that processes TBS (The Beer Store) price change Excel reports and generates formatted email summaries using CrewAI's multi-crew Flow architecture. Replaces Mark's 30-45 minute manual workflow.

**Formula:** `=PROPER($D9)&" "&$H9&$L9&" "&$M9&"$"&ABS($K9)&" to $"&$J9` → Example: `Budweiser 30C -$5.50 to $45.99`

**Flow:** Excel input → Parse & categorize by brewer (LABATT, MOLSON, SLEEMAN) and change type (Begin/End LTO, Permanent Changes) → Generate formatted email → Save to output directory

---

## Business Requirements

### Problem Statement

Mark spends 30-45 minutes weekly processing TBS price change files. The process is formulaic and repeatable, making it ideal for automation. The goal is to eliminate manual work while maintaining the same output format stakeholders expect.

### Success Criteria

- ✅ Automatically process TBS Excel files when received via email
- ✅ Apply Mark's formula logic to generate formatted price change lines
- ✅ Categorize changes by brewer (LABATT, MOLSON, SLEEMAN, etc.)
- ✅ Organize by change type (Begin LTO, End LTO, Permanent Changes)
- ✅ Generate email with subject line, opening text, and highlights in exact template format
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

The AI agent must produce a draft email with:

#### 1. Subject Line & Opening Text
- **Consistent wording each week** for easy identification
- **Example:** "TBS Price Change Summary – Effective [Date]"
- **Date Source:** Effective date is extracted from the input Excel filename (e.g., "October 13th'25" → "October 13, 2025")
- Opening text should provide brief context about the price changes

#### 2. Highlights Section
- **Grouped by brewer hierarchy:**
  - LABATT (includes Budweiser, Bud Light, Stella Artois, Corona, Modelo, Becks, Hoegaarden, Michelob)
  - MOLSON (includes Coors, Molson Canadian, Miller, Heineken)
  - SLEEMAN (includes Sleeman products, Sapporo)
  - Other (includes Laker, Peroni, James Ready, Moosehead, Guinness, etc.)

- **Example format:**
  ```
  Budweiser 30C +$1 to $59.95
  ```

- **Pack size notation:**
  - C = 355mL can
  - TC = 473mL tall can
  - B = bottle

**Format:** Plain text email content (not HTML)

**Price Change Categorization Logic:**

1. **Calculate Percentage Column:** For each row, calculate `(new price / old price) * 100` to determine the new price as a percentage of the old price

2. **Filter by Type of Sale:** Categorization rules apply differently based on the "Type of Sale" field:

   **For Type of Sale = "TBS – Retail Price":**
   - **Permanent Change:** Price change where new price is between 96% and 104% of old price (96% ≤ percentage ≤ 104%)
   - **Begin LTO:** Price **decrease** where new price < 96% of old price (percentage < 96%)
   - **End LTO:** Price **increase** where new price > 104% of old price (percentage > 104%)
   - **End LTO & Permanent Change:** Same as End LTO, but price does not return to pre-LTO level (requires historical check)

   **For Type of Sale = "New SKU":**
   - Include in separate "NEW SKUs" section (no category label)

   **For Type of Sale = "TBS - Licensee":**
   - Include in separate "LICENSEE CHANGES" section

3. **No Filtering Rule:** **ALL changes for LABATT, MOLSON, SLEEMAN, and Other groups MUST be included in the email** - do not filter out any changes based on magnitude, significance, or any other criteria

**Reference Template:**
`data/templates/Output format.docx` contains actual examples of Mark's email format with real product data

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

**Task 2: extract_effective_date**
```yaml
Agent: excel_parser_agent
Input: {excel_file_path}
Output: Effective date in ISO and display formats
Key Actions:
  - Extract date from input filename
  - Parse pattern: "October 13th'25" → "October 13, 2025"
  - Return both ISO format (2025-10-13) and display format (October 13, 2025)
  - Fallback to current date if parsing fails
Tools Used:
  - DateExtractorTool
Purpose:
  - Determines when price changes take effect (from filename)
  - Used in email subject line and body
  - Distinguishes effective_date (from file) from trigger_date (when flow runs)
```

**Task 3: generate_formula_excel**
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

**Task 4: analyze_price_changes**
```yaml
Agent: data_analyst_agent
Input: Parsed data from Task 1
Output: Categorized changes grouped by brewer and type
Key Actions:
  - Calculate percentage column for each row: (new price / old price) * 100
  - Apply formula logic: PROPER(Product) + PackSize + +/-$Amount + to $NewPrice
  - Categorize based on "Type of Sale" field:

    FOR "Type of Sale" = "TBS – Retail Price":
      * Permanent Change: 96% ≤ percentage ≤ 104% (price change within ±4%)
      * Begin LTO: percentage < 96% (price DECREASE > 4%)
      * End LTO: percentage > 104% (price INCREASE > 4%)
      * End LTO & Perm Change: requires historical price check (percentage > 104% but not returning to pre-LTO level)

    FOR "Type of Sale" = "New SKU":
      * Include in "NEW SKUs" section (no category label)

    FOR "Type of Sale" = "TBS - Licensee":
      * Include in "LICENSEE CHANGES" section

  - Group retail price changes by brewer (LABATT, MOLSON, SLEEMAN, Other)
  - **CRITICAL: Include ALL changes - do not filter by magnitude or significance**
  - All changes for LABATT, MOLSON, SLEEMAN, and Other groups must appear in output

Format:
  {
    "LABATT": {
      "Begin LTO": ["Budweiser 30C -$5.50 to $45.99", ...],
      "End LTO": ["Bud Light 12C +$2 to $29.99", ...],
      "End LTO & Permanent Change": ["Stella Artois 24B +$3.50 to $52.99", ...],
      "Permanent Changes": ["Bud Light 28B -$0.50 to $43.49", ...]
    },
    "MOLSON": {...},
    "SLEEMAN": {...},
    "Other": {...},
    "LICENSEE CHANGES": [...],
    "NEW SKUs": [...]
  }
```

**Task 5: validate_data_quality**
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
- **Role:** Price Change Email Writer
- **Goal:** Generate complete email with subject line, opening text, and highlights
- **Key Skills:**
  - Generate consistent subject line: "TBS Price Change Summary – Effective [Date]" (date extracted from filename)
  - Write brief opening text with context
  - Format highlights by brewer hierarchy with proper categorization
  - Include pack size notation (C = 355mL can, TC = 473mL tall can, B = bottle)

#### Task

**Task: write_highlights_content**
```yaml
Agent: email_content_writer_agent
Input: {price_changes_categorized}, {effective_date}
Output: Complete email (subject line, opening text, and highlights)

Structure:
  1. Subject Line: "TBS Price Change Summary – Effective [Date]"
     - Use effective_date (extracted from input filename by Excel processor crew)
     - Consistent format each week

  2. Opening Text:
     - Brief paragraph providing context
     - Reference the effective date (from filename, not current date)

  3. Highlights Section:
     - Title: "Highlights (Price Before Tax and Deposit)"
     - Pack size notation note: C = 355mL can, TC = 473mL tall can, B = bottle
     - For each brewer (LABATT, MOLSON, SLEEMAN, Other) in order:
       * Brewer name as header
       * Begin LTO section (if applicable)
       * End LTO section (if applicable)
       * End LTO & Permanent Change section (if applicable)
       * Permanent Changes section (if applicable)
       * Blank line between brewers
     - After all brewers:
       * LICENSEE CHANGES section (if applicable)
       * NEW SKUs section (if applicable)

Format: Plain text, NOT HTML

Reference: data/templates/Output format.docx contains examples of Mark's email format
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

```
revman/
├── src/revman/
│   ├── main.py                          # Main Flow definition
│   ├── crews/
│   │   ├── excel_processor_crew/        # Crew 1: Parse & categorize
│   │   └── email_builder_crew/          # Crew 2: Format email
│   └── tools/
│       ├── excel_tools.py
│       └── email_tools.py
├── data/
│   ├── input/                           # TBS Excel files
│   ├── templates/                       # Output format.docx
│   └── output/                          # Generated .txt, _metadata.json, _validation.json
├── .env                                 # Environment config
└── pyproject.toml                       # Dependencies
```

**Path Constants:** Defined in `main.py` using `PROJECT_ROOT`, `DATA_DIR`, `INPUT_DIR`, `OUTPUT_DIR`, `TEMPLATE_DIR` with environment variable overrides

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
excel_file_path: str = r"C:\Users\...\data\input\"
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
  "subject": "TBS Price Change Summary – Effective October 13, 2025",
  "generated_at": "2025-11-09T14:23:45",
  "trigger_date": "2025-11-09T00:00:00",
  "effective_date": "2025-10-13T00:00:00",
  "input_file": "C:\\...\\data\\input\\TBS Price Change Summary Report - October 13th'25.xlsx",
  "validation_passed": true,
  "recipients": ["aaditya.singhal@anheuser-busch.com"]
}
```
**Note:** `trigger_date` is when the flow runs (e.g., Nov 9), while `effective_date` is extracted from the filename (e.g., Oct 13) and represents when the price changes take effect.

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
Subject: TBS Price Change Summary – Effective November 7, 2025

---

Dear Team,

Please find below the TBS price changes effective November 7, 2025. This summary includes all price adjustments across our portfolio, organized by brewer and change type.

Highlights (Price Before Tax and Deposit)

Note: Pack size notation - C = 355mL can, TC = 473mL tall can, B = bottle

LABATT
Begin LTO
Budweiser 30C -$5.50 to $45.99
MSO 24C -$4 to $44.99
Bud Light Lime 12C -$3 to $27.49

End LTO
Bud Light Lemon Lime 12C +$2 to $29.99
Michelob Ultra 24B +$2.50 to $58.99

End LTO & Permanent Change
Stella Artois 24B +$3.50 to $52.99

Permanent Changes
Bud Light 28B -$0.50 to $43.49
Corona Extra 12C +$0.25 to $24.99

MOLSON
Begin LTO
Coors Light 30C -$4 to $45.49
Molson Canadian 24C -$3.50 to $42.99

Permanent Changes
Miller Lite 24C +$0.75 to $45.25

SLEEMAN
Begin LTO
Sleeman Honey Brown 24C -$2.00 to $42.99

Other
Permanent Changes
Laker Lager 24C +$0.50 to $35.99

LICENSEE CHANGES
Craft Beer Brand 12C +$1.00 to $28.99

NEW SKUs
New Product Launch 24C $49.99

---

Best regards,
Revenue Management Team
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

## Key Design Decisions

1. **AI Agents replicate Excel formula logic** - More flexible than direct formula execution, easier to maintain and extend
2. **Plain text email output** - Matches current workflow, simpler validation
3. **Sequential crew execution** - Clear dependencies, easier debugging
4. **Minimal validation for POC** - Focus on core functionality, enhance later
5. **File-based output** - Safe for POC, human review before sending, provides audit trail

---

## Success Metrics

**Targets:** < 2 min execution (vs 30-45 min manual), 100% accuracy, 100% format compliance, zero manual intervention, complete data coverage

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
