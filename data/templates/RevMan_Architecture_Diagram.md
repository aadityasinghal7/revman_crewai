# RevMan POC - Architecture & Flow Diagram

## System Overview

The **RevMan POC** is a CrewAI Flow-based automation system that processes TBS (The Beer Store) price change reports and generates formatted email summaries for the Revenue Management team at Anheuser-Busch InBev. The system orchestrates three specialized crews that work sequentially to extract, analyze, and present pricing data.

**Key Capabilities:**
- Automated Excel parsing with formula generation
- Historical price trend analysis and forecasting
- Statistical anomaly detection for significant price changes
- Professional email generation with brewer-grouped highlights

---

## Complete System Architecture Tree

```
RevManFlow (main.py)
│
├─── TRIGGER
│    └─── Inputs: excel_file_path, email_recipients
│    └─── Auto-generated: trigger_date, effective_date
│
├─── CREW 1: Excel Processor Crew
│    │
│    ├─── AGENT: excel_parser_agent
│    │    ├─── Role: Excel Data Parser Specialist
│    │    ├─── Model: claude-sonnet-4-5
│    │    └─── Tools:
│    │         ├─── ExcelReaderTool (reads Excel, skips 7 header rows)
│    │         ├─── DataCleanerTool (handles nulls, normalizes text)
│    │         ├─── FormulaExcelGeneratorTool (adds price formulas)
│    │         └─── DateExtractorTool (extracts date from filename)
│    │
│    ├─── AGENT: data_analyst_agent
│    │    ├─── Role: Price Change Data Formatter
│    │    ├─── Model: claude-sonnet-4-5
│    │    └─── Tools:
│    │         ├─── PriceCalculatorTool (calculates price changes)
│    │         └─── PriceCategorizationTool (categorizes into 5 groups)
│    │
│    └─── TASKS (Sequential):
│         ├─── Task 1: parse_excel_file
│         │    ├─── Agent: excel_parser_agent
│         │    ├─── Tools: ExcelReaderTool → DataCleanerTool
│         │    └─── Output: Structured data with all product records
│         │
│         ├─── Task 2: extract_effective_date
│         │    ├─── Agent: excel_parser_agent
│         │    ├─── Tools: DateExtractorTool
│         │    └─── Output: effective_date_iso, effective_date_display
│         │
│         ├─── Task 3: generate_formula_excel
│         │    ├─── Agent: excel_parser_agent
│         │    ├─── Context: parse_excel_file
│         │    ├─── Tools: FormulaExcelGeneratorTool
│         │    └─── Output: Formula Excel file (_formula.xlsx)
│         │         └─── Column N: Product name + price change string
│         │         └─── Column O: Price ratio percentage
│         │
│         └─── Task 4: analyze_price_changes
│              ├─── Agent: data_analyst_agent
│              ├─── Context: parse_excel_file, generate_formula_excel
│              ├─── Tools: PriceCategorizationTool
│              └─── Output: Flat JSON with 5 categories
│                   ├─── LICENSEE CHANGES
│                   ├─── NEW SKUs
│                   ├─── Permanent Changes (96%-104% ratio)
│                   ├─── Begin LTO (ratio < 96%)
│                   └─── End LTO (ratio > 104%)
│
├─── CREW 2: Pricing Analysis Crew (runs in parallel)
│    │
│    ├─── AGENT: pricing_trend_analyst_agent
│    │    ├─── Role: Pricing Trend Analyst & Forecasting Specialist
│    │    ├─── Model: claude-sonnet-4-5
│    │    └─── Tools:
│    │         ├─── HistoricalPriceAnalysisTool (calculates week-over-week changes)
│    │         ├─── PriceForecastingTool (exponential weighted moving average)
│    │         └─── AnomalyDetectionTool (z-score ranking)
│    │
│    └─── TASKS (Sequential):
│         ├─── Task 1: analyze_historical_trends
│         │    ├─── Agent: pricing_trend_analyst_agent
│         │    ├─── Input: Historical_price_change_summary_report_vF.xlsx
│         │    ├─── Tools: HistoricalPriceAnalysisTool
│         │    ├─── Process: Calculates statistics for 108 SKUs (mean, std, min, max)
│         │    └─── Output: historical_analysis_results.json
│         │
│         ├─── Task 2: forecast_next_week_prices
│         │    ├─── Agent: pricing_trend_analyst_agent
│         │    ├─── Tools: PriceForecastingTool
│         │    ├─── Process: Uses last 8 weeks with exponential weighting
│         │    └─── Output: price_forecasts.json (forecasted prices for all SKUs)
│         │
│         └─── Task 3: identify_notable_changes
│              ├─── Agent: pricing_trend_analyst_agent
│              ├─── Tools: AnomalyDetectionTool
│              ├─── Process: Calculates z-scores, ranks by statistical significance
│              └─── Output: pricing_anomalies.json (top 10 notable changes)
│
├─── CREW 3: Email Builder Crew
│    │
│    ├─── AGENT: email_content_writer_agent
│    │    ├─── Role: TBS Price Change Email Writer
│    │    ├─── Model: claude-sonnet-4-5 (max_tokens=8000)
│    │    └─── Tools: None (LLM-based formatting only)
│    │
│    └─── TASKS:
│         └─── Task 1: write_highlights_content
│              ├─── Agent: email_content_writer_agent
│              ├─── Inputs:
│              │    ├─── price_changes_categorized (from Crew 1)
│              │    ├─── effective_date (from Crew 1)
│              │    └─── pricing_forecast_analysis (from Crew 2, optional)
│              ├─── Process:
│              │    ├─── Groups Permanent/Begin LTO/End LTO by brewer:
│              │    │    ├─── LABATT (Budweiser, Stella, Corona, etc.)
│              │    │    ├─── MOLSON (Coors, Heineken, Miller, etc.)
│              │    │    ├─── SLEEMAN (Sleeman, Sapporo, Colt 45)
│              │    │    └─── Other (Laker, Peroni, Guinness, etc.)
│              │    ├─── Keeps Licensee Changes & New SKUs ungrouped
│              │    └─── Adds pricing forecast table if available
│              └─── Output: Complete plain text email with subject line
│
└─── SAVE OUTPUT
     ├─── Email content: price_change_email_YYYY-MM-DD.txt
     └─── Metadata: price_change_email_YYYY-MM-DD_metadata.json
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ INPUT PHASE                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼──────────────────────────┐
            │                         │                          │
            ▼                         ▼                          ▼
  Excel File (Current Week)    Historical Excel         email_recipients
  "TBS Price Change...xlsx"    (108 SKUs, 2018-2025)    (config/env)
            │                         │                          │
            │                         │                          │
┌───────────▼──────────────┐  ┌───────▼──────────────┐          │
│  CREW 1: Excel Processor │  │ CREW 2: Pricing      │          │
│                          │  │ Analysis             │          │
│  ┌─────────────────────┐ │  │                      │          │
│  │ Task 1: Parse Excel │ │  │ ┌──────────────────┐ │          │
│  │  • ExcelReaderTool  │ │  │ │ Task 1: Analyze  │ │          │
│  │  • DataCleanerTool  │ │  │ │ Historical Trends│ │          │
│  └──────────┬──────────┘ │  │ │  • HistoricalTool│ │          │
│             ▼            │  │ └────────┬─────────┘ │          │
│  ┌─────────────────────┐ │  │          ▼           │          │
│  │ Task 2: Extract     │ │  │   historical_       │          │
│  │ Effective Date      │ │  │   analysis_         │          │
│  │  • DateExtractor    │ │  │   results.json      │          │
│  └──────────┬──────────┘ │  │          │           │          │
│             ▼            │  │          ▼           │          │
│  ┌─────────────────────┐ │  │ ┌──────────────────┐ │          │
│  │ Task 3: Generate    │ │  │ │ Task 2: Forecast │ │          │
│  │ Formula Excel       │ │  │ │ Next Week Prices │ │          │
│  │  • FormulaExcelGen  │ │  │ │  • ForecastTool  │ │          │
│  └──────────┬──────────┘ │  │ └────────┬─────────┘ │          │
│             ▼            │  │          ▼           │          │
│   _formula.xlsx          │  │   price_forecasts   │          │
│   (Columns N & O added)  │  │   .json             │          │
│             │            │  │          │           │          │
│             ▼            │  │          ▼           │          │
│  ┌─────────────────────┐ │  │ ┌──────────────────┐ │          │
│  │ Task 4: Categorize  │ │  │ │ Task 3: Identify │ │          │
│  │ Price Changes       │ │  │ │ Notable Changes  │ │          │
│  │  • PriceCategorize  │ │  │ │  • AnomalyTool   │ │          │
│  └──────────┬──────────┘ │  │ └────────┬─────────┘ │          │
│             ▼            │  │          ▼           │          │
│   price_categories.json  │  │   pricing_anomalies │          │
│   {                      │  │   .json             │          │
│     "LICENSEE CHANGES",  │  │   (Top 10 SKUs by   │          │
│     "NEW SKUs",          │  │    z-score)         │          │
│     "Permanent Changes", │  │                      │          │
│     "Begin LTO",         │  │                      │          │
│     "End LTO"            │  │                      │          │
│   }                      │  │                      │          │
└───────────┬──────────────┘  └───────────┬──────────┘          │
            │                             │                     │
            └─────────────────┬───────────┘                     │
                              ▼                                 │
┌─────────────────────────────────────────────────────────────┐ │
│  CREW 3: Email Builder                                      │ │
│                                                              │ │
│  ┌────────────────────────────────────────────────────────┐ │ │
│  │ Task 1: Write Highlights Content                       │ │ │
│  │  • Groups Permanent/Begin LTO/End LTO by brewer        │ │ │
│  │  • Keeps Licensee Changes & New SKUs ungrouped         │ │ │
│  │  • Adds pricing forecast table (if available)          │ │ │
│  │  • Formats complete email with subject & signature     │ │◄┘
│  └──────────────────────────┬─────────────────────────────┘ │
│                             ▼                                │
│   Plain Text Email                                           │
│   ┌────────────────────────────────────────────────────┐    │
│   │ Subject: TBS Price Change Summary – Effective Date │    │
│   │                                                     │    │
│   │ Dear Team,                                          │    │
│   │ [Context paragraph]                                 │    │
│   │                                                     │    │
│   │ Highlights (Price Before Tax and Deposit)          │    │
│   │                                                     │    │
│   │ LABATT                                              │    │
│   │   Begin LTO: [products]                             │    │
│   │   End LTO: [products]                               │    │
│   │   Permanent Changes: [products]                     │    │
│   │                                                     │    │
│   │ MOLSON / SLEEMAN / Other [same structure]          │    │
│   │                                                     │    │
│   │ LICENSEE CHANGES: [ungrouped products]             │    │
│   │ NEW SKUs: [ungrouped products]                     │    │
│   │                                                     │    │
│   │ PRICING TREND FORECAST – Next Week (OPTIONAL)      │    │
│   │ [Table with top 10 notable changes]                │    │
│   │                                                     │    │
│   │ Best regards, Mark Robinson                         │    │
│   └────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT PHASE                                                                │
│  • price_change_email_YYYY-MM-DD.txt                                        │
│  • price_change_email_YYYY-MM-DD_metadata.json                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Crew Interaction & Orchestration

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ RevManFlow Orchestrator (main.py)                                           │
│                                                                              │
│  ┌─────────┐     ┌──────────────────┐     ┌──────────────────┐             │
│  │ Trigger │ ──▶ │ Process Excel    │ ──▶ │ Email Generation │ ──▶ Save   │
│  │         │     │ (Crew 1)         │     │ (Crew 3)         │             │
│  └─────────┘     └──────────────────┘     └──────────────────┘             │
│                           │                        ▲                         │
│                           │                        │                         │
│                           │     ┌──────────────────┴───────┐                │
│                           └────▶│ Pricing Trend Analysis   │                │
│                                 │ (Crew 2)                 │                │
│                                 └──────────────────────────┘                │
│                                                                              │
│  Flow State Variables:                                                      │
│  • excel_file_path (input)                                                  │
│  • trigger_date (auto-generated)                                            │
│  • effective_date (extracted by Crew 1)                                     │
│  • raw_data (from Crew 1)                                                   │
│  • price_changes_categorized (from Crew 1) ──────────┐                     │
│  • pricing_forecast_analysis (from Crew 2, optional) ├─▶ Crew 3 Inputs     │
│  • email_recipients (from config/env) ───────────────┘                     │
│  • email_content (output from Crew 3)                                       │
│  • email_subject (output from Crew 3)                                       │
│  • email_metadata (output from Crew 3)                                      │
└──────────────────────────────────────────────────────────────────────────────┘

Key Orchestration Points:
├─ Crew 1 & Crew 2 run in parallel (no direct dependency)
├─ Crew 3 waits for both Crew 1 & Crew 2 to complete
├─ If Crew 2 fails, Crew 3 continues without forecast data
└─ All communication via Flow state (no direct crew-to-crew calls)
```

