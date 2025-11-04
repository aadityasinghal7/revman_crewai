# RevMan Price Change Email Flow - Implementation Plan

## Executive Summary
Transform the existing PoemFlow template into a production-ready Revenue Management system that processes Excel price change reports and generates formatted HTML email templates using a multi-crew CrewAI Flow architecture.

---

## IMPORTANT UPDATE - Actual Template Discovered (Nov 4, 2025)

### What Changed
After successfully analyzing `Output format.docx`, the **actual email template structure is MUCH SIMPLER** than initially assumed. This plan has been updated to reflect the real requirements.

### Key Discoveries
1. **NO complex HTML tables** - Output is simple structured text organized by sections
2. **Highlights format** - Focus on curated key changes, not exhaustive data dumps
3. **Organized by Brewer** - LABATT, MOLSON, SLEEMAN sections
4. **Categorized by change type** - Begin LTO, End LTO, Permanent Changes
5. **Business context included** - Strategic rationale provided (e.g., "competitive response", "SCO mitigation")

### Example Format (from actual template):
```
Highlights (Price Before Tax and Deposit)

LABATT
Begin LTO
Budweiser 30C -$5.50 to $45.99 (increased depth as a competitive response)
MSO 24C -$4 to $44.99
...

End LTO
Bud Light Lemon Lime 12C +$2 to $29.99 (end SCO mitigation)
...

MOLSON
Begin LTO
...
```

### What This Means
- **Simpler implementation** - Less complex than initially planned
- **Focus on intelligent categorization** - Not just data parsing, but understanding LTO strategy
- **Business context identification** - Agents need to infer WHY changes are happening
- **Curated highlights** - Not all products included, only strategic/significant ones

### Sections Updated
- ✅ Section 1: Output Requirements - Now shows actual template format
- ✅ Section 2: Flow State Model - Simplified structure with `price_changes_categorized`
- ✅ Section 3.1: Excel Processor Crew - Analysis task updated for categorization
- ✅ Section 3.2: Email Builder Crew - Simplified from 3 agents to 2, tasks match template
- ✅ Tools - Removed complex table generator, added text-to-HTML formatter

---

## 1. Data Analysis Summary

### Excel Input Structure
**File**: `TBS Price Change Summary Report - October 13th'25.xlsx`
- **Format**: Single sheet with header rows (data starts at row 7)
- **Total Records**: ~182 product records
- **Key Columns**:
  1. SAP Art. No. (Article Number)
  2. Type of Sale (e.g., "TBS - Retail Price")
  3. Brewer
  4. Product Name
  5. Pack Type (Bottles/Cans)
  6. Pack Volume ml
  7. Package Full Name
  8. Pack Size
  9. Old Price
  10. New Price
  11. Increase/(Decrease)
  12. Additional classification columns
  13. Summary text

### Output Requirements (Based on Actual Template Analysis)
**Source**: `Output format.docx` - Analyzed November 4, 2025

**Format**: Simple structured text email (NOT complex tables)

**Structure**:
1. **Title**: "Highlights (Price Before Tax and Deposit)"
2. **Organized by Brewer**: LABATT, MOLSON, SLEEMAN (and others as applicable)
3. **Within each brewer, categorized by**:
   - **Begin LTO** - Price decreases indicating start of Limited Time Offers
   - **End LTO** - Price increases as LTOs conclude
   - **End LTO & Perm Change** - Combined changes
   - **Permanent Changes** - Ongoing adjustments

**Line Item Format**:
```
Product Name PackSize +/-$Amount to $FinalPrice (optional business context)
```

**Examples from actual template**:
- "Budweiser 30C -$5.50 to $45.99 (increased depth as a competitive response)"
- "Bud Light Lemon Lime 12C +$2 to $29.99 (end SCO mitigation)"
- "Miller High Life 12TC +$2.50 to $23.49 (Labatt Value at $23.49)"
- "Corona 24B +$3 to $50.69"

**Key Characteristics**:
- Focus on **highlights only** - not comprehensive data dump
- **Business context** provided where strategic (competitive responses, value positioning)
- **Concise bullet-point style** - easy to scan
- **Simple HTML formatting** - clean sections, not complex tables

---

## 2. Architecture Overview

