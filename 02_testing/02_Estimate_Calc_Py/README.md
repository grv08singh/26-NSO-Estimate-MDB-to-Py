# NSO Crop Yield & Percentage Standard Error Estimation Engine

Modern, modular, object-oriented Python implementation replicating the crop yield rate (Kg/ha) and percentage Standard Error (%SE) estimation pipeline from the National Statistical Office (NSO) India **Improvement of Crop Statistics (ICS) Scheme** (`ESTIMATE.accdb`).

---

## User Interfaces for Windows

You have two convenient graphical user interfaces designed to run on Windows:

### 1. Native Windows Desktop GUI (`app_gui.py`)
A fast, native Windows desktop application built with Python's native `tkinter` and `ttk`. It requires **zero** external web browsers or web servers.

**How to launch:**
- Double-click **`Launch_Estimate_GUI.bat`** in the repository root, or:
- From terminal:
  ```bash
  python 02_Estimate_Calc_Py/app_gui.py
  ```

**Key Features:**
- 📁 **Data Source Selection**: Load directly from Microsoft Access (`.accdb` / `.mdb`), CSV, Excel (`.xlsx`), or synthetic mock data.
- ⚙️ **Live CCF Calculation**: Enter driage ratio ($d$), recovery ratio ($r$), and plot conversion factor ($f$) with instant CCF readout.
- 🎯 **Filter Parameters**: Choose Sample Type (Central, State, Combined), Crop Code, Season Code, and State Code.
- 📊 **Metric Cards**: Immediate visual KPIs for State Estimated Dry Yield (Kg/ha), Variance, Standard Error (Kg/ha), and %SE with green/amber/red precision indicator.
- 📑 **Interactive Tabs**:
  - **District Breakdown Table**: Scrollable sortable data grid showing each district's yields, weights, areas, and intermediate ANOVA terms.
  - **Official NSO Summary Report**: Monospaced text view mirroring the official Access reports.
  - **ANOVA Variance Details**: Comprehensive table of between-village MS, within-village MS, and sampling degrees of freedom.
- 💾 **One-Click Export**: Save district tables to CSV or full statistical summaries to JSON.

---

### 2. Modern Interactive Web Dashboard (`app_web.py`)
An interactive web interface powered by Streamlit.

**How to launch:**
- Double-click **`Launch_Estimate_Web.bat`** in the repository root, or:
- From terminal:
  ```bash
  streamlit run 02_Estimate_Calc_Py/app_web.py
  ```

---

## Architecture Overview

```
02_Estimate_Calc_Py/
├── models/                     # Data models (dataclasses)
│   ├── conversion_factors.py   # Driage, recovery, and plot-to-hectare factors (CCF)
│   ├── experiment.py           # Individual CCE observation representation
│   └── district_result.py      # DistrictEstimate and StateEstimate statistical models
├── loaders/                    # Extensible data ingestion layer
│   ├── base_loader.py          # Abstract BaseDataLoader interface
│   ├── access_loader.py        # Loads directly from Access (.accdb/.mdb) via pyodbc
│   ├── tabular_loader.py       # Loads from CSV, Excel (.xlsx/.xls), or pandas DataFrames
│   └── mock_loader.py          # Synthetic CCE generator for demos & automated tests
├── engine/                     # Core calculation engine
│   ├── preprocessor.py         # Filtering (INSPSTATE=1, REJ!=1), sample & crop routing
│   ├── village_calculator.py   # Village-level sums (col11, nij^2)
│   ├── district_calculator.py  # District yield, degrees of freedom, ANOVA components
│   ├── merger.py               # District merging logic
│   └── state_estimator.py      # State-level weighted yield, ANOVA variance & %SE
├── pipeline.py                 # NSOEstimatePipeline orchestrator
├── cli.py                      # Full-featured Command-Line Interface
├── requirements.txt            # Package dependencies
├── CHECKPOINT.md               # Session history & resumption context
└── tests/                      # Automated unittest test suite
    └── test_pipeline.py
```

