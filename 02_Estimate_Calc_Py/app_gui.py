"""
Native Windows Desktop GUI for NSO Crop Yield & Standard Error Estimation.
Built with Python's native tkinter and ttk.
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import pandas as pd

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversion_factors import ConversionFactors
from loaders.access_loader import AccessDataLoader
from loaders.tabular_loader import TabularDataLoader
from loaders.mock_loader import MockDataLoader
from pipeline import NSOEstimatePipeline


class NSOEstimateApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NSO Crop Yield & %SE Estimation Engine (ICS Scheme)")
        self.geometry("1180x760")
        self.minsize(980, 640)

        # Apply system theme if available
        self.style = ttk.Style(self)
        available_themes = self.style.theme_names()
        if 'vista' in available_themes:
            self.style.theme_use('vista')
        elif 'clam' in available_themes:
            self.style.theme_use('clam')

        self.pipeline: NSOEstimatePipeline = None
        self.current_result = None

        self._init_variables()
        self._build_ui()
        self._on_source_type_changed()
        self._update_ccf_readout()

    def _init_variables(self):
        # Data source
        self.var_source_type = tk.StringVar(value="accdb")
        self.var_file_path = tk.StringVar(value="")
        self.var_areas_path = tk.StringVar(value="")
        self.var_table_name = tk.StringVar(value="total estimate")

        # Set default path to workspace accdb if exists
        default_accdb = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "01_Estimate_Workflow_in_mdb", "ASSOFTWARE", "ESTIMATE.accdb"
        ))
        if os.path.exists(default_accdb):
            self.var_file_path.set(default_accdb)

        # Conversion factors
        self.var_driage = tk.DoubleVar(value=0.7502)
        self.var_recovery = tk.DoubleVar(value=1.0000)
        self.var_cf = tk.DoubleVar(value=0.4000)
        self.var_ccf_text = tk.StringVar(value="CCF: 0.30008")

        # Filters
        self.var_state = tk.StringVar(value="")
        self.var_crop = tk.StringVar(value="")
        self.var_season = tk.StringVar(value="")
        self.var_sample = tk.StringVar(value="2")
        self.var_conv_type = tk.IntVar(value=1)

        # Status
        self.var_status = tk.StringVar(value="Ready. Select data source and click 'Run Estimation'.")

        # Traces
        self.var_driage.trace_add("write", lambda *args: self._update_ccf_readout())
        self.var_recovery.trace_add("write", lambda *args: self._update_ccf_readout())
        self.var_cf.trace_add("write", lambda *args: self._update_ccf_readout())

    def _update_ccf_readout(self):
        try:
            d = float(self.var_driage.get() or 0.0)
            r = float(self.var_recovery.get() or 0.0)
            f = float(self.var_cf.get() or 0.0)
            ccf = d * r * f
            self.var_ccf_text.set(f"CCF = d × r × f = {ccf:.5f}")
        except Exception:
            self.var_ccf_text.set("CCF: Invalid input")

    def _build_ui(self):
        # Main layout: Header at top, split pane (left controls, right results), status at bottom
        header = tk.Frame(self, bg="#1a365d", height=54)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="Government of India  •  National Statistical Office (NSO)\nCrop Yield Rate (Kg/ha) & Standard Error (%SE) Engine",
            fg="white",
            bg="#1a365d",
            font=("Segoe UI", 12, "bold"),
            justify=tk.LEFT,
            padx=16,
            pady=6
        )
        title_lbl.pack(side=tk.LEFT)

        # Status Bar
        status_bar = tk.Frame(self, relief=tk.SUNKEN, bd=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar, textvariable=self.var_status, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8, pady=3)

        # Content Split Container
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left control frame
        left_frame = ttk.Frame(paned, width=380)
        paned.add(left_frame, weight=0)

        # Right results frame
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        self._build_controls(left_frame)
        self._build_results_view(right_frame)

    def _build_controls(self, parent):
        # 1. Data Source Section
        sec_source = ttk.LabelFrame(parent, text=" 1. Data Source ", padding=8)
        sec_source.pack(fill=tk.X, pady=(0, 6))

        rb_frame = ttk.Frame(sec_source)
        rb_frame.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(rb_frame, text="Access DB", variable=self.var_source_type, value="accdb", command=self._on_source_type_changed).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(rb_frame, text="CSV/Excel", variable=self.var_source_type, value="tabular", command=self._on_source_type_changed).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(rb_frame, text="Demo Mock", variable=self.var_source_type, value="mock", command=self._on_source_type_changed).pack(side=tk.LEFT, padx=4)

        # File browse row
        self.lbl_file = ttk.Label(sec_source, text="Database File:")
        self.lbl_file.pack(anchor=tk.W, pady=(4, 1))

        f_row = ttk.Frame(sec_source)
        f_row.pack(fill=tk.X, pady=2)
        self.entry_file = ttk.Entry(f_row, textvariable=self.var_file_path, font=("Segoe UI", 9))
        self.entry_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.btn_browse = ttk.Button(f_row, text="Browse...", width=9, command=self._browse_file)
        self.btn_browse.pack(side=tk.RIGHT)

        # Table name row (for Access)
        self.f_table = ttk.Frame(sec_source)
        self.f_table.pack(fill=tk.X, pady=2)
        ttk.Label(self.f_table, text="Table:").pack(side=tk.LEFT)
        ttk.Entry(self.f_table, textvariable=self.var_table_name, width=18).pack(side=tk.LEFT, padx=4)

        # Areas file row (for CSV mode)
        self.f_areas = ttk.Frame(sec_source)
        ttk.Label(self.f_areas, text="Areas CSV (Opt):").pack(anchor=tk.W, pady=(4, 1))
        f_areas_row = ttk.Frame(self.f_areas)
        f_areas_row.pack(fill=tk.X)
        ttk.Entry(f_areas_row, textvariable=self.var_areas_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(f_areas_row, text="Browse...", width=9, command=self._browse_areas).pack(side=tk.RIGHT)

        # 2. Conversion Factors
        sec_factors = ttk.LabelFrame(parent, text=" 2. Conversion Factors ", padding=8)
        sec_factors.pack(fill=tk.X, pady=6)

        grid_f = ttk.Frame(sec_factors)
        grid_f.pack(fill=tk.X)

        ttk.Label(grid_f, text="Driage Ratio (d):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_f, textvariable=self.var_driage, width=12).grid(row=0, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_f, text="Recovery Ratio (r):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_f, textvariable=self.var_recovery, width=12).grid(row=1, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_f, text="Conversion Factor (f):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_f, textvariable=self.var_cf, width=12).grid(row=2, column=1, sticky=tk.E, pady=2)

        lbl_ccf = ttk.Label(sec_factors, textvariable=self.var_ccf_text, font=("Segoe UI", 9, "bold"), foreground="#2b6cb0")
        lbl_ccf.pack(anchor=tk.W, pady=(6, 2))

        # 3. Filter Parameters
        sec_filters = ttk.LabelFrame(parent, text=" 3. Survey Filters (Optional) ", padding=8)
        sec_filters.pack(fill=tk.X, pady=6)

        grid_flt = ttk.Frame(sec_filters)
        grid_flt.pack(fill=tk.X)

        ttk.Label(grid_flt, text="Mode:").grid(row=0, column=0, sticky=tk.W, pady=2)
        conv_cb = ttk.Combobox(grid_flt, textvariable=self.var_conv_type, values=[1, 2], width=10, state="readonly")
        conv_cb.grid(row=0, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_flt, text="Sample:").grid(row=1, column=0, sticky=tk.W, pady=2)
        sample_cb = ttk.Combobox(grid_flt, textvariable=self.var_sample, values=["", "1", "2"], width=10)
        sample_cb.grid(row=1, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_flt, text="State Code:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_flt, textvariable=self.var_state, width=12).grid(row=2, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_flt, text="Crop Code:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_flt, textvariable=self.var_crop, width=12).grid(row=3, column=1, sticky=tk.E, pady=2)

        ttk.Label(grid_flt, text="Season Code:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(grid_flt, textvariable=self.var_season, width=12).grid(row=4, column=1, sticky=tk.E, pady=2)

        # 4. Actions
        sec_actions = ttk.Frame(parent, padding=4)
        sec_actions.pack(fill=tk.X, pady=8)

        self.btn_run = tk.Button(
            sec_actions,
            text="▶  Calculate Yield & %SE",
            bg="#2b6cb0",
            fg="white",
            activebackground="#2c5282",
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._on_run_clicked
        )
        self.btn_run.pack(fill=tk.X, pady=(0, 6))

        exp_row = ttk.Frame(sec_actions)
        exp_row.pack(fill=tk.X)
        self.btn_export_csv = ttk.Button(exp_row, text="💾 Export CSV", state=tk.DISABLED, command=self._export_csv)
        self.btn_export_csv.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.btn_export_json = ttk.Button(exp_row, text="💾 Export JSON", state=tk.DISABLED, command=self._export_json)
        self.btn_export_json.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

    def _build_results_view(self, parent):
        # Top KPI Metric Cards
        cards_container = ttk.Frame(parent)
        cards_container.pack(fill=tk.X, pady=(0, 8))

        self.card_yield = self._create_kpi_card(cards_container, "STATE DRY YIELD", "-- Kg/ha", "#2b6cb0")
        self.card_yield.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        self.card_se = self._create_kpi_card(cards_container, "STANDARD ERROR (SE)", "-- Kg/ha", "#4a5568")
        self.card_se.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        self.card_pct_se = self._create_kpi_card(cards_container, "PERCENTAGE SE (%SE)", "-- %", "#2f855a")
        self.card_pct_se.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        self.card_samples = self._create_kpi_card(cards_container, "TOTAL EXPERIMENTS", "--", "#744210")
        self.card_samples.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # Tabbed Notebook for Tables & Reports
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: District Table
        tab_districts = ttk.Frame(self.notebook)
        self.notebook.add(tab_districts, text="  District Breakdown Table  ")
        self._build_treeview(tab_districts)

        # Tab 2: Official NSO Report View
        tab_report = ttk.Frame(self.notebook)
        self.notebook.add(tab_report, text="  Official NSO Summary Report  ")
        self._build_report_view(tab_report)

        # Tab 3: ANOVA Variance Components
        tab_anova = ttk.Frame(self.notebook)
        self.notebook.add(tab_anova, text="  ANOVA Variance Analysis  ")
        self._build_anova_view(tab_anova)

    def _create_kpi_card(self, parent, title, default_val, accent_color):
        card = tk.Frame(parent, bg="white", relief=tk.SOLID, bd=1, padx=8, pady=8)
        lbl_title = tk.Label(card, text=title, font=("Segoe UI", 8, "bold"), fg="#718096", bg="white")
        lbl_title.pack(anchor=tk.W)
        lbl_val = tk.Label(card, text=default_val, font=("Segoe UI", 16, "bold"), fg=accent_color, bg="white")
        lbl_val.pack(anchor=tk.W, pady=(2, 0))
        card.lbl_val = lbl_val
        return card

    def _build_treeview(self, parent):
        # Columns matching ESTIMATE.accdb intermediate & final table
        self.cols = (
            ("district_code", "Code", 50),
            ("district_name", "District Name", 130),
            ("village", "Villages (m)", 80),
            ("expt", "Expt (n)", 70),
            ("netweight", "Net Weight (g)", 100),
            ("area", "Area (ha)", 80),
            ("ccf", "CCF", 75),
            ("agreenyield", "Green Yield", 90),
            ("dryyield", "Dry Yield (Kg/ha)", 110),
            ("avy*area", "Yield × Area", 100),
            ("i", "i-Ratio", 65),
            ("col11", "Col11", 90),
            ("col12", "Col12", 90)
        )
        col_ids = [c[0] for c in self.cols]

        f_tree = ttk.Frame(parent)
        f_tree.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(f_tree, columns=col_ids, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(f_tree, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(f_tree, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for cid, label, width in self.cols:
            self.tree.heading(cid, text=label, anchor=tk.CENTER)
            self.tree.column(cid, width=width, anchor=tk.CENTER)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        f_tree.rowconfigure(0, weight=1)
        f_tree.columnconfigure(0, weight=1)

    def _build_report_view(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.txt_report = tk.Text(
            f,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#f7fafc",
            fg="#2d3748",
            padx=12,
            pady=12,
            relief=tk.SOLID,
            bd=1
        )
        vsb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self.txt_report.yview)
        hsb = ttk.Scrollbar(f, orient=tk.HORIZONTAL, command=self.txt_report.xview)
        self.txt_report.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.txt_report.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

    def _build_anova_view(self, parent):
        f = ttk.Frame(parent, padding=12)
        f.pack(fill=tk.BOTH, expand=True)

        self.txt_anova = tk.Text(
            f,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#1a202c",
            padx=16,
            pady=16,
            relief=tk.SOLID,
            bd=1
        )
        self.txt_anova.pack(fill=tk.BOTH, expand=True)

    def _on_source_type_changed(self):
        st = self.var_source_type.get()
        if st == "accdb":
            self.lbl_file.configure(text="Access Database File (.accdb / .mdb):")
            self.entry_file.configure(state=tk.NORMAL)
            self.btn_browse.configure(state=tk.NORMAL)
            self.f_table.pack(fill=tk.X, pady=2)
            self.f_areas.pack_forget()
        elif st == "tabular":
            self.lbl_file.configure(text="Experiments CSV / Excel File:")
            self.entry_file.configure(state=tk.NORMAL)
            self.btn_browse.configure(state=tk.NORMAL)
            self.f_table.pack_forget()
            self.f_areas.pack(fill=tk.X, pady=2)
        else: # mock
            self.lbl_file.configure(text="Mock Generator Mode (No file needed):")
            self.entry_file.configure(state=tk.DISABLED)
            self.btn_browse.configure(state=tk.DISABLED)
            self.f_table.pack_forget()
            self.f_areas.pack_forget()

    def _browse_file(self):
        st = self.var_source_type.get()
        if st == "accdb":
            fn = filedialog.askopenfilename(
                title="Select Access Database",
                filetypes=[("Access Database", "*.accdb;*.mdb"), ("All Files", "*.*")]
            )
        else:
            fn = filedialog.askopenfilename(
                title="Select Experiments Data File",
                filetypes=[("CSV and Excel", "*.csv;*.xlsx;*.xls"), ("CSV Files", "*.csv"), ("Excel Files", "*.xlsx;*.xls")]
            )
        if fn:
            self.var_file_path.set(fn)

    def _browse_areas(self):
        fn = filedialog.askopenfilename(
            title="Select District Areas File",
            filetypes=[("CSV and Excel", "*.csv;*.xlsx;*.xls"), ("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if fn:
            self.var_areas_path.set(fn)

    def _on_run_clicked(self):
        self.btn_run.configure(state=tk.DISABLED, text="⏳ Calculating...")
        self.var_status.set("Processing crop estimation calculations...")
        threading.Thread(target=self._run_calculation_thread, daemon=True).start()

    def _run_calculation_thread(self):
        try:
            factors = ConversionFactors(
                driage_ratio=float(self.var_driage.get()),
                recovery_ratio=float(self.var_recovery.get()),
                conversion_factor=float(self.var_cf.get())
            )

            st = self.var_source_type.get()
            if st == "mock":
                loader = MockDataLoader()
            elif st == "accdb":
                path = self.var_file_path.get().strip()
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Database file not found: {path}")
                loader = AccessDataLoader(db_path=path, table_name=self.var_table_name.get().strip())
            else:
                path = self.var_file_path.get().strip()
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Data file not found: {path}")
                areas_p = self.var_areas_path.get().strip() or None
                loader = TabularDataLoader(experiments_source=path, areas_source=areas_p)

            self.pipeline = NSOEstimatePipeline(loader=loader, conversion_factors=factors)
            self.current_result = self.pipeline.run(
                state_code=self.var_state.get().strip() or None,
                crop_code=self.var_crop.get().strip() or None,
                season_code=self.var_season.get().strip() or None,
                sample_type=self.var_sample.get().strip() or None,
                conversion_type=int(self.var_conv_type.get())
            )

            # Schedule UI update on main thread
            self.after(0, self._display_results)
        except Exception as e:
            self.after(0, lambda err=e: self._show_error(err))

    def _show_error(self, error):
        self.btn_run.configure(state=tk.NORMAL, text="▶  Calculate Yield & %SE")
        self.var_status.set(f"Error: {error}")
        messagebox.showerror("Calculation Error", str(error))

    def _display_results(self):
        self.btn_run.configure(state=tk.NORMAL, text="▶  Calculate Yield & %SE")
        self.btn_export_csv.configure(state=tk.NORMAL)
        self.btn_export_json.configure(state=tk.NORMAL)

        res = self.current_result

        # Update KPI cards
        self.card_yield.lbl_val.configure(text=f"{res.state_dry_yield:,.0f} Kg/ha")
        self.card_se.lbl_val.configure(text=f"{res.standard_error:,.2f} Kg/ha")

        # Color-code %SE card (Green if < 10%, Amber if 10-15%, Red if > 15%)
        pct_color = "#2f855a" if res.percentage_se < 10.0 else ("#c05621" if res.percentage_se <= 15.0 else "#c53030")
        self.card_pct_se.lbl_val.configure(text=f"{res.percentage_se:.1f} %", fg=pct_color)
        self.card_samples.lbl_val.configure(text=f"{res.total_experiments:,} ({res.total_villages} vil)")

        # Populate Treeview
        for row in self.tree.get_children():
            self.tree.delete(row)

        df = self.pipeline.to_district_dataframe()
        for idx, r in df.iterrows():
            vals = [
                r['district_code'],
                r['district_name'],
                f"{r['village']}",
                f"{r['expt']}",
                f"{r['netweight']:,.0f}",
                f"{r['area']:,.1f}",
                f"{r['ccf']:.4f}",
                f"{r['agreenyield']:,.0f}",
                f"{r['dryyield']:,.0f}",
                f"{r['avy*area']:,.0f}",
                f"{r['i']:.2f}",
                f"{r['col11']:,.0f}",
                f"{r['col12']:,.0f}"
            ]
            self.tree.insert("", tk.END, values=vals)

        # Populate Official Report View
        report_text = f"""========================================================================================
  GOVERNMENT OF INDIA  •  NATIONAL STATISTICAL OFFICE (NSO)
  IMPROVEMENT OF CROP STATISTICS (ICS) SCHEME
  ESTIMATE OF CROP YIELD RATE AND STANDARD ERROR