### Flow Structure (Replacing PoemFlow)
```
FlowState (Pydantic Model)
    ↓
[@start] trigger_flow()  ← Triggered by email from aaditya.singhal@anheuser-busch.com
                           with subject "test" and Excel attachment
    ↓
[@listen] excel_processing_crew()  ← Crew 1: Excel Parser
    ↓
[@listen] email_generation_crew()  ← Crew 2: Email Builder
    ↓
[@listen] validation_agent()       ← Light Agent: Validator
    ↓
[@listen] save_email_output()      ← Save to local directory
```

### Flow State Model
```python
class RevManFlowState(BaseModel):
    # Input
    excel_file_path: str
    trigger_date: datetime
    email_recipients: Optional[List[str]] = None

    # Excel Processing Output (Crew 1)
    raw_data: Dict[str, Any]  # Raw parsed Excel data
    price_changes_categorized: Dict[str, Any]  # Organized by brewer → change type → products
    # Structure: {
    #   "LABATT": {
    #     "Begin LTO": ["Budweiser 30C -$5.50 to $45.99 (increased depth...)"],
    #     "End LTO": [...],
    #     "Permanent Changes": [...]
    #   },
    #   "MOLSON": {...},
    #   ...
    # }
    parsing_errors: List[str]

    # Email Generation Output (Crew 2)
    highlights_text: str  # Plain text version of highlights
    email_html: str  # Final HTML email
    email_subject: str  # Email subject line
    email_metadata: Dict[str, Any]  # Additional metadata (date, record count, etc.)

    # Validation Output
    validation_passed: bool
    validation_report: Dict[str, Any]

    # Final Output
    output_file_path: Optional[str] = None
```

---

## 3. Detailed Component Design

### 3.1 Crew 1: Excel Processing Crew

**Purpose**: Parse Excel file, extract data, perform calculations, and structure for email generation

**Location**: `src/revman/crews/excel_processor_crew/`

#### Agents (agents.yaml)
```yaml
excel_parser_agent:
  role: Excel Data Parser Specialist
  goal: Parse the TBS Price Change Summary Excel file and extract clean, structured data with {record_count} records
  backstory: Expert in handling complex Excel files with headers, formatting, and data validation.
    Skilled in identifying data quality issues and cleaning datasets for downstream processing.

data_analyst_agent:
  role: Price Change Categorization Specialist
  goal: Categorize price changes by brewer and change type (LTO vs Permanent) with business context
  backstory: ABI pricing strategy expert with deep understanding of Limited Time Offers (LTO),
    competitive responses, and SCO mitigation tactics. Skilled at identifying strategic pricing moves,
    categorizing changes by business purpose, and providing clear rationale for price adjustments.

data_validator_agent:
  role: Data Quality Validator
  goal: Ensure data integrity, validate calculations, and flag any anomalies or errors
  backstory: Quality assurance specialist with expertise in data validation,
    error detection, and ensuring data meets business rules and constraints.
```

#### Tasks (tasks.yaml)
```yaml
parse_excel_file:
  description: |
    Parse the Excel file at {excel_file_path} and extract all price change records.
    - Skip header rows (first 6 rows)
    - Extract all columns including SAP Art. No., Brewer, Product Name, Pack details, Old/New Prices
    - Handle data type conversions (numbers, text, dates)
    - Clean any formatting issues or special characters
    - Return structured JSON with all records
  expected_output: |
    Structured JSON containing:
    - List of all product records with complete column data
    - Column metadata and data types
    - Row count and data quality flags
  agent: excel_parser_agent

analyze_price_changes:
  description: |
    Analyze and categorize price change data for highlights email based on the actual template structure:

    PRIMARY CATEGORIZATION:
    1. Group all products by Brewer (e.g., LABATT, MOLSON, SLEEMAN)
    2. Within each brewer, categorize changes by type:
       - "Begin LTO" - Price decreases indicating start of Limited Time Offers
       - "End LTO" - Price increases indicating end of Limited Time Offers
       - "End LTO & Perm Change" - Combined LTO ending with permanent adjustment
       - "Permanent Changes" - Ongoing price adjustments

    FOR EACH PRODUCT:
    - Calculate price change amount (+ or -)
    - Determine final price
    - Identify business context (competitive response, SCO mitigation, value positioning, etc.)
    - Format as: "Product Name PackSize +/-$X.XX to $YY.YY (optional context)"

    INTELLIGENT FILTERING:
    - Focus on highlights only (significant changes, strategic moves)
    - Not all products need to be included - curate based on business importance
    - Prioritize larger changes and strategic pricing moves
  expected_output: |
    Structured categorization with:
    - Products grouped by Brewer (LABATT, MOLSON, SLEEMAN, etc.)
    - Within each brewer, sub-grouped by change type (Begin LTO, End LTO, etc.)
    - Each product formatted as: "Product PackSize +/-$Amount to $FinalPrice (context)"
    - Business context identified (competitive response, mitigation strategy, etc.)
    - Only notable/significant changes included (highlights, not exhaustive list)
    - Ready for direct insertion into email template
  agent: data_analyst_agent
  context:
    - parse_excel_file

validate_data_quality:
  description: |
    Validate data quality and integrity:
    - Check for missing required fields
    - Verify price calculations (Old Price - New Price = Change)
    - Identify outliers or anomalies
    - Flag any data quality issues
    - Ensure all records are complete and accurate
  expected_output: |
    Validation report with:
    - Pass/fail status for each validation check
    - List of any errors or warnings
    - Data quality score
    - Recommendations for data corrections
  agent: data_validator_agent
  context:
    - parse_excel_file
    - analyze_price_changes
```