---

## Tool Responsibilities Matrix

| Tool Name                    | Crew | Agent               | Purpose                                      | Input                    | Output                     |
|------------------------------|------|---------------------|----------------------------------------------|--------------------------|----------------------------|
| ExcelReaderTool              | 1    | excel_parser        | Read Excel, skip headers, extract columns    | Excel file path          | Structured JSON records    |
| DataCleanerTool              | 1    | excel_parser        | Clean nulls, normalize text                  | Raw records              | Cleaned records            |
| DateExtractorTool            | 1    | excel_parser        | Extract date from filename                   | Filename string          | ISO date, display date     |
| FormulaExcelGeneratorTool    | 1    | excel_parser        | Create formula Excel (columns N & O)         | Excel file, output dir   | Formula Excel path         |
| PriceCalculatorTool          | 1    | data_analyst        | Calculate price change amount & percentage   | Old price, new price     | Change stats JSON          |
| PriceCategorizationTool      | 1    | data_analyst        | Categorize products into 5 groups            | Formula Excel path       | Categorized products JSON  |
| HistoricalPriceAnalysisTool  | 2    | pricing_trend       | Analyze week-over-week changes, calculate stats | Historical Excel path | historical_analysis.json   |
| PriceForecastingTool         | 2    | pricing_trend       | Forecast next week prices (EWMA)             | Analysis results JSON    | price_forecasts.json       |
| AnomalyDetectionTool         | 2    | pricing_trend       | Identify top 10 notable changes (z-score)    | Forecasts JSON           | pricing_anomalies.json     |

