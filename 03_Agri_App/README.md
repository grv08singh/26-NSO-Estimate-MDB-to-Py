## Agriculture Estimation & Report Generation Tool ##

Steps to follow

#### Create Python environment
pip install uvicorn
uv venv .venv --python 3.13
.venv\Source\activate
uv pip install -r requirements.txt

---

## NSO_DGCES_TEST — what was added to this copy

This folder is a copy of `26-NSO-Estimate-MDB-to-Py` (without its git history).

### Folders

```
03_Agri_App/                RULE: every piece of data, from raw to final, is kept STATE-WISE and YEAR-WISE:
                            <top folder>/<NN_module>/<STATE>/<YEAR>/…  (nothing for several states in one place)
                            Modules: 00_masterlist, 01_importschedules, 02_controlregister, 03_viewschedule,
                            04_datavalidation, 05_estimates, 06_estimatereport, 07_rc7, 08_annexures (04_src/utils/folders.py).
                            Code: components/c0N_<module>.py, pipelines/p0N_<module>_pipeline.py
  00_database/        HIDDEN - stored data
    00_masterlist/<STATE>/<YEAR>/        master_list.csv + info.json
    01_importschedules/<STATE>/<YEAR>/   file_cache/ (each file's reading), dgces_samples.json
    04_datavalidation/<STATE>/<YEAR>/    corrections.csv, yield_limits.csv
    05_estimates/<STATE>/<YEAR>/         estimate_inputs.csv (factors), area_sheets.csv
    06_estimatereport/<STATE>/<YEAR>/    report_inputs.csv (typed CES / previous-year figures, dates)
    07_rc7/<STATE>/<YEAR>/               final.csv, final_rows.csv (crops + samples marked final)
    08_annexures/<STATE>/<YEAR>/         previous_rc7.csv (last year's RC-7 when loaded from a file), typed.csv (XVI, XVII, XXV)
  01_raw_data/        input (the picked files, copied)
    00_masterlist/<STATE>/<YEAR>/                 master lists (state + year read from the file)
    01_importschedules/<STATE>/<YEAR>/MDB/        .mdb / .accdb / .zip      (the state + year OPEN in the app;
    01_importschedules/<STATE>/<YEAR>/DGCES/      DGCES Excel                rows of others are left out)
  02_artifacts/       output of each module (all CSV)
    00_masterlist/<STATE>/<YEAR>/        ingested_ML.csv, ML_check_report_*.csv, MasterList_Summary_*.csv,
                                         errors/<date-time>_<file>_ERRORS/
    01_importschedules/<STATE>/<YEAR>/   ingested_sch.csv (RC-7), mdb/ (blocks from .mdb), dgces/ (the same from
                                         DGCES + DGCES_ID), clubbed/ (both), report/ (Files, Tables, Last_import,
                                         DGCES issues …), import_history.csv
    02_controlregister/<STATE>/<YEAR>/   control_register/<date-time>/*.csv, NR/<dd.mm.yyyy>/Central|State/*.xlsx
    03_viewschedule/<STATE>/<YEAR>/      <CROP>/<Central|State>/P_EXPTID_….pdf,
    04_datavalidation/<STATE>/<YEAR>/    Outliers|Basic Data/<CROP>/<Central|State>/*.csv
    05_estimates/<STATE>/<YEAR>/         <Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/<date-time>_<season>_<variety>_<sample>.xlsx
    06_estimatereport/<STATE>/<YEAR>/    <Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/…_report.xlsx
    07_rc7/<STATE>/<YEAR>/               <dd.mm.yyyy>/…_proposed_corrections.csv, …_problems.csv; final/RC7_final.csv
    08_annexures/<STATE>/<YEAR>/         <SEASONS>/<dd.mm.yyyy>/<date-time>_<seasons>_annexures.xlsx + csv/ (a CSV per table)
  03_logs/            <STATE>/<YEAR>/<date>.log (work on that state + year), app/<date>.log (start-up, master lists)
  04_src/             the code (components = work, pipelines = run it, app = window, utils)
  05_backup/          <NN_module>/<STATE>/<YEAR>/<date-time>/ (old stored data), …/raw/<date-time>/ (old copy of a
                      re-picked raw file)
  app.py, run_app.bat         start the window (run_app.bat: on any PC – see below; setup_runtime.ps1,
                              runtime_requirements.txt: the one-time set-up of runtime\)
  run_step.py                 run one module without the window
  bootstrap.py                lets the code in 04_src be imported as `src` (a Python name cannot start with a digit)
  config.yaml                 every path above, and the DGCES codes still to be decided
```

