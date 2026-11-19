# NSO Crop Estimation Python Pipeline — Session History & Checkpoint

> **Date & Timestamp:** 2026-11-20T00:11:00+05:30  
> **Status:** Fully functional, modular, OOP pipeline implemented and verified.

---

## 1. Project Context & Objectives

The goal of this project is to convert the Microsoft Access database (`01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE.accdb`) used by the **National Statistical Office (NSO), India** under the **Improvement of Crop Statistics (ICS) Scheme** into a clean, modern, modular, object-oriented Python pipeline in `02_Estimate_Calc_Py`.

The calculations determine:
1. **Average Dry Yield Rate** in Kg per hectare.
2. **Variance and Standard Error (SE)** in Kg per hectare.
3. **Percentage Standard Error (%SE)** for district and state-level crop production estimates.

---

## 2. Completed Milestones

### Phase 1: Reverse-Engineering & Mathematical Analysis
- Extracted and analyzed all 22 tables, 35+ queries, 17 forms, and reports from `ESTIMATE.accdb`.
- Reverse-engineered the core queries:
  - `Query1` (per-experiment village flags and weight squared).
  - `Query4` and `COL11NIJ2` (village-level $(\sum y)^2 / n_{ij}$ and $n_{ij}^2$).
  - `prebasictable query` and `basictable query` (district aggregation with crop area).
  - `finalestimatequery` and `finalquery` (intermediate ANOVA scaling factors, green yield, and dry yield).
  - **Reports `%se` and `INTERMEDIATE TABLE`**: Discovered the exact ANOVA formulas for between-village mean square ($Text0$), within-village mean square ($Text1$), weighted green variance ($Text3$), dry variance ($Text4$), SE ($Text5$), and %SE ($Text6$).