#### Custom Tools
**File**: `src/revman/tools/excel_tools.py`

```python
# ExcelReaderTool
- Parse Excel files with complex headers
- Handle skiprows, data types, and formatting
- Extract metadata (sheet names, dimensions)
- Support for .xlsx and .xls formats

# DataCleanerTool
- Remove special characters and formatting
- Standardize data types
- Handle missing values
- Normalize text fields

# PriceCalculatorTool
- Validate price calculations
- Calculate percentage changes
- Identify trends and patterns
- Generate statistics
```

---

### 3.2 Crew 2: Email Generation Crew

**Purpose**: Transform structured data into professional HTML email template

**Location**: `src/revman/crews/email_builder_crew/`

#### Agents (agents.yaml)
```yaml
email_content_writer_agent:
  role: Price Change Highlights Writer
  goal: Transform categorized price change data into clear, concise highlights email following ABI format
  backstory: Expert in ABI pricing communications with deep understanding of business context
    (LTO strategy, competitive responses, SCO mitigation). Skilled at presenting price changes
    in the standard "Highlights (Price Before Tax and Deposit)" format with appropriate business rationale.

html_email_formatter_agent:
  role: HTML Email Formatter
  goal: Format the highlights content into clean, professional HTML email with ABI styling
  backstory: Email formatting specialist who converts structured text into well-formatted HTML emails.
    Experienced with simple, readable email layouts that work across all email clients.
    Focuses on clarity and professional presentation over complex designs.
```

#### Tasks (tasks.yaml)
```yaml
write_highlights_content:
  description: |
    Transform the categorized price change data into the standard "Highlights" email format.

    REQUIRED STRUCTURE:
    1. Title: "Highlights (Price Before Tax and Deposit)"
    2. For each Brewer (LABATT, MOLSON, SLEEMAN, etc.):
       - Brewer name as header
       - "Begin LTO" section with price decreases
       - "End LTO" section with price increases
       - "End LTO & Perm Change" section (if applicable)
       - "Permanent Changes" section (if applicable)
       - Empty line between sections

    FORMAT EACH LINE:
    Product PackSize +/-$Amount to $FinalPrice (optional context)
    Examples:
    - "Budweiser 30C -$5.50 to $45.99 (increased depth as a competitive response)"
    - "Bud Light Lemon Lime 12C +$2 to $29.99 (end SCO mitigation)"
    - "Corona 24B +$3 to $50.69"

    BUSINESS CONTEXT:
    Add context where appropriate explaining WHY the change is happening:
    - "increased depth as a competitive response"
    - "end SCO mitigation"
    - Value positioning references (e.g., "Labatt Value at $23.49")
    - Competitive benchmarking (e.g., "Ultra at $58.99")

    Use the categorized data from: {price_changes_categorized}
  expected_output: |
    Structured text content ready for email:
    - Title line
    - Brewer sections (LABATT, MOLSON, SLEEMAN, etc.)
    - Each section contains Begin LTO, End LTO, and Permanent Changes subsections
    - Each product line properly formatted with price change and context
    - Professional business tone with strategic rationale
    - Plain text format (not HTML yet)
  agent: email_content_writer_agent

format_as_html_email:
  description: |
    Convert the highlights text content into a clean, professional HTML email.

    REQUIREMENTS:
    - Simple, readable HTML structure (not complex tables)
    - Use clean typography and spacing
    - Style brewer names as bold headers
    - Style section headers (Begin LTO, End LTO, etc.) as subheaders
    - Indent product lines for readability
    - Use appropriate colors for price increases (+) and decreases (-)
    - Add professional email header and footer
    - Ensure mobile-responsive design
    - Compatible with all major email clients

    INPUT: Plain text highlights from previous task
  expected_output: |
    Complete HTML email with:
    - Valid HTML structure with inline CSS
    - Professional header with title
    - Formatted brewer sections with proper hierarchy
    - Color-coded price changes (red for increases, green for decreases)
    - Clean spacing and readability
    - Professional footer
    - Subject line: "TBS Price Change Summary - [Date]"
  agent: html_email_formatter_agent
  context:
    - write_highlights_content
```