========================================================================================
  State:    {res.state_name} (Code: {res.state_code})
  Crop:     {res.crop_name} (Code: {res.crop_code})
  Season:   {res.season_name}
  Sample:   {res.sample_name}
  Year:     {res.year}
----------------------------------------------------------------------------------------
  Total Area Sown (Hectares):          {res.total_area:,.2f}
  Total Sampled Villages (FSU):        {res.total_villages}
  Total Crop Cutting Experiments:      {res.total_experiments}
  Average Composite Conversion Factor: {res.avg_ccf:.5f}
----------------------------------------------------------------------------------------
  ★ ESTIMATED STATE DRY YIELD:         {res.state_dry_yield:,.0f} Kg / hectare
  ★ DRY YIELD VARIANCE:                {res.dry_yield_variance:,.0f}
  ★ STANDARD ERROR (SE):               {res.standard_error:,.2f} Kg / hectare
  ★ PERCENTAGE STANDARD ERROR (%SE):   {res.percentage_se:.1f} %
========================================================================================
"""
        self.txt_report.delete("1.0", tk.END)
        self.txt_report.insert("1.0", report_text)

        # Populate ANOVA tab
        anova_text = f"""========================================================================================
  STATISTICAL ANALYSIS OF VARIANCE (ANOVA) & SAMPLING DESIGN COMPONENTS