- Produced the comprehensive analytical markdown:
  - [`01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE_Calculation_Workflow.md`](file:///d:/05%20GIT/26-NSO-Estimate-MDB-to-Py/01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE_Calculation_Workflow.md)

### Phase 2: Python Pipeline Implementation (`02_Estimate_Calc_Py`)
Built a modular, object-oriented package with the following directory structure:

```
02_Estimate_Calc_Py/
├── __init__.py                     # Package entry point
├── cli.py                          # CLI runner with argparse
├── pipeline.py                     # NSOEstimatePipeline orchestrator
├── requirements.txt                # Dependencies (pandas, numpy, pyodbc, openpyxl)
├── CHECKPOINT.md                   # This resume checkpoint file
├── README.md                       # Comprehensive project & formula documentation
├── models/
│   ├── __init__.py
│   ├── conversion_factors.py       # ConversionFactors (driage, recovery, cf, CCF)
│   ├── experiment.py               # ExperimentRecord dataclass
│   └── district_result.py          # DistrictEstimate & StateEstimate dataclasses
├── loaders/
│   ├── __init__.py
│   ├── base_loader.py              # Abstract BaseDataLoader interface
│   ├── access_loader.py            # AccessDataLoader (loads from .accdb/.mdb via pyodbc)
│   ├── tabular_loader.py           # TabularDataLoader (loads from CSV, Excel, DataFrame)
│   └── mock_loader.py              # MockDataLoader (synthetic CCE test generator)
├── engine/
│   ├── __init__.py
│   ├── preprocessor.py             # ExperimentPreprocessor (harvest filtering, sample selection)
│   ├── village_calculator.py       # VillageCalculator (col11, nij^2, village aggregates)
│   ├── district_calculator.py      # DistrictCalculator (dry yield, ANOVA df, col9, col12)
│   ├── merger.py                   # DistrictMerger (district merging rules)
│   └── state_estimator.py          # StateEstimator (weighted yield, ANOVA MS, SE, %SE)
└── tests/
    ├── __init__.py
    └── test_pipeline.py            # Unit test suite covering loaders, calculators, and end-to-end
```

### Phase 3: Testing & Verification
- Test suite executed via `unittest discover` with 100% pass rate.
- CLI tested with `--mock` synthetic mode and validated against live Access database (`ESTIMATE.accdb`).
- Successfully exported district results to `districts_output.csv` and state results to `state_output.json`.

### Phase 4: Graphical User Interfaces for Windows
- **Native Windows Desktop GUI (`app_gui.py`)**:
  - Native Windows desktop application built using `tkinter` / `ttk`.
  - Supports loading from Access databases, CSV/Excel, and mock data.
  - Interactive parameter entry, CCF live calculation, filter controls.
  - Visual KPI cards for State Dry Yield, Variance, SE, and %SE (with color precision alert).
  - Multi-tabbed views: District table, Official NSO report text, and ANOVA variance components.
  - Single-click CSV and JSON export.
  - Launchable via desktop double-click with `Launch_Estimate_GUI.bat`.
- **Streamlit Web Dashboard (`app_web.py`)**:
  - Modern web dashboard launchable via `Launch_Estimate_Web.bat` or `streamlit run app_web.py`.

---

## 3. Mathematical Reference Guide

### Notation
- $i$: District index
- $j$: Village / Selection Order (`SELORDER`) index
- $k$: Experiment index
- $n_{ij}$: Number of experiments in village $j$ of district $i$
- $y_{ijk}$: Green net weight in grams from experiment $k$
- $m_i$: Number of sampled villages in district $i$
- $n_i = \sum_j n_{ij}$: Total experiments in district $i$
- $A_i$: Crop area in district $i$ (hectares)
- $d, r, f$: Driage ratio, recovery ratio, plot-to-hectare conversion factor
- $\text{CCF} = d \times r \times f$

### Village Level
$$\text{col11}_{ij} = \frac{\left(\sum_k y_{ijk}\right)^2}{n_{ij}}, \quad \text{nij2}_{ij} = n_{ij}^2$$

### District Level
- $\text{Green Yield}_i = \text{Round}\left(\frac{\sum_{j,k} y_{ijk}}{n_i}, 0\right)$ (grams/plot)
- $\text{Dry Yield}_i = \text{Round}(\text{Green Yield}_i \times \text{CCF}, 0)$ (Kg/hectare)
- $\hat{\imath}_i = \text{Round}\left(\frac{n_i^2 - \sum_j n_{ij}^2}{n_i (m_i - 1)}, 2\right)$
- $\frac{A_i^2}{n_i} = \text{Round}\left(\frac{A_i^2}{n_i}, 0\right)$
- $\text{col9}_i = \text{Round}\left(\frac{A_i^2 \sum_j n_{ij}^2}{n_i \cdot \hat{\imath}_i}, 0\right)$
- $\text{col12}_i = \text{Round}\left(\frac{(\sum y_{ijk})^2}{n_i}, 0\right)$

### State Level (Report `%se`)
- **Total Area:** $A = \sum_i A_i$
- **State Dry Yield:** $\bar{Y}_{\text{state}} = \text{Round}\left(\frac{\sum_i \text{Dry Yield}_i \times A_i}{A}, 0\right)$
- **Between-Village Mean Square ($Text0$):**
  $$Text0 = \text{Round}\left(\frac{\sum_i \text{col11}_i - \sum_i \text{col12}_i}{\sum_i (m_i - 1)}, 0\right)$$
- **Within-Village Mean Square ($Text1$):**
  $$Text1 = \begin{cases} \text{"Not Applicable"}, & \text{if equal sampling } (\sum i = \sum check) \\ \text{Round}\left(\frac{\sum y^2 - \sum \text{col11}}{\sum (n_i - m_i)}, 0\right), & \text{otherwise} \end{cases}$$
- **Green Variance ($Text3$):**
  $$Text3 = \begin{cases} \text{Round}\left(\frac{Text0 \sum (A_i^2/n_i)}{A^2}, 0\right), & \text{if equal sampling} \\ \text{Round}\left(\frac{Text1 \sum (A_i^2/n_i) + (Text0 - Text1) \cdot Text46}{A^2}, 0\right), & \text{otherwise} \end{cases}$$
- **Dry Yield Variance ($Text4$):**
  $$\text{Var}(\bar{Y}) = \text{Round}(Text3 \times \overline{\text{CCF}}^2, 0)$$
- **Standard Error ($Text5$):**
  $$\text{SE} = \text{Round}\left(\sqrt{\text{Var}(\bar{Y})}, 2\right) \quad (\text{Kg/ha})$$
- **Percentage Standard Error ($Text6$):**
  $$\%\text{SE} = \text{Round}\left(\frac{\text{SE} \times 100}{\bar{Y}_{\text{state}}}, 1\right)$$

---

## 4. How to Resume Later

### Running Unit Tests
```bash
python -m unittest discover -s "02_Estimate_Calc_Py/tests"
```

### Running with Mock Data (Demonstration)
```bash
python 02_Estimate_Calc_Py/cli.py --mock --driage-ratio 0.75 --recovery-ratio 1.0 --conversion-factor 0.4
```

### Running with Access Database
```bash
python 02_Estimate_Calc_Py/cli.py \
  --db-path "01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE.accdb" \
  --table-name "total estimate" \
  --driage-ratio 0.7502 \
  --recovery-ratio 1.0 \
  --conversion-factor 0.4 \
  --export-csv "02_Estimate_Calc_Py/districts_output.csv" \
  --export-json "02_Estimate_Calc_Py/state_output.json"
```

### Programmatic Usage in Python
```python
from pipeline import NSOEstimatePipeline
from models.conversion_factors import ConversionFactors
from loaders.access_loader import AccessDataLoader

factors = ConversionFactors(driage_ratio=0.7502, recovery_ratio=1.0, conversion_factor=0.4)
pipeline = NSOEstimatePipeline(
    db_path="01_Estimate_Workflow_in_mdb/ASSOFTWARE/ESTIMATE.accdb",
    conversion_factors=factors
)
result = pipeline.run(state_code='33', season_code='4', crop_code='1611', sample_type='2')
pipeline.print_summary()
df_districts = pipeline.to_district_dataframe()
```

---

## 5. Potential Next Steps (When Resuming)
1. **Batch Pipeline / Multi-Crop runner**: Add a script to loop over all crops, seasons, and sample types in the database and generate consolidated Excel workbooks.
2. **REST API / Streamlit Dashboard**: Build an interactive web UI where users can upload survey files or select crops and view instant reports with charts.
3. **Database Exporter**: Script to push calculated estimates back into SQL or database tables if needed.