#### Custom Tools
**File**: `src/revman/tools/email_tools.py`

```python
# TextToHTMLFormatterTool
- Convert structured plain text to HTML
- Apply inline CSS styling for email compatibility
- Handle ABI branding (colors, fonts, spacing)
- Format sections with proper hierarchy (headers, subheaders, lists)
- Color-code price increases (red) and decreases (green)

# EmailValidatorTool
- Validate HTML structure and syntax
- Check email client compatibility
- Verify all content is properly formatted
- Test responsive design
- Validate subject line and metadata
```

---

### 3.3 Light Validation Agent

**Purpose**: Final validation before email output

**Location**: `src/revman/main.py` (inline agent, not a full crew)

#### Agent Configuration
```python
validation_agent = Agent(
    role="Email Quality Validator",
    goal="Perform final validation on the generated email to ensure it meets all quality standards",
    backstory="""Quality assurance specialist who performs final checks on email templates
    before delivery. Ensures data completeness, formatting correctness, and business rule compliance.""",
    tools=[EmailValidatorTool(), HTMLLinterTool(), DataCompletenessCheckerTool()],
    verbose=True
)
```

#### Validation Checks
1. **Data Completeness**
   - All required fields populated
   - No missing or null values in critical sections
   - Record count matches input data

2. **Business Rules**
   - Price calculations are accurate
   - Price change math is correct (Old - New = Change)
   - Currency formatting is consistent
   - Date formatting is correct

3. **Template Formatting**
   - Valid HTML structure
   - All placeholders replaced
   - Responsive design elements present
   - Email client compatibility
   - Links and images properly formatted
   - Subject line length appropriate

4. **Output Quality**
   - Professional appearance
   - Brand guidelines followed
   - Clear and readable formatting
   - Proper spacing and alignment

---

## 4. File Structure Changes

### New Directory Structure

**Data Organization**: All data files are centralized in `revman/data/` with organized subfolders:
- `data/input/` - Incoming Excel files (price change reports)
- `data/output/` - Generated HTML emails and reports
- `data/templates/` - Reference templates and documentation

✅ **Status**: Data folder structure created and existing files organized (Nov 4, 2025)

```
revman/                                  # Project root (standard Python project structure)
├── src/revman/
│   ├── main.py                          # [MODIFY] Main Flow definition
│   ├── crews/
│   │   ├── poem_crew/                   # [REMOVE or ARCHIVE]
│   │   ├── excel_processor_crew/        # [NEW] Crew 1
│   │   │   ├── __init__.py
│   │   │   ├── excel_processor_crew.py
│   │   │   └── config/
│   │   │       ├── agents.yaml
│   │   │       └── tasks.yaml
│   │   └── email_builder_crew/          # [NEW] Crew 2
│   │       ├── __init__.py
│   │       ├── email_builder_crew.py
│   │       └── config/
│   │           ├── agents.yaml
│   │           └── tasks.yaml
│   └── tools/
│       ├── __init__.py
│       ├── custom_tool.py               # [REMOVE or ARCHIVE]
│       ├── excel_tools.py               # [NEW] Excel processing tools
│       └── email_tools.py               # [NEW] Email generation tools
├── data/                                # ✅ CREATED - All data in one place
│   ├── input/                           # ✅ CREATED - Input Excel files
│   │   └── TBS Price Change Summary Report - October 13th'25.xlsx  # ✅ MOVED
│   ├── templates/                       # ✅ CREATED - Email templates
│   │   └── Output format.docx           # ✅ MOVED
│   └── output/                          # ✅ CREATED - Generated emails
│       └── [generated emails will be saved here]
├── tests/                               # [NEW] Test suite
│   ├── test_excel_processor.py
│   ├── test_email_builder.py
│   ├── test_flow.py
│   └── fixtures/
│       └── sample_data.xlsx
└── .env                                 # [UPDATE] Add new config vars
```