### The app (window)
All data and reports the app writes are CSV (UTF-8, opens in Excel); no limit on rows, quick to read.
The window fits any screen (from about 600 px wide, any Windows scaling): it opens sized to the screen, module
buttons / counts / Season-Crop wrap onto more lines when narrow, the module list folds away by dragging its edge,
and a page scrolls instead of being cut off (`FlowLayout`, `fit_to_screen` in `look.py`).
`python app.py` or double-click `run_app.bat`. Look copied from KrishiStat (`04_src/app/look.py`, `states_page.py`).

**On any PC** (Windows 10 / 11, 64-bit – even one with nothing installed): double-click `run_app.bat`. It uses the first
Python that can run the app – the app's own `runtime\` folder, a `.venv\`, or Anaconda / Miniconda with the libraries. If
there is none, the first start sets up `runtime\` (`setup_runtime.ps1`: the official embeddable Python from python.org +
the libraries of `runtime_requirements.txt`, about 800 MB; needs internet once, under a minute on a good line, no admin rights, nothing installed on
the PC – log in `03_logs/setup_runtime.log`). After that the whole app folder, with `runtime\`, can be copied to a PC with
no internet and started there. Importing .mdb / .accdb schedules also needs Microsoft's "Access Database Engine 2016
Redistributable (x64)" on that PC (CSV / Excel work without it); the set-up says when it is missing.

* **Start page** — welcome only (logo, name, Start).
* **Year** in the top bar — the years with a stored master list (any state). It starts on the current agricultural
  year (July – June) when that has one, else the newest. Every page shows that year.
* **States page** (KrishiStat's cards) — one card per state for the chosen year, with **Open →** when its master list
  for that year is stored (a card without it says which other years it has). **Import Master List…** (once a year) is here: pick the file(s), the state and year are read
  from the file, the checks run, a review shows what changes season by season, and nothing is stored until you confirm.
  A new file replaces only the seasons it contains.
* **00. Master List** — not a module tab: it is imported on the States page (once a year), and the work page's
  **Master list** button shows the stored list of the state + year, view only (crop-wise, district-wise, files and
  checks, backups).
* **Work page** — left: the modules **1. Import Schedules · 2. Control Register · 3. View Schedule · 4. Data Validation · 5. Estimates · 6. Estimate Report · 7. RC7 · 8. Annexures**. Right: **Season** and **Crop** dropdowns
  with counts (from the stored master list; the crops are those of the chosen season; hidden on 7. RC7, which has its own
  season ticks), the chosen module, the log.
  Changing the year in the top bar keeps the same state and module open if the state has that year.
  * 1. Import Schedules: **Choose schedule files…** copies files into `01_raw_data/01_importschedules/MDB|DGCES/<STATE>/<YEAR>/`
    (a file with the same name already there goes to `05_backup/raw/…` first) and runs; tables show the chosen state + year.
  * 2. Control Register and 3. View Schedule: copies of KrishiSoft_V0.1's Control Register and Print Schedules.

Without the window: `python run_step.py 0` (master lists) · `python run_step.py 1` (schedules of every <STATE>/<YEAR> raw folder) · `python run_step.py 2 [STATE YEAR]` (Control Register summary, shown only) · `python run_step.py 5 [STATE YEAR] [--export]` (every saved estimate worked out again; --export writes the workbooks) · `python run_step.py 6 [STATE YEAR] [--export]` (the Estimate Report of every saved estimate) · `python run_step.py 7 [STATE YEAR] [--export]` (RC-7 checks, counted; never applies) · `python run_step.py 8 [STATE YEAR] [--seasons kharif|rabi|2,3] [--export] [--languages Eng,Hi,Bi]` (the Kharif and Rabi reports, or the one given; --export writes the workbooks). (`python -m src.pipelines…` no longer works because the code folder is `04_src`.)

### 00. Master List (`c00_masterlist.py`, `04_src/utils/masterlist_checks.py`)
KrishiSoft's master list checks in **lenient** mode:
* cleaned and listed, not rejected: spaces / tabs / line breaks in text, column names in any case or order, extra
  columns, an EXPTID column (must equal its parts), several sheets in one file, rows repeated exactly;
* real errors reject the file (blank or wrong-width codes, one code with two names, the same Exp-ID with different
  data, more than one state / year in a file, …) and an error report is written to
  `02_artifacts/00_masterlist/<STATE>/<YEAR>/errors/<date-time>_<file>_ERRORS/`: Read_me, Rules,
  Problem_count, Errors, Marked_data (the rows with problems; PROBLEMS and BAD_COLUMNS say what is wrong), Cleaned.
* Stored state-wise and year-wise in `00_database/00_masterlist/<STATE>/<YEAR>/`; the old list goes to
  `05_backup/00_masterlist/<STATE>/<YEAR>/<date-time>/` before it is replaced (last 20 kept).
* A stored list changes only when every file of that state + year passes and the result differs; a rejected file
  never changes it, and a list stays stored when its file is taken out of 01_raw_data/00_masterlist.
* `<STATE>/<YEAR>/ingested_ML.csv` = that stored list. YR = the first year (2025-26 → 2025), as RC-7 YR.

### 1. Import Schedules (`c01_importschedules.py`, `c01_importschedules_dgces.py`, `c01_dgces_rc7/`, `04_src/utils/schedule20.py`)
* `.mdb / .accdb / .zip`: `Sch20RC7` → `ingested_sch.csv` and `mdb/Sch20RC7.csv`; all Schedule 2.0 block tables
  → `mdb/Sch20Block….csv`, exactly the .mdb columns, values as text, + YR, SOURCE, SOURCE_FILE. The Exp-ID has no year in
  it (1,369 Exp-IDs are in both NSSAS2024 and NSSAS2025), so rows are kept per Exp-ID + YR; the newer file wins.
* DGCES Excel (sheets FinalNSOFieldData + FinalNSO_PW_FieldData): converted into the same block tables and Sch20RC7
  → `dgces/`. Rules: `DGCES_to_Schedule2.0_block_mapping.xlsx` (Collab_VSC folder); RC-7 codes by KrishiStat's rc7
  package (copied to `04_src/components/c01_dgces_rc7`).
  * The **sample** (Central / State) is chosen by the user (in the app, or `--sample`). Without it DGCES files are skipped.
  * **EXPTID is blank** — DGCES has no order of selection. Each row has `DGCES_KEY`
    (year|season|state LGD|district LGD|village LGD|crop|expt); `DGCES_ID.csv` keeps the LGD codes and names.
  * Codes still to be decided (irrigation source, manure, substitution reason): `config.yaml` → `DGCES_codes`.
* `clubbed/` = mdb and DGCES rows of every table together.
* `report/`: Files.csv (files read), Tables.csv (rows per table), and per DGCES file `DGCES issues <file>.csv`,
  `DGCES codes <file>.csv` (codes not in the tables), `PW vs S <file>.csv` (PW vs supervisor).
* All outputs are rebuilt from the raw files on each run (no appending), but each file's result is kept in
  `00_database/01_importschedules/file_cache/`: an unchanged file is not read again, only new / changed ones (and
  files that failed). Raise `CACHE_VERSION` in `c01_importschedules.py` when the reading code changes.
* The page shows the open state + year only: **Import log (last import)** = one line per file of the last import:
  ✓ imported (how many experiments, what was left out) or ✗ not imported and why; **Import history** = every import of the state + year, saved in
  `02_artifacts/01_importschedules/import_history.csv` (all states, appended). The full text log of every run is in
  `03_logs/`. A picked file of another state / year (read from the file) is saved there, and a message says so.

### Schedules for the modules (`04_src/utils/schedules.py`)
Every module reads the imported schedules of the open state + year only through this file (RC-7 and the block tables
of the .mdb files, keyed by EXPTID + YR; DGCES identity rows). When the store changes (received / processed folders
per state + year) only this file changes.

### 2. Control Register (`c02_controlregister_summary.py`, page `app/page_controlregister.py`)
Copy of KrishiSoft_V0.1 (old AS 2.0 control register.accdb): Planned = master list; Received = has RC-7; Harvested =
STAGIN 1 minus REJ 1; Missed STAGIN 2; Lost STAGIN 3; Harvest % = harvested × 100 / planned. Counts for the chosen
Season / Crop (work page) and Sample (header); tabs **By crop**, **By RO / SRO**, **NR (Not Received)** (lists that
only offer what still has NR, with counts) and **Received, not in master list**. Worked out when shown (no Run).
Export: CSV files; NR: office-format Excel (one file per season + crop + sample, as the office's NR files).
DGCES experiments have no Exp-ID yet: counted as "DGCES received (not linked yet)", not matched.
Without the app: `pipelines/p02_controlregister_pipeline.py` (`run_step.py 2 [STATE YEAR]`) shows the same summary
(nothing written). The page recalculates whenever it is opened, schedules are imported or corrections saved.

### 3. View Schedule (`c03_viewschedule.py`, page `app/page_viewschedule.py`, template `04_src/resources/as20.docx`)
Copy of KrishiSoft_V0.1's Print Schedules: type the Exp-ID parts (Sample, District, Sel. order, Crop code, Expt; the
state is the open one) → Search → details (found / in master list but not imported / not in master list) →
**View** (the schedule block by block in a window – Block 1 … Block 12 and RC-7, read-only, corrections included – with
**Print as PDF** at the bottom), **Add to print list**, **Print this as PDF** (the saved PDF is then shown inside the app); **Print list as PDF**; **Print all** (imported, chosen
Season / Crop; asks above 50). The Schedule 2.0 form (as20.docx, layout checked in KrishiSoft against 59 old
printouts) is filled and saved as PDF with Microsoft Word; empty fields stay blank; no editing.

### 4. Data Validation (`c04_datavalidation.py`, page `app/page_datavalidation.py`, `04_src/resources/max_yield.csv`)
Copy of KrishiSoft_V0.1's Yield Checking (= old AS 2.0 YIELD CHECKING.accdb) with a **minimum yield** added. Choose
the crop (and season) in the work page's lists and the Sample in the header; every experiment of that crop with
Block 9 (SRL 1), RC-7, Block 5 part 1 and Block 10 is listed. Checks (red cells):
* **above maximum** – net weight (yield, g) ≥ maximum yield (old `yield rc7` table, or saved here);
* **below minimum** – net weight < minimum yield (saved here), except a completely destroyed crop (condition 4);
* **Poor crop – No cause** – crop condition 3 / 4 but "affected by" 0;
* **Good crop – Affected** – crop condition 1 / 2 but "affected by" not 0;
* **rejected** – REJ 1.

Editable: plot weight, net weight, crop condition, affected by, REJ, potato sides L1 / L2; RC-7 QTYG / QTYP / CROPCON /
AFFECT follow by the old rules (WEIGHT × 1000; crops 3000 / 2400 net weight typed; crop 2000 in state 21 from L1 + L2);
RUN YIELD CONVERSION applies the rule to all rows. **SAVE** (confirmed) writes each changed value to
`00_database/04_datavalidation/<STATE>/<YEAR>/corrections.csv`; `utils/schedules.py` applies the corrections whenever
schedules are read, so every module uses the corrected value (9.5, not the 7.45 it replaced) and re-importing the
same file never undoes it; when a REVISED file brings a new value for that field, the new value is kept. Limits: `yield_limits.csv` in the same folder (old file to `05_backup/04_datavalidation/…` first).
Exports (CSV with a FLAGS column): Outliers (red rows) / Basic Data (all rows) in
`02_artifacts/04_datavalidation/<STATE>/<YEAR>/Outliers|Basic Data/<CROP>/<Central|State>/`.

### 5. Estimates (`c05_estimates.py`, `c05_estimates_report.py`, page `app/page_estimates.py`, `pipelines/p05_estimates_pipeline.py`)
Copy of the old AS 2.0 ESTIMATE.accdb (as in KrishiSoft_V0.1). Crop (and season) from the work page's lists.
**Sample**: Central, State or Combined – one at a time. **Combined** shows two choices below the counts, each
"Crop code [typed] ☐ Central ☐ State" (choice 1 starts as the crop chosen above); the estimate pools both, e.g.
1611 State + 1612 State = 1600, or 1611 Central + 1611 State.
* Plots used: every planned experiment with its RC-7 (Data Validation corrections applied) that was harvested
  (STAGIN 1) – rejected plots included, as the old tool; yield = QTYP (grams per plot).
* The tabs follow the office printout: **Area Sheet → Intermediate Table → Variance (columns 1 – 14) → (%) S.E. →
  Compiled Data → Estimate BD**.
* **Area Sheet**: one row per district with plots: area, merge dist code (a district whose plots and area this row
  takes in; 1 = leave out – the office's rule for a district with fewer than 4 expts: give it 1 and put its code in
  the merge column of the district that takes it in; such districts and left-out rows are red, on screen and in the
  workbook); click a cell and type (Enter goes down a row); conversion factor, driage ratio, recovery
  ratio, prepared by. **Calculate & save** keeps it for this selection (`00_database/05_estimates/<STATE>/<YEAR>/`,
  old copy to `05_backup/05_estimates/…`); opening the selection again shows the estimate at once. **Copy from the
  other sample** fills the Central / State one.
* **Export**: ONE Excel workbook (an exception to the CSV rule, like the NR files) with those six sheets in a plain
  style (title, state · year · season · crop · sample, the factors, then a table with proper headings, number formats,
  total row, frozen heading, A4 landscape printing) – the same tables the app shows, in `02_artifacts/05_estimates/<STATE>/<YEAR>/<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/`.
* Information accompanying, the T-test and the Confidential sheet are a later module (their code stays in
  `c05_estimates.py`).
* Checked against the office's stored estimates: Tamil Nadu 2024-25 / 2025-26 (Gaurav's ESTIMATE.accdb) 47 of 61
  identical district by district, combined ones included; Bihar 2025-26 MAIZE_HY Central 3,054 kg/ha, %SE 5.5. The
  others differ only in the plots: schedules received or imported since, weights the office changed inside the old
  estimate (such changes belong in 4. Data Validation).
* Not covered yet: Kerala's per-tree crops (arecanut, banana, coconut, pepper) and Tamil Nadu cotton pickings
  (`01_estimate_files`), which use their own methods.

### 6. Estimate Report (`c06_estimatereport.py`, `c06_estimatereport_excel.py`, page `app/page_estimatereport.py`, `pipelines/p06_estimatereport_pipeline.py`)
What goes out with an estimate saved in 5. Estimates (same Season / Crop and Central / State / Combined picker):
* **Information Accompanying** – current vs previous year: receipt of schedules (planned, analysed, % analysed,
  missed, lost, rejected, not received), distribution of the green yield per plot (no., %, cumulative %), ancillary
  information (irrigated, HY seed, fertiliser, manure, pesticides), crop condition, reasons for crop damage; ICS and
  CES yields (SE%) of the 5 previous years; due date, date of submission, ID.
* **T-test** – |Y1 − Y2| ÷ √(V1 + V2) against 1.96: current vs previous year, current vs CES.
* **Confidential Sheet** – the office's Hindi letter (state / season / crop names from the master list's Hindi
  columns): yield (SE%) this year, previous year, CES; % difference (* = significant); planned, analysed, % response.
* Previous-year figures (counts, previous yield and variance, ICS yields of earlier years) are **filled from the app**
  when that year's master list / schedules / saved estimate are in it (tinted on screen); typing over a value keeps the
  typed one. **Save** keeps the typed figures (`00_database/06_estimatereport/<STATE>/<YEAR>/report_inputs.csv`);
  **Export** writes one workbook (the three sheets) in
  `02_artifacts/06_estimatereport/<STATE>/<YEAR>/<Central|State|Combined>/<VARIETY>/<dd.mm.yyyy>/`.

### 7. RC7 (`c07_rc7.py`, page `app/page_rc7.py`, `pipelines/p07_rc7_pipeline.py`)
The crop cutting record (RC-7) of the open state + year: the old `RC7 <year>.accdb` validation (DataValidation20) and the
auto-corrections of the 06_RC_Cleaning script, for all crops (the work page's Season / Crop lists are hidden here). A line
under the title has a tick box for each season of the master list (1 to 5 or more, with its planned schedules; one at
least stays ticked) and Central / State ticks. Both lists show the season of each line.
* **Proposed corrections** – one line per kind of fix (field, now → proposed, why) per crop + sample, all ticked; untick
  what you don't want, **Apply ticked…** asks first and writes them to `00_database/04_datavalidation/<STATE>/<YEAR>/corrections.csv`
  (like Data Validation: the import stays as it is, every module uses the corrected value). Fixes: REJ 0/1, CCE 0 → 7, RSV,
  REXML (missed / lost) → 9, CFC → 4, RCSSN → 0, blank equipment codes → 9, QTYG / QTYP blank for missed and 0 for a destroyed
  crop, E13 / E14, AFFECT 0 for a good / normal crop, NIRR / IRR, CODN / CODP / CODK and N / P / K, FERTC 1 when N / P / K
  given, lost plots blanked, NEXP = planned and NEXNR = planned − received (per crop group), CONFAC = ⌊CCF × 10,000⌋ from
  5. Estimates' saved area sheet, YR = the first year.
* **Problems** – codes outside `04_src/resources/rc7_code_rules.csv` (the old 40 rules; YR now = the year), harvested
  with yield 0 (not destroyed), FERTC 1 without N / P / K, IRR 1 without irrigations, yield above the maximum (4. Data
  Validation's limits), QTYP < QTYG × 1000, order of selection > 25, conversion factor missing (one line per crop + sample),
  seed ratio above `04_src/resources/seed_ratio.csv`, harvest date not a date. Type the right value in **New value** and
  **Save typed values** (asks first); yields are fixed in 4. Data Validation (plot weight → QTYG and QTYP).
* **Mark final / Unmark final** – for the crops + samples shown (one crop at the top, or all): asks first (says how many
  corrections / problems are still open), keeps the rows as they are (`00_database/07_rc7/<STATE>/<YEAR>/final.csv`,
  `final_rows.csv`) and writes the final RC-7 file `02_artifacts/07_rc7/<STATE>/<YEAR>/final/RC7_final.csv` (for 8.
  Annexures). Final crops are locked (no corrections, no typed values) until unmarked; if their data changes afterwards
  (re-import, Data Validation) the page says so and the button becomes **Mark final again**.
* **Export**: both lists as CSV in `02_artifacts/07_rc7/<STATE>/<YEAR>/<dd.mm.yyyy>/`.

### 8. Annexures (`c08_annexures.py`, `c08_annexures_tables.py`, `c08_annexures_final.py`, `c08_annexures_excel.py`, page `app/page_annexures.py`, `pipelines/p08_annexures_pipeline.py`)
The RC-7 tables (exact copies of the old workbooks) and annexures (the office's final standard) of the report. Pick the report on the
line under the title – **Kharif report** or **Rabi report** (none picked to start with) – and press **Export**. Their seasons
come from the master list: Kharif = season codes 1 – 3 (Kharif, or Bhadai + Agahani), Rabi = the others (Rabi, or
Rabi + Summer) – one or two seasons per report. The work page's Season / Crop lists are hidden here.
* **This year**: the app's RC-7 (corrected) – rows marked final in 7. RC7 for final crops + samples, the current rows for
  the others; planned = master list.
* **Previous year**: the app's own RC-7 of that year first; only when the app does not have it, the file loaded with
  **Load previous year RC-7…** (the old `PY State Details` Excel, sheet RC-7 · rc7.dbf · CSV · .mdb / .accdb Sch20RC7). It is
  copied to `01_raw_data/08_annexures/<STATE>/<YEAR>/` and kept as `00_database/08_annexures/<STATE>/<YEAR>/previous_rc7.csv`;
  More ▸ Remove the loaded previous-year file.
* **CONFAC table** (the page's main area): one line per season + crop + sample with the CONFAC used for the yields and
  where it is from – the RC-7 (applied in 7. RC7; change it there), 5. Estimates' area sheet (⌊CCF × 10,000⌋), or typed
  here. Missing ones are red: type the value in the white cell (Enter saves it to
  `00_database/08_annexures/<STATE>/<YEAR>/confac.csv`; empty it to drop it). Yield = CONFAC × QTYP ÷ 10,000.
* **Export** asks which annexure workbooks to make – English, Hindi, Bilingual (any of them) – then writes, in
  `02_artifacts/08_annexures/<STATE>/<YEAR>/<SEASONS>/<dd.mm.yyyy>/`:
  * `1Annexures(Eng).xlsx`, `1Annexures(Hi).xlsx`, `1Annexures(Bi).xlsx` – **Annex-XIX … Annex-XXIV** (this year and last
    year, Central / State / Pooled) in the office's final standard (XVI, XVII, XVIII and XXV are typed by the office: not
    made). One or two seasons per report – see "How the annexure books are made" below.
  * `1Tables S-1.xlsx`, `1Tables S-2.xlsx` … – RC7-Y1 … Y7, Y11, Y12, Y13 of each season (S-1 = first season …), Central and
    State; `1Tables 8,9,10-Y.xlsx` – Tab 8 / 9 / 10 of every season (I, II …).
  * `csv/` – Annex XIX … XXIV and every Y-table as CSV.
  The workbooks just made are listed as links under the buttons (until another state / year is opened).
* **How the annexure books are made** (`c08_annexures_final.py`): the template is the office's own final Bilingual book
  (`04_src/resources/annex_final_Bi.xlsx`, Gujarat Kharif 2024-25, made by hand). Each sheet is written from its rows –
  heading, season row, crop / agency blocks, totals, the closing double line – with the same fonts, borders, row heights,
  two-line Hindi + English text, the cells' padding ('750  ', '( 95.5) ', '6(  2.5)') and page set-up. The headings get
  this report's state, years and season; crop names are the words all crops of the crop code's first two digits share
  (ज्वार/JOWAR for irrigated + unirrigated; धान-कार/PADDY KAR and धान-सांबा/PADDY SAMBA stay apart). XX and XXIV: a page
  holds what page 1 of the template holds, then a new page with the "Contd.." heading; pages are labelled अ-18/A-18,
  अ-19/A-19 … through the book. A second season is added in the same style: XIX a second Central / State / Pooled column
  set (one page wide), XX / XXIV a season row + crops (XXIV with each season's total), XXI / XXIII a block per season
  and year (XXIII then fitted to one page), XXII a page per season. The Hindi and English books are the Bilingual one
  with each cell keeping only its Hindi or only its English text. Numbers: the same as the engine's Annex XIX … XXIV
  (checked for Tamil Nadu and Bihar, Kharif and Rabi).
* **How the Y-table copies are made**: the old print sheets are the templates (`annex_tables_S.xlsx`,
  `annex_tables_8910.xlsx`, titles and labels in `annex_tables_cells.json`); the old calculation sheets are rebuilt in
  memory – Table-Y…(o) of each season (numbers from the app) and the Crops sheet (state, year, seasons, crops) – and
  every old formula is worked out to a value. Same titles, merged headings, column numbers, borders, fonts and page
  set-up; crop rows the season has are shown, the others hidden; no formulas or links in the files; the "Developed by"
  lines are left out.
* **Checked against the old Bihar 2024-25 workbooks**: Y-tables 8,662 cells and the rebuilt RC-7 TAnnex (Annex-19 … 24,
  ~11,000 cells) equal, except the old Excel's own slips – Y-7 second crop's % SE, Y-10 post-harvest "% with
  fertilizer", Y-13 State half pesticide counts (post-harvest plots), "YEAR:2" in S-2 titles, "0 (0)" / `#VALUE!` in empty
  crop slots. (The old `1Annexures(Hi / Bi)` files themselves still hold 2022-23 results – they were never recalculated.)
  As in the old tables a rejected plot is also counted in its stage, so "not received" can go below 0.

### Other changes
* `04_src/utils/common.py`: works without the `ensure` package (it only checked argument types).
* `requirements.txt`: + PySide6.