---

## Key Business Logic Explained

### 1. Price Categorization (Crew 1, Task 4)

The system categorizes ALL products into exactly 5 categories based on two factors:

**Factor A: Type of Sale**
- "TBS - Licensee" → LICENSEE CHANGES
- "New SKU" → NEW SKUs
- "TBS - Retail Price" → Continue to Factor B

**Factor B: Price Ratio (only for TBS - Retail Price)**
- Price Ratio = (New Price / Old Price) × 100
- 96% ≤ ratio ≤ 104% → **Permanent Changes**
- ratio < 96% → **Begin LTO** (price dropped >4%)
- ratio > 104% → **End LTO** (price increased >4%)

**Example:**
- Old: $50.00 | New: $48.00 → Ratio: 96% → **Permanent Change**
- Old: $50.00 | New: $45.00 → Ratio: 90% → **Begin LTO**
- Old: $50.00 | New: $55.00 → Ratio: 110% → **End LTO**

---

### 2. Historical Analysis & Forecasting (Crew 2)

**Step 1: Historical Analysis (Task 1)**
- Reads 108 SKUs with weekly prices from 2018 to October 2025
- Calculates week-over-week percentage change: ((Price_Week_N - Price_Week_N-1) / Price_Week_N-1) × 100
- Computes statistics for each SKU: mean, standard deviation, min, max