**Why this structure?**
- ✅ All data centralized at `revman/data/` (not scattered)
- ✅ Clear separation: input vs output vs templates
- ✅ Standard Python project layout (data at root level alongside src/)
- ✅ Easy to manage, backup, and .gitignore specific folders
- ✅ Follows common conventions for data science/ML projects

---

## 5. Implementation Steps

### Phase 1: Project Setup & Cleanup
1. **Archive/Remove Template Code**
   - Move `poem_crew/` to `archive/` or delete
   - Remove `custom_tool.py` template
   - Clean up main.py

2. **Update Dependencies**
   - Add to `pyproject.toml`:
     ```toml
     dependencies = [
         "crewai[tools]==1.2.0",
         "pandas>=2.0.0",
         "openpyxl>=3.1.0",
         "python-docx>=1.0.0",
         "jinja2>=3.1.0",
         "lxml>=4.9.0",
         "premailer>=3.10.0"  # For inline CSS in emails
     ]
     ```

3. **Set Up Directory Structure**
   - Create new crew directories
   - Create tool directories
   - Set up data/input, data/templates, data/output folders

### Phase 2: Build Custom Tools
**Priority: High** (Foundation for crews)

1. **Excel Tools** (`tools/excel_tools.py`)
   - ExcelReaderTool
   - DataCleanerTool
   - PriceCalculatorTool

2. **Email Tools** (`tools/email_tools.py`)
   - HTMLTemplateBuilderTool
   - HTMLTableGeneratorTool
   - EmailValidatorTool

### Phase 3: Implement Crew 1 (Excel Processor)
1. Create crew structure in `crews/excel_processor_crew/`
2. Define agents in `config/agents.yaml`
3. Define tasks in `config/tasks.yaml`
4. Implement crew class in `excel_processor_crew.py`
5. Test with sample Excel file

### Phase 4: Implement Crew 2 (Email Builder)
1. Create crew structure in `crews/email_builder_crew/`
2. Define agents in `config/agents.yaml`
3. Define tasks in `config/tasks.yaml`
4. Implement crew class in `email_builder_crew.py`
5. Test with mock data from Crew 1

### Phase 5: Build Main Flow
1. **Define Flow State Model** (RevManFlowState)

2. **Implement Flow Methods**:
   - `@start() trigger_flow()` - Initialize flow from trigger
     * **For POC**: Accept file path as parameter (manual trigger)
     * **For Phase 8**: Extract Excel from email (automatic trigger from aaditya.singhal@anheuser-busch.com with subject "test")
     * Initialize state with excel_file_path, trigger_date
     * Validate input file exists and is readable

   - `@listen() excel_processing_step()` - Run Crew 1
     * Execute Excel Processor Crew
     * Populate state with: raw_data, price_changes, summary_stats
     * Handle parsing errors gracefully

   - `@listen() email_generation_step()` - Run Crew 2
     * Execute Email Builder Crew
     * Populate state with: email_html, email_subject, email_metadata
     * Generate HTML email from processed data

   - `@listen() validation_step()` - Run validation agent
     * Validate data completeness, business rules, formatting
     * Populate state with: validation_passed, validation_report
     * Fail flow if critical validations don't pass

   - `@listen() save_email_output()` - Save to disk
     * Save HTML email to data/output/
     * Save metadata and validation report
     * Log completion status

3. **Add Error Handling**:
   - Try/catch blocks for each step
   - State error tracking
   - Graceful degradation
   - Logging and monitoring