---

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies
- `pandas >= 2.0.0`
- `numpy >= 1.24.0`
- `pyodbc >= 5.0.0` (required if reading directly from Access `.accdb`/`.mdb` files)
- `openpyxl >= 3.1.0` (required if reading from Excel files)

---

## Quick Start

### 1. Command-Line Interface (CLI)

#### Run on Synthetic Mock Data (Demo Mode)
```bash
python cli.py --mock --driage-ratio 0.75 --recovery-ratio 1.0 --conversion-factor 0.4
```

#### Run against Microsoft Access Database
```bash
python cli.py \
  --db-path "../01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE.accdb" \
  --table-name "total estimate" \
  --driage-ratio 0.7502 \
  --recovery-ratio 1.0 \
  --conversion-factor 0.4 \
  --export-csv "districts_output.csv" \
  --export-json "state_output.json"
```

#### Run against CSV / Excel Files
```bash
python cli.py \
  --experiments-csv "path/to/experiments.csv" \
  --areas-csv "path/to/district_areas.csv" \
  --driage-ratio 0.75 \
  --recovery-ratio 1.0 \
  --conversion-factor 0.4
```

---

### 2. Python Programmatic Usage

```python
from pipeline import NSOEstimatePipeline
from models.conversion_factors import ConversionFactors
from loaders.tabular_loader import TabularDataLoader

# 1. Define conversion factors
factors = ConversionFactors(
    driage_ratio=0.7502,
    recovery_ratio=1.0,
    conversion_factor=0.4
)

# 2. Initialize pipeline with data
pipeline = NSOEstimatePipeline(
    experiments_file="path/to/experiments.csv",
    areas_file="path/to/areas.csv",
    conversion_factors=factors
)

# 3. Execute estimation
result = pipeline.run(
    state_code='33',
    season_code='4',
    crop_code='1611',
    sample_type='2'
)

# 4. Access statistical outputs
print(f"State Dry Yield: {result.state_dry_yield:,.0f} Kg/ha")
print(f"Variance:        {result.dry_yield_variance:,.0f}")
print(f"Standard Error: {result.standard_error:,.2f} Kg/ha")
print(f"Percentage SE:  {result.percentage_se:.1f} %")

# 5. Export results
df_districts = pipeline.to_district_dataframe()
pipeline.print_summary()
pipeline.export_csv("districts_summary.csv")
```

---

## Mathematical Formulation

### 1. Composite Conversion Factor (CCF)
$$\text{CCF} = d \times r \times f$$
Where $d$ is the driage ratio, $r$ is the recovery ratio, and $f$ converts plot weight (g) to per-hectare yield (Kg/ha).

### 2. District Yield Rate
$$\bar{y}_i^{(\text{green})} = \text{Round}\left(\frac{\sum_j \sum_k y_{ijk}}{n_i}, 0\right)$$
$$\bar{y}_i^{(\text{dry})} = \text{Round}\left(\bar{y}_i^{(\text{green})} \times \text{CCF}, 0\right) \quad (\text{Kg/hectare})$$

### 3. State Weighted Yield
$$\bar{Y}_{\text{state}} = \text{Round}\left(\frac{\sum_i \bar{y}_i^{(\text{dry})} \times A_i}{\sum_i A_i}, 0\right) \quad (\text{Kg/hectare})$$

### 4. Percentage Standard Error (%SE)
Following NSO's two-stage stratified ANOVA variance formulas:
$$\text{Var}(\bar{Y}) = \text{Round}\left(V_{\text{green}} \times \overline{\text{CCF}}^2, 0\right)$$
$$\text{SE} = \text{Round}\left(\sqrt{\text{Var}(\bar{Y})}, 2\right) \quad (\text{Kg/hectare})$$
$$\%\text{SE} = \text{Round}\left(\frac{\text{SE} \times 100}{\bar{Y}_{\text{state}}}, 1\right)$$

---

## Running Automated Tests

```bash
python -m unittest discover -s tests
```
All unit tests verify:
- Conversion factor validation
- Village-level statistical aggregations against known values
- Mock end-to-end pipeline execution
- Schema compatibility with `ESTIMATE.accdb`