========================================================================================

1. DESIGN PARAMETERS (Two-Stage Stratified Cluster Sampling):
   • Primary Sampling Unit (FSU): Villages (Selection Orders)
   • Second Stage Unit:           Crop Cutting Experiments (CCE)
   • Total Villages Sampled (m):  {res.total_villages}
   • Total Experiments (n):       {res.total_experiments}
   • Sum Degrees of Freedom (m-1):{sum(d.mi_minus_1 for d in res.district_estimates.values())}
   • Sum DF within Village (n-m): {sum(d.ni_minus_mi for d in res.district_estimates.values())}

2. VARIANCE COMPONENTS (MS Access Report '%se' Equivalents):
   • Between-Village Mean Square (Text0):  {res.between_village_ms:,.2f}
   • Within-Village Mean Square (Text1):   {res.within_village_ms}
   • Mean Square Difference (Text2):       {res.ms_difference}
   • Green Yield Variance (Text3):         {res.green_yield_variance:,.2f}
   • Dry Yield Variance (Text4):           {res.dry_yield_variance:,.2f}

3. PRECISION & RELIABILITY CRITERIA:
   • Estimated Yield:                      {res.state_dry_yield:,.0f} Kg/ha
   • Standard Error:                       {res.standard_error:,.2f} Kg/ha
   • Precision (%SE):                      {res.percentage_se:.1f} %
   • Status Assessment:                    {'HIGH PRECISION (<10% SE)' if res.percentage_se < 10 else ('ACCEPTABLE PRECISION (10-15% SE)' if res.percentage_se <= 15 else 'HIGH VARIABILITY (>15% SE)')}
========================================================================================
"""
        self.txt_anova.delete("1.0", tk.END)
        self.txt_anova.insert("1.0", anova_text)

        self.var_status.set(f"Completed! State Dry Yield: {res.state_dry_yield:,.0f} Kg/ha | %SE: {res.percentage_se:.1f}% across {len(df)} districts.")

    def _export_csv(self):
        if not self.pipeline:
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export District Breakdown CSV"
        )
        if fn:
            self.pipeline.export_csv(fn)
            messagebox.showinfo("Export Successful", f"District breakdown exported to:\n{fn}")

    def _export_json(self):
        if not self.pipeline:
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Export State Summary JSON"
        )
        if fn:
            self.pipeline.export_json(fn)
            messagebox.showinfo("Export Successful", f"State summary exported to:\n{fn}")


def main():
    app = NSOEstimateApp()
    app.mainloop()

if __name__ == "__main__":
    main()