### Phase 6: Implement Validation Agent
1. Create light validation agent in main.py
2. Implement validation tools
3. Define validation checks (data, business rules, formatting)
4. Create validation report structure

### Phase 7: Testing & Refinement
1. **Unit Tests**
   - Test each tool independently
   - Test agents with mock data
   - Test tasks individually

2. **Integration Tests**
   - Test Crew 1 end-to-end
   - Test Crew 2 end-to-end
   - Test full flow with sample data

3. **Validation Testing**
   - Test validation agent with good data
   - Test validation agent with bad data
   - Verify error detection

4. **Output Quality Testing**
   - Review generated HTML emails
   - Test in multiple email clients
   - Verify responsive design
   - Validate data accuracy

### Phase 8: Email Trigger Integration (Future)
**Note**: Defer to post-POC phase

**Trigger Specification**:
- **Sender Email**: aaditya.singhal@anheuser-busch.com
- **Subject Line**: "test"
- **Attachment**: Excel file (TBS Price Change Summary Report)
- **Action**: Automatically trigger the RevMan flow when email is received

**Implementation Steps**:
1. **Set up email listener/webhook**
   - Monitor mailbox for incoming emails
   - Filter by sender: aaditya.singhal@anheuser-busch.com
   - Filter by subject: "test"
   - Options: IMAP polling, Microsoft Graph API, or email service webhook

2. **Implement email attachment extraction**
   - Extract Excel attachment from email
   - Save to `data/input/` directory with timestamp
   - Validate file type (.xlsx)
   - Handle multiple attachments (if applicable)

3. **Add trigger payload handling**
   - Extract metadata from email (sender, date, subject)
   - Construct trigger payload with file path
   - Pass to Flow start node

4. **Configure email sending (SMTP or API)**
   - Send generated email template to recipients
   - Use reply-to or configured recipient list
   - Include original sender in CC/BCC if needed

**Recommended Approach**: Microsoft Graph API (for ABI Office 365 integration)
- More reliable than IMAP
- Better security with OAuth 2.0
- Access to full email metadata
- Webhook support for real-time triggers

---

## 6. Configuration Updates

### Environment Variables (.env)
```bash
# Existing
OPENAI_API_KEY=your_openai_key_here

# Data directory configuration (relative to project root: revman/)
REVMAN_INPUT_DIR=./data/input      # ✅ All Excel files stored here
REVMAN_OUTPUT_DIR=./data/output    # ✅ Generated emails saved here
REVMAN_TEMPLATE_DIR=./data/templates  # ✅ Reference templates stored here

# Email Trigger Configuration (for Phase 8)
# EMAIL_TRIGGER_ENABLED=false
# EMAIL_TRIGGER_SENDER=aaditya.singhal@anheuser-busch.com
# EMAIL_TRIGGER_SUBJECT=test
# EMAIL_TRIGGER_MAILBOX=revman@abi.com
# EMAIL_CHECK_INTERVAL_SECONDS=60

# Email Output Configuration (for future use)
# SMTP_HOST=smtp.abi.com
# SMTP_PORT=587
# SMTP_USER=revman@abi.com
# SMTP_PASSWORD=<secure_password>
# EMAIL_FROM=revman@abi.com
# EMAIL_TO_DEFAULT=stakeholders@abi.com

# Microsoft Graph API (Recommended for Office 365)
# MS_GRAPH_TENANT_ID=<tenant_id>
# MS_GRAPH_CLIENT_ID=<client_id>
# MS_GRAPH_CLIENT_SECRET=<client_secret>
# MS_GRAPH_MAILBOX=revman@abi.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/revman.log

# Flow configuration
MAX_RETRIES=3
TIMEOUT_SECONDS=300
```

### Update pyproject.toml
```toml
[tool.crewai]
project_type = "flow"

[project.scripts]
revman = "revman.main:kickoff"
revman-plot = "revman.main:plot"
revman-trigger = "revman.main:run_with_trigger"
```

---

## 7. Sample Flow Execution

### POC Mode (Manual Trigger - Phases 1-7)

**Trigger Method**: Manual execution with file path parameter

**Command**:
```bash
crewai run_with_trigger '{"excel_file_path": "./data/input/TBS Price Change Summary Report - October 13th'\''25.xlsx", "trigger_date": "2025-10-06T00:00:00Z"}'
```