**Step 2: Forecasting (Task 2)**
- Uses Exponential Weighted Moving Average (EWMA) of last 8 weeks
- Recent weeks receive higher weight than older weeks
- Formula: Forecasted_Change = Σ(weight_i × change_i) where recent weights > older weights
- Forecasted_Price = Current_Price × (1 + Forecasted_Change/100)

**Step 3: Anomaly Detection (Task 3)**
- Calculates z-score for each SKU: z = (Forecasted_Change - Historical_Mean) / Historical_StdDev
- Ranks ALL 108 SKUs by absolute z-score
- Selects top 10 most statistically significant changes
- z-score > 2.0 indicates change is >2 standard deviations from historical average (highly unusual)

---

### 3. Email Brewer Grouping (Crew 3, Task 1)

Only **Permanent Changes**, **Begin LTO**, and **End LTO** are grouped by brewer. The agent groups products based on brand names:

**LABATT Group:**
- Budweiser, Bud Light, Stella Artois, Corona, Modelo, Becks, Hoegaarden, Michelob, Mill St

**MOLSON Group:**
- Coors, Molson Canadian, Miller, Heineken, Creemore

**SLEEMAN Group:**
- Sleeman, Sapporo, Colt 45

**Other Group:**
- All remaining brands: Laker, Peroni, James Ready, Moosehead, Guinness, Steam Whistle, Muskoka, Beaus, etc.

**Ungrouped Sections:**
- LICENSEE CHANGES (listed individually)
- NEW SKUs (listed individually)

---

## Summary: How It All Works Together

1. **Input:** User provides an Excel file like "TBS Price Change Summary Report - October 13th'25.xlsx"

2. **Crew 1 (Excel Processor)** processes the file:
   - Parses Excel data (skips 7 header rows, extracts columns A-L)
   - Extracts effective date from filename
   - Creates formula Excel with product name strings and price ratios
   - Categorizes ALL products into 5 groups based on Type of Sale and price ratio

3. **Crew 2 (Pricing Analysis)** runs in parallel:
   - Analyzes historical price data (108 SKUs, 2018-2025)
   - Forecasts next week's prices using weighted moving average
   - Identifies top 10 statistically significant changes using z-scores

4. **Crew 3 (Email Builder)** combines all data:
   - Groups Permanent/Begin LTO/End LTO by brewer (LABATT, MOLSON, SLEEMAN, Other)
   - Lists Licensee Changes and New SKUs ungrouped
   - Adds pricing forecast table if Crew 2 succeeded
   - Formats complete professional email with subject line and signature

5. **Output:** Plain text email saved to `data/output/price_change_email_YYYY-MM-DD.txt`

**The entire process is orchestrated by RevManFlow (main.py)**, which manages state, sequences crew execution, and ensures all data flows correctly from one crew to the next. This design allows each crew to focus on its specific expertise while maintaining clear separation of concerns.
