# RevMan Pricing Analysis - Complete Architecture Documentation

**Generated:** December 9, 2025  
**Author:** GitHub Copilot  
**Repository:** revman_crewai  
**Branch:** feat/production-hardening

---

## Table of Contents

1. [Layer 1: High-Level File Relationships](#layer-1-high-level-file-relationships)
2. [Layer 2: Class Inheritance Diagram](#layer-2-class-inheritance-diagram)
3. [Layer 3: Pydantic Model Relationships](#layer-3-pydantic-model-relationships)
4. [Layer 4: Complete Execution Flow (Runtime)](#layer-4-complete-execution-flow-runtime)
5. [Layer 5: Data Flow Diagram (The Data Journey)](#layer-5-data-flow-diagram-the-data-journey)
6. [Quick Reference: Method Call Summary](#quick-reference-method-call-summary)

---

## Layer 1: High-Level File Relationships

This diagram shows how the Python files import and depend on each other.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FILE HIERARCHY                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              main.py                                              │   │
│  │                         (THE ORCHESTRATOR)                                        │   │
│  │  Imports from:                                                                    │   │
│  │    ├── models/pricing.py      → Pydantic data contracts                          │   │
│  │    └── tools/pricing_analysis_tools.py → Tool classes                            │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                                  │
│                                       │ uses                                             │
│                    ┌──────────────────┴──────────────────┐                              │
│                    ▼                                      ▼                              │
│  ┌────────────────────────────────┐   ┌────────────────────────────────────────────┐   │
│  │    models/pricing.py           │   │    tools/pricing_analysis_tools.py          │   │
│  │    (DATA CONTRACTS)            │   │    (WORKER TOOLS)                           │   │
│  │                                │   │                                             │   │
│  │  • SKUAnalysis                 │   │  Imports from:                              │   │
│  │  • HistoricalAnalysisResult    │   │    └── tools/base_tool.py                   │   │
│  │  • SKUForecast                 │   │                                             │   │
│  │  • ForecastResult              │   │  • HistoricalPriceAnalysisTool              │   │
│  │  • NotableChange               │   │  • PriceForecastingTool                     │   │
│  │  • AnomalyDetectionResult      │   │  • AnomalyDetectionTool                     │   │
│  └────────────────────────────────┘   └─────────────────┬───────────────────────────┘   │
│                                                          │                               │
│                                                          │ inherits                      │
│                                                          ▼                               │
│                                       ┌──────────────────────────────────────────────┐  │
│                                       │    tools/base_tool.py                         │  │
│                                       │    (BASE CLASS)                               │  │
│                                       │                                               │  │
│                                       │  • ValidatedBaseTool                          │  │
│                                       │  • ToolValidationError                        │  │
│                                       └──────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Files Summary

| File | Location | Purpose |
|------|----------|---------|
| `main.py` | `src/revman/main.py` | Flow orchestrator - coordinates all tools |
| `pricing.py` | `src/revman/models/pricing.py` | Pydantic data contracts |
| `pricing_analysis_tools.py` | `src/revman/tools/pricing_analysis_tools.py` | Tool implementations |
| `base_tool.py` | `src/revman/tools/base_tool.py` | Base class with validation |

---

## Layer 2: Class Inheritance Diagram

This diagram shows how tool classes inherit from each other.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               CLASS INHERITANCE                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  crewai.tools.BaseTool (external library)                                               │
│          │                                                                               │
│          │ inherits                                                                      │
│          ▼                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ValidatedBaseTool  (base_tool.py)                                                 │  │
│  │  ├── Attributes:                                                                   │  │
│  │  │     • min_output_items: int = 0                                                 │  │
│  │  │     • required_output_keys: List[str] = []                                      │  │
│  │  │     • fail_on_error_key: bool = True                                            │  │
│  │  │                                                                                 │  │
│  │  └── Methods:                                                                      │  │
│  │        • _run(**kwargs) → str           ← Called by CrewAI, returns JSON string   │  │
│  │        • _execute(**kwargs) → Dict      ← Called directly, returns dict (ABSTRACT)│  │
│  │        • _validate_output(result)       ← Checks required keys, min items          │  │
│  │        • _count_items(result) → int     ← Counts output items                      │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│          │                                                                               │
│          │ inherits (3 child classes)                                                    │
│          ▼                                                                               │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────────────┐   │
│  │HistoricalPriceTool  │   │ PriceForecastingTool│   │ AnomalyDetectionTool        │   │
│  ├─────────────────────┤   ├─────────────────────┤   ├─────────────────────────────┤   │
│  │args_schema:         │   │args_schema:         │   │args_schema:                 │   │
│  │HistoricalPriceInput │   │ PriceForecastInput  │   │ AnomalyDetectionInput       │   │
│  ├─────────────────────┤   ├─────────────────────┤   ├─────────────────────────────┤   │
│  │required_output_keys:│   │required_output_keys:│   │required_output_keys:        │   │
│  │ • sku_analysis      │   │ • forecasts         │   │ • top_10_notable_changes    │   │
│  │ • total_skus        │   │ • total_skus_forec..│   │ • total_anomalies_detected  │   │
│  ├─────────────────────┤   ├─────────────────────┤   ├─────────────────────────────┤   │
│  │_execute():          │   │_execute():          │   │_execute():                  │   │
│  │ → Dict with         │   │ → Dict with         │   │ → Dict with                 │   │
│  │   sku_analysis      │   │   forecasts         │   │   top_10_notable_changes    │   │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Method Differences

| Method | Return Type | Called By | Purpose |
|--------|-------------|-----------|---------|
| `_run()` | `str` (JSON) | CrewAI Agent | Wrapper with validation, returns JSON string |
| `_execute()` | `Dict` | Direct Python code | Actual implementation, returns raw dictionary |

---

## Layer 3: Pydantic Model Relationships

This diagram shows the Pydantic models and how they nest within each other.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          PYDANTIC MODELS (pricing.py)                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  pydantic.BaseModel                                                                      │
│          │                                                                               │
│          │ inherits (6 model classes)                                                    │
│          ▼                                                                               │
│                                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  HISTORICAL ANALYSIS MODELS                                                        │  │
│  ├───────────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                                    │  │
│  │  ┌──────────────────────────────┐                                                 │  │
│  │  │  SKUAnalysis                 │  ← Single SKU's historical data                 │  │
│  │  │  • brand: str                │                                                 │  │
│  │  │  • pack_size: Optional[int]  │                                                 │  │
│  │  │  • mean_change_pct: float    │                                                 │  │
│  │  │  • std_change_pct: float     │                                                 │  │
│  │  │  • latest_price: float       │                                                 │  │
│  │  │  • all_changes: List[float]  │                                                 │  │
│  │  └──────────────────────────────┘                                                 │  │
│  │              ▲                                                                     │  │
│  │              │ contains many                                                       │  │
│  │              │                                                                     │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐     │  │
│  │  │  HistoricalAnalysisResult                                                 │     │  │
│  │  │  • sku_analysis: Dict[str, SKUAnalysis]   ← Maps SKU name → SKUAnalysis  │     │  │
│  │  │  • total_skus: int                                                        │     │  │
│  │  │  • analysis_date: str                                                     │     │  │
│  │  │  ─────────────────────────────────────────────────────────────────────────│     │  │
│  │  │  Methods:                                                                 │     │  │
│  │  │  • from_dict(data) → HistoricalAnalysisResult   (class method)           │     │  │
│  │  │  • to_dict() → Dict                              (instance method)        │     │  │
│  │  └──────────────────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  FORECAST MODELS                                                                   │  │
│  ├───────────────────────────────────────────────────────────────────────────────────┤  │
│  │  ┌──────────────────────────────┐                                                 │  │
│  │  │  SKUForecast                 │  ← Single SKU's forecast                        │  │
│  │  │  • current_price: float      │                                                 │  │
│  │  │  • forecasted_price: float   │                                                 │  │
│  │  │  • forecasted_change_pct     │                                                 │  │
│  │  └──────────────────────────────┘                                                 │  │
│  │              ▲                                                                     │  │
│  │              │ contains many                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐     │  │
│  │  │  ForecastResult                                                           │     │  │
│  │  │  • forecasts: Dict[str, SKUForecast]                                      │     │  │
│  │  │  • total_skus_forecasted: int                                             │     │  │
│  │  │  • from_dict() / to_dict()                                                │     │  │
│  │  └──────────────────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ANOMALY DETECTION MODELS                                                          │  │
│  ├───────────────────────────────────────────────────────────────────────────────────┤  │
│  │  ┌──────────────────────────────┐                                                 │  │
│  │  │  NotableChange               │  ← Single anomaly                               │  │
│  │  │  • sku: str                  │                                                 │  │
│  │  │  • z_score: float            │                                                 │  │
│  │  │  • significance: str (2.3σ)  │                                                 │  │
│  │  └──────────────────────────────┘                                                 │  │
│  │              ▲                                                                     │  │
│  │              │ contains list of                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐     │  │
│  │  │  AnomalyDetectionResult                                                   │     │  │
│  │  │  • top_10_notable_changes: List[NotableChange]                            │     │  │
│  │  │  • total_anomalies_detected: int                                          │     │  │
│  │  │  • from_dict() / to_dict()                                                │     │  │
│  │  └──────────────────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Model Summary Table

| Model | Contains | Purpose |
|-------|----------|---------|
| `SKUAnalysis` | - | Single SKU's historical statistics |
| `HistoricalAnalysisResult` | Dict[str, SKUAnalysis] | All SKUs' historical data |
| `SKUForecast` | - | Single SKU's price prediction |
| `ForecastResult` | Dict[str, SKUForecast] | All SKUs' predictions |
| `NotableChange` | - | Single anomalous price change |
| `AnomalyDetectionResult` | List[NotableChange] | Top 10 most significant changes |

---

## Layer 4: Complete Execution Flow (Runtime)

This diagram shows what happens step-by-step when the code runs.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          RUNTIME EXECUTION FLOW                                          │
│                    (What happens when you run the code)                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  USER RUNS: crewai run                                                                   │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py :: RevManFlow.pricing_trend_analysis()                                  │    │
│  │  Line 134-220                                                                    │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │                                                                                 │
│  ══════╧════════════════════════════════════════════════════════════════════════════    │
│  STEP 1: HISTORICAL ANALYSIS                                                             │
│  ══════════════════════════════════════════════════════════════════════════════════════  │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 164-165:                                                           │    │
│  │  historical_tool = HistoricalPriceAnalysisTool()                                 │    │
│  │                     └── Creates instance of the tool class                       │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 167-170:                                                           │    │
│  │  historical_result = historical_tool._execute(                                   │    │
│  │      file_path=str(historical_file_path),                                        │    │
│  │      save_to_file=False                                                          │    │
│  │  )                                                                               │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ calls                                       │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  pricing_analysis_tools.py :: HistoricalPriceAnalysisTool._execute()             │    │
│  │  Line 137-230                                                                    │    │
│  │  ─────────────────────────────────────────────────────────────────────────────── │    │
│  │  What it does:                                                                   │    │
│  │  1. Path(file_path) → Resolve file location                                      │    │
│  │  2. pd.read_excel() → Read Excel into DataFrame                                  │    │
│  │  3. df.pct_change() → Calculate week-over-week changes                           │    │
│  │  4. sanitize_float() → Clean NaN/Inf values                                      │    │
│  │  5. return {"sku_analysis": {...}, "total_skus": 150}                            │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ returns Dict                                │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 173:                                                               │    │
│  │  historical_data = HistoricalAnalysisResult.from_dict(historical_result)         │    │
│  │                    └── Converts raw dict to validated Pydantic model             │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ calls                                       │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  pricing.py :: HistoricalAnalysisResult.from_dict()                              │    │
│  │  Line 67-88                                                                      │    │
│  │  ─────────────────────────────────────────────────────────────────────────────── │    │
│  │  What it does:                                                                   │    │
│  │  1. Loop through sku_analysis dict                                               │    │
│  │  2. Sanitize each SKU's data (None → 0.0)                                        │    │
│  │  3. SKUAnalysis(**sku_data) → Create validated SKU model                         │    │
│  │  4. Return HistoricalAnalysisResult with all SKUs                                │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │                                                                                 │
│  ══════╧════════════════════════════════════════════════════════════════════════════    │
│  STEP 2: PRICE FORECASTING                                                               │
│  ══════════════════════════════════════════════════════════════════════════════════════  │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 180-184:                                                           │    │
│  │  forecast_tool = PriceForecastingTool()                                          │    │
│  │  forecast_result = forecast_tool._execute(                                       │    │
│  │      sku_analysis=historical_result.get('sku_analysis', {})  ← CHAINED DATA!    │    │
│  │  )                                                                               │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ calls                                       │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  pricing_analysis_tools.py :: PriceForecastingTool._execute()                    │    │
│  │  Line 288-380                                                                    │    │
│  │  ─────────────────────────────────────────────────────────────────────────────── │    │
│  │  What it does:                                                                   │    │
│  │  1. For each SKU in sku_analysis:                                                │    │
│  │     a. Get latest_price, mean_change, all_changes                                │    │
│  │     b. np.exp(linspace) → Calculate exponential weights                          │    │
│  │     c. np.average(recent, weights) → Weighted moving average                     │    │
│  │     d. forecasted_price = latest * (1 + change/100)                              │    │
│  │  2. return {"forecasts": {...}, "total_skus_forecasted": 150}                    │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ returns Dict → Pydantic conversion          │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 188 + pricing.py:                                                  │    │
│  │  forecast_data = ForecastResult.from_dict(forecast_result)                       │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │                                                                                 │
│  ══════╧════════════════════════════════════════════════════════════════════════════    │
│  STEP 3: ANOMALY DETECTION                                                               │
│  ══════════════════════════════════════════════════════════════════════════════════════  │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 194-198:                                                           │    │
│  │  anomaly_tool = AnomalyDetectionTool()                                           │    │
│  │  anomaly_result = anomaly_tool._execute(                                         │    │
│  │      forecasts=forecast_result.get('forecasts', {})  ← CHAINED DATA!            │    │
│  │  )                                                                               │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ calls                                       │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  pricing_analysis_tools.py :: AnomalyDetectionTool._execute()                    │    │
│  │  Line 450-530                                                                    │    │
│  │  ─────────────────────────────────────────────────────────────────────────────── │    │
│  │  What it does:                                                                   │    │
│  │  1. For each SKU in forecasts:                                                   │    │
│  │     a. z_score = |forecasted_change - mean| / std                                │    │
│  │     b. Append to anomalies list with z_score                                     │    │
│  │  2. anomalies.sort(key=z_score, reverse=True)                                    │    │
│  │  3. top_10 = anomalies[:10]                                                      │    │
│  │  4. return {"top_10_notable_changes": [...], "total_anomalies_detected": 50}     │    │
│  └────────────────────────────────────────┬────────────────────────────────────────┘    │
│                                            │                                             │
│                                            │ returns Dict → stored in flow state         │
│                                            ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  main.py line 202-203:                                                           │    │
│  │  anomaly_data = AnomalyDetectionResult.from_dict(anomaly_result)                 │    │
│  │  self._pricing_forecast_analysis = anomaly_result  ← STORED FOR EMAIL!          │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │                                                                                 │
│  ══════╧════════════════════════════════════════════════════════════════════════════    │
│  STEP 4: DATA FLOWS TO EMAIL                                                             │
│  ══════════════════════════════════════════════════════════════════════════════════════  │
│        │                                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  Later in main.py :: build_email() method                                        │    │
│  │  self._pricing_forecast_analysis → Used to build "Pricing Forecast" email section│    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 5: Data Flow Diagram (The Data Journey)

This diagram shows how data transforms as it flows through the system.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA TRANSFORMATION JOURNEY                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  📊 EXCEL FILE                                                                           │
│  Historical_price_change_summary_report_vF.xlsx                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │ SKU       | BRAND    | Week       | Price | Pack Size | Pack Type  |           │    │
│  │ SKU001    | Budweiser| 2025-01-01 | 12.99 | 12        | Cans       |           │    │
│  │ SKU001    | Budweiser| 2025-01-08 | 13.49 | 12        | Cans       |           │    │
│  │ SKU002    | Corona   | 2025-01-01 | 15.99 | 6         | Bottles    |           │    │
│  │ ...       | ...      | ...        | ...   | ...       | ...        |           │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │ pd.read_excel()                                                                 │
│        │ df.pct_change()                                                                 │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  TOOL 1 OUTPUT: historical_result (Dict)                                         │    │
│  │  {                                                                               │    │
│  │    "sku_analysis": {                                                             │    │
│  │      "SKU001": {                                                                 │    │
│  │        "brand": "Budweiser",                                                     │    │
│  │        "mean_change_pct": 1.23,          ← Average weekly change                │    │
│  │        "std_change_pct": 0.45,           ← How much it varies                   │    │
│  │        "latest_price": 13.49,            ← Most recent price                    │    │
│  │        "all_changes": [3.85, -1.2, 0.5]  ← Every weekly % change               │    │
│  │      },                                                                          │    │
│  │      "SKU002": {...}                                                             │    │
│  │    },                                                                            │    │
│  │    "total_skus": 150                                                             │    │
│  │  }                                                                               │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │ HistoricalAnalysisResult.from_dict()                                            │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  PYDANTIC MODEL: historical_data (HistoricalAnalysisResult)                      │    │
│  │  ├── .sku_analysis["SKU001"] → SKUAnalysis object                                │    │
│  │  │      ├── .brand → "Budweiser"                                                 │    │
│  │  │      ├── .mean_change_pct → 1.23                                              │    │
│  │  │      └── .all_changes → [3.85, -1.2, 0.5]                                     │    │
│  │  └── .total_skus → 150                                                           │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │ Passed to PriceForecastingTool                                                  │
│        │ via sku_analysis=historical_result['sku_analysis']                              │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  TOOL 2 OUTPUT: forecast_result (Dict)                                           │    │
│  │  {                                                                               │    │
│  │    "forecasts": {                                                                │    │
│  │      "SKU001": {                                                                 │    │
│  │        "brand": "Budweiser",                                                     │    │
│  │        "current_price": 13.49,                                                   │    │
│  │        "forecasted_price": 13.65,        ← PREDICTED next week!                 │    │
│  │        "forecasted_change_pct": 1.19,    ← Predicted % change                   │    │
│  │        "historical_mean_change_pct": 1.23,                                       │    │
│  │        "historical_std_change_pct": 0.45                                         │    │
│  │      }                                                                           │    │
│  │    },                                                                            │    │
│  │    "total_skus_forecasted": 150                                                  │    │
│  │  }                                                                               │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │ Passed to AnomalyDetectionTool                                                  │
│        │ via forecasts=forecast_result['forecasts']                                      │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  TOOL 3 OUTPUT: anomaly_result (Dict) → self._pricing_forecast_analysis         │    │
│  │  {                                                                               │    │
│  │    "top_10_notable_changes": [                                                   │    │
│  │      {                                                                           │    │
│  │        "sku": "SKU042",                                                          │    │
│  │        "brand": "Stella Artois",                                                 │    │
│  │        "current_price": 18.99,                                                   │    │
│  │        "forecasted_price": 21.49,                                                │    │
│  │        "forecasted_change_pct": 13.17,                                           │    │
│  │        "z_score": 4.52,                  ← 4.52 std devs from mean!             │    │
│  │        "significance": "4.5σ"            ← Human readable                       │    │
│  │      },                                                                          │    │
│  │      {...9 more...}                                                              │    │
│  │    ],                                                                            │    │
│  │    "total_anomalies_detected": 47                                                │    │
│  │  }                                                                               │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                                 │
│        │ Used by EmailBuilderCrew                                                        │
│        ▼                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │  📧 EMAIL OUTPUT (Pricing Forecast Section)                                      │    │
│  │  ─────────────────────────────────────────────────────────────────────────────── │    │
│  │  PRICING FORECAST: TOP 10 NOTABLE PRICE CHANGES                                  │    │
│  │                                                                                  │    │
│  │  1. Stella Artois 12pk Bottles                                                   │    │
│  │     Current: $18.99 → Forecast: $21.49 (+13.17%)                                 │    │
│  │     Significance: 4.5σ above historical average                                  │    │
│  │                                                                                  │    │
│  │  2. ...                                                                          │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: Method Call Summary

| Step | File | Class | Method | Input | Output |
|------|------|-------|--------|-------|--------|
| 1a | main.py | RevManFlow | `pricing_trend_analysis()` | trigger event | orchestrates all tools |
| 1b | pricing_analysis_tools.py | `HistoricalPriceAnalysisTool` | `_execute()` | file_path | Dict with sku_analysis |
| 1c | pricing.py | `HistoricalAnalysisResult` | `from_dict()` | raw Dict | validated Pydantic model |
| 2a | pricing_analysis_tools.py | `PriceForecastingTool` | `_execute()` | sku_analysis Dict | Dict with forecasts |
| 2b | pricing.py | `ForecastResult` | `from_dict()` | raw Dict | validated Pydantic model |
| 3a | pricing_analysis_tools.py | `AnomalyDetectionTool` | `_execute()` | forecasts Dict | Dict with anomalies |
| 3b | pricing.py | `AnomalyDetectionResult` | `from_dict()` | raw Dict | validated Pydantic model |

---

## Appendix: Key Design Decisions

### Why Direct Tool Calls Instead of AI Agent?

The pricing analysis uses **direct Python calls** (`_execute()`) instead of AI agent calls because:

1. **Reliability** - Direct Python calls are 100% predictable
2. **Speed** - No AI inference delay
3. **Cost** - No API calls = no token costs
4. **Data Integrity** - Data chaining is guaranteed correct

### Why Pydantic Models?

1. **Type Safety** - IDE catches errors before runtime
2. **Validation** - Automatic data sanitization (None → 0.0)
3. **Documentation** - Models are self-documenting
4. **Serialization** - Easy JSON conversion via `to_dict()` / `from_dict()`

---

## Document Information

- **File:** `docs/PRICING_ANALYSIS_ARCHITECTURE.md`
- **Format:** Markdown (can be converted to Word/PDF)
- **Diagrams:** ASCII art (displays correctly in any text editor or Markdown viewer)

### To Convert to Word:

1. Open this file in VS Code
2. Install "Markdown PDF" extension
3. Right-click → "Markdown PDF: Export (pdf)" or use Pandoc:
   ```bash
   pandoc PRICING_ANALYSIS_ARCHITECTURE.md -o PRICING_ANALYSIS_ARCHITECTURE.docx
   ```