**Trigger Payload**:
```json
{
  "excel_file_path": "./data/input/TBS Price Change Summary Report - October 13th'25.xlsx",
  "trigger_date": "2025-10-06T00:00:00Z",
  "email_recipients": ["stakeholder1@abi.com", "stakeholder2@abi.com"]
}
```

### Phase 8 Mode (Email Trigger - Future)

**Trigger Method**: Automatic execution when email received

**Email Trigger Criteria**:
- **From**: aaditya.singhal@anheuser-busch.com
- **Subject**: "test"
- **Attachment**: Excel file (*.xlsx)

**Flow Behavior**:
1. Email monitoring service detects incoming email matching criteria
2. Extract Excel attachment and save to `./data/input/`
3. Construct trigger payload automatically with extracted file path
4. Execute flow automatically
5. (Optional) Send generated email to configured recipients

### Execution Steps (Both Modes)
1. **Start** → Parse trigger, initialize state, validate file exists
2. **Crew 1** → Parse Excel, analyze data, validate
3. **Crew 2** → Generate email content, build HTML, create tables
4. **Validation** → Check completeness, business rules, formatting
5. **Save** → Write HTML email to `./data/output/price_change_email_2025-10-06.html`

### Output Files
```
data/output/
├── price_change_email_2025-10-06.html           # Final HTML email
├── price_change_email_2025-10-06_metadata.json  # Metadata & stats
└── price_change_email_2025-10-06_report.json    # Validation report
```

---

## 8. Key Design Decisions

### 1. Flow State vs File I/O
**Decision**: Use Flow State (Pydantic model) to pass data between crews
**Rationale**:
- More efficient (no disk I/O overhead)
- Type-safe with Pydantic validation
- Easier to track state changes
- Better for debugging and logging

### 2. Light Validation Agent (Not a Full Crew)
**Decision**: Use a single agent for validation instead of a full crew
**Rationale**:
- Validation tasks are straightforward and don't require complex collaboration
- Reduces overhead and execution time
- Simpler to maintain
- Appropriate for the scope of validation needed

### 3. HTML Email Format
**Decision**: Generate HTML emails (not plain text)
**Rationale**:
- Better presentation of tabular data
- Professional appearance with branding
- Support for styling and visual hierarchy
- Industry standard for business communications

### 4. Sequential Crew Execution
**Decision**: Crews execute sequentially (not parallel)
**Rationale**:
- Clear dependency chain (Crew 2 needs Crew 1 output)
- Easier to debug and monitor
- Predictable execution flow
- Matches current Process.sequential pattern

---

## 9. Testing Strategy

### Unit Testing
- **Tools**: Test each custom tool with sample inputs
- **Agents**: Mock agent responses for predictability
- **Tasks**: Test task execution with fixtures

### Integration Testing
- **Crew 1**: Test with real Excel file from data/input
- **Crew 2**: Test with mock Crew 1 output
- **Full Flow**: End-to-end test with complete data pipeline

### Validation Testing
- **Happy Path**: Valid Excel → Valid Email
- **Error Cases**:
  - Malformed Excel file
  - Missing data
  - Invalid calculations
  - Template generation failures

### Output Quality Testing
- Manual review of generated emails
- Email client rendering tests (Gmail, Outlook, Apple Mail)
- Responsive design verification
- Data accuracy spot checks

---

## 10. Future Enhancements (Post-POC)

### Email Trigger Integration
1. Set up email inbox monitoring
2. Extract Excel attachments automatically
3. Trigger flow on email receipt
4. Send generated email automatically

### Advanced Features
1. **Multi-file Support**: Process multiple Excel files in one run
2. **Comparison Mode**: Compare current vs previous price changes
3. **Alert System**: Flag unusual price changes or anomalies
4. **Dashboard**: Web UI to monitor flow executions
5. **Template Customization**: Multiple email templates for different audiences
6. **Scheduling**: Automated periodic runs
7. **Approval Workflow**: Review/approve before sending
8. **Analytics**: Track price change trends over time

### Performance Optimizations
1. Parallel task execution where possible
2. Caching of template components
3. Batch processing for large datasets
4. Async operations for I/O

---

## 11. Risk Mitigation

### Technical Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Excel format changes | High | Add robust parsing with fallbacks; version detection |
| Data quality issues | Medium | Comprehensive validation; error reporting |
| HTML rendering issues | Medium | Test across email clients; use email-safe HTML |
| Long execution times | Low | Add timeouts; monitor performance; optimize tools |
| API rate limits (OpenAI) | Medium | Implement retry logic; use efficient prompts |

### Operational Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing input files | High | Validate file existence before processing |
| Incorrect data transformations | High | Comprehensive testing; validation checks |
| Email delivery failures | Medium | Defer to Phase 8; add retry mechanisms |

---

## 12. Success Criteria

### MVP (Minimum Viable Product)
- [ ] Successfully parse TBS Excel file
- [ ] Extract all price change records
- [ ] Calculate summary statistics
- [ ] Generate professional HTML email
- [ ] Include properly formatted price change table
- [ ] Pass all validation checks
- [ ] Save email to local directory
- [ ] Complete execution in < 5 minutes

### Quality Metrics
- [ ] 100% data accuracy (no calculation errors)
- [ ] Email renders correctly in 3+ major clients
- [ ] Validation catches all major data issues
- [ ] Code coverage > 80%
- [ ] Zero critical bugs in testing

---

## 13. Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| 1. Project Setup | 1-2 hours | None |
| 2. Build Tools | 4-6 hours | Phase 1 |
| 3. Crew 1 Implementation | 3-4 hours | Phase 2 |
| 4. Crew 2 Implementation | 3-4 hours | Phase 2 |
| 5. Main Flow | 2-3 hours | Phases 3 & 4 |
| 6. Validation Agent | 2-3 hours | Phase 5 |
| 7. Testing & Refinement | 4-6 hours | Phases 1-6 |
| 8. Email Trigger (Future) | TBD | Post-POC |

**Total POC Estimate**: 19-28 hours (2.5 - 3.5 work days)

---

## 14. Open Questions & Clarifications Needed

### 1. Email Template Design
**Question**: Do you have specific ABI branding guidelines, logos, or color schemes to use?
**Action**: Need brand assets and style guide

### 2. Word Document Template
**Question**: The "Output format.docx" file couldn't be read (permission error). Can you share its contents or describe the expected email layout?
**Action**: Need to review Word doc or get description of email structure

### 3. Email Recipients
**Question**: Who should receive these emails? Should recipients be configurable?
**Action**: Define recipient list and configuration approach

### 4. Data Refresh Frequency
**Question**: How often will this flow run? Daily? Weekly? Ad-hoc?
**Action**: Understand scheduling requirements

### 5. Historical Data
**Question**: Should we compare current prices to historical data or just show current changes?
**Action**: Clarify if historical tracking is needed

### 6. Error Notifications
**Question**: If the flow fails, who should be notified and how?
**Action**: Define error notification strategy

### 7. Approval Process
**Question**: Should the email be reviewed/approved before sending, or is automated sending acceptable?
**Action**: Clarify workflow and approval requirements

---

## 15. Next Steps

### Immediate Actions
1. **Review this plan** with stakeholders
2. **Answer open questions** (Section 14)
3. **Obtain Word document template** (or provide description)
4. **Provide ABI branding assets** (logos, colors, fonts)
5. **Approve architecture and approach**

### Once Approved
1. Begin Phase 1 (Project Setup)
2. Implement custom tools (Phase 2)
3. Build Crew 1 (Phase 3)
4. Iterative development following phases 4-7

---

## 16. Additional Notes

### Why This Approach?
- **Modular**: Each crew and tool has a single responsibility
- **Testable**: Clear interfaces make testing straightforward
- **Maintainable**: Configuration-driven design eases updates
- **Scalable**: Can add more crews or enhance existing ones
- **Follows Best Practices**: Aligns with CrewAI Flow patterns and Python standards

### Alternative Approaches Considered
1. **Single Crew**: Simpler but less modular; harder to test and maintain
2. **File-based Communication**: More debuggable but slower and less type-safe
3. **Parallel Crew Execution**: Not applicable due to dependencies

---

## Contact & Support
For questions or clarifications about this plan, please reach out to the development team.

**Plan Version**: 1.0
**Date**: November 4, 2025
**Status**: Draft - Awaiting Approval
