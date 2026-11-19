"""
Streamlit Web User Interface for NSO Crop Yield & %SE Estimation.
"""
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.conversion_factors import ConversionFactors
from loaders.access_loader import AccessDataLoader
from loaders.tabular_loader import TabularDataLoader
from loaders.mock_loader import MockDataLoader
from pipeline import NSOEstimatePipeline

st.set_page_config(
    page_title="NSO Crop Estimation Engine",
    page_icon="🌾",
    layout="wide"
)

st.title("🌾 NSO Crop Yield & %SE Estimation Dashboard")
st.caption("Improvement of Crop Statistics (ICS) Scheme • National Statistical Office (NSO), India")

# Sidebar
st.sidebar.header("1. Data Source Selection")
source_type = st.sidebar.radio(
    "Data Source Mode",
    ["Access Database (.accdb / .mdb)", "Upload CSV / Excel", "Demo Mock Generator"],
    index=0
)

db_path = None
uploaded_file = None
uploaded_areas = None

if source_type == "Access Database (.accdb / .mdb)":
    default_accdb = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "01_Estimate_Workflow_in_mdb", "ASSOFTWARE", "ESTIMATE.accdb"
    ))
    db_path = st.sidebar.text_input("Database File Path", value=default_accdb if os.path.exists(default_accdb) else "")
    table_name = st.sidebar.text_input("Experiments Table Name", value="total estimate")
elif source_type == "Upload CSV / Excel":
    uploaded_file = st.sidebar.file_uploader("Upload Experiments File (.csv, .xlsx)", type=["csv", "xlsx", "xls"])
    uploaded_areas = st.sidebar.file_uploader("Upload District Areas File (Optional)", type=["csv", "xlsx", "xls"])

st.sidebar.header("2. Conversion Factors")
col_d, col_r = st.sidebar.columns(2)
with col_d:
    driage = st.number_input("Driage Ratio (d)", min_value=0.0, max_value=1.0, value=0.7502, step=0.0001, format="%.4f")
with col_r:
    recovery = st.number_input("Recovery Ratio (r)", min_value=0.0, max_value=1.0, value=1.0000, step=0.0001, format="%.4f")

cf = st.sidebar.number_input("Plot Conversion Factor (f)", min_value=0.0, max_value=10.0, value=0.4000, step=0.0001, format="%.4f")
ccf = driage * recovery * cf
st.sidebar.info(f"**Composite Factor (CCF):** `{ccf:.5f}`")

st.sidebar.header("3. Survey Criteria Filters")
conv_type = st.sidebar.selectbox("Conversion Mode", [1, 2], format_func=lambda x: "1 - Specific Sample" if x == 1 else "2 - Combined Sample")
sample_code = st.sidebar.selectbox("Sample Type", ["", "1 (Central)", "2 (State)"])
sample_filter = sample_code[0] if sample_code else None

state_code = st.sidebar.text_input("State Code (Optional)", value="")
crop_code = st.sidebar.text_input("Crop Code (Optional)", value="")
season_code = st.sidebar.text_input("Season Code (Optional)", value="")

# Execution
if st.sidebar.button("▶ Calculate Yield & %SE", type="primary", use_container_width=True):
    try:
        factors = ConversionFactors(driage_ratio=driage, recovery_ratio=recovery, conversion_factor=cf)

        if source_type == "Demo Mock Generator":
            loader = MockDataLoader()
        elif source_type == "Access Database (.accdb / .mdb)":
            if not os.path.exists(db_path):
                st.error(f"Access database not found at: {db_path}")
                st.stop()
            loader = AccessDataLoader(db_path=db_path, table_name=table_name)
        else:
            if not uploaded_file:
                st.warning("Please upload an experiments data file.")
                st.stop()
            df_exp = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(uploaded_file)
            df_area = None
            if uploaded_areas:
                df_area = pd.read_excel(uploaded_areas) if uploaded_areas.name.endswith(('.xlsx', '.xls')) else pd.read_csv(uploaded_areas)
            loader = TabularDataLoader(experiments_source=df_exp, areas_source=df_area)

        with st.spinner("Processing NSO estimation pipeline..."):
            pipeline = NSOEstimatePipeline(loader=loader, conversion_factors=factors)
            result = pipeline.run(
                state_code=state_code.strip() or None,
                crop_code=crop_code.strip() or None,
                season_code=season_code.strip() or None,
                sample_type=sample_filter,
                conversion_type=conv_type
            )
            df_districts = pipeline.to_district_dataframe()

        # Display High-Level KPIs
        st.subheader("State-Level Summary Results")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("State Estimated Dry Yield", f"{result.state_dry_yield:,.0f} Kg/ha")
        kpi2.metric("Standard Error (SE)", f"{result.standard_error:,.2f} Kg/ha")
        
        # Color indicator based on precision
        pct_color = "normal" if result.percentage_se <= 10.0 else "inverse"
        kpi3.metric("Percentage SE (%SE)", f"{result.percentage_se:.1f} %")
        kpi4.metric("Total Experiments Analysed", f"{result.total_experiments:,}", f"{result.total_villages} Villages")

        # Tabs for details
        tab1, tab2, tab3 = st.tabs(["📊 District Breakdown Table", "📋 Official Report View", "📐 ANOVA Variance Details"])

        with tab1:
            st.dataframe(df_districts, use_container_width=True)
            csv_data = df_districts.to_csv(index=False).encode('utf-8')
            st.download_button("⬇ Download District Breakdown CSV", data=csv_data, file_name="nso_district_yield_estimate.csv", mime="text/csv")

        with tab2:
            report_str = f"""========================================================================================
  GOVERNMENT OF INDIA  •  NATIONAL STATISTICAL OFFICE (NSO)
  IMPROVEMENT OF CROP STATISTICS (ICS) SCHEME
  ESTIMATE OF CROP YIELD RATE AND STANDARD ERROR
========================================================================================
  State:    {result.state_name} (Code: {result.state_code})
  Crop:     {result.crop_name} (Code: {result.crop_code})
  Season:   {result.season_name}
  Sample:   {result.sample_name}
  Year:     {result.year}
----------------------------------------------------------------------------------------
  Total Area Sown (Hectares):          {result.total_area:,.2f}
  Total Sampled Villages (FSU):        {result.total_villages}
  Total Crop Cutting Experiments:      {result.total_experiments}
  Average Composite Conversion Factor: {result.avg_ccf:.5f}
----------------------------------------------------------------------------------------
  ★ ESTIMATED STATE DRY YIELD:         {result.state_dry_yield:,.0f} Kg / hectare
  ★ DRY YIELD VARIANCE:                {result.dry_yield_variance:,.0f}
  ★ STANDARD ERROR (SE):               {result.standard_error:,.2f} Kg / hectare
  ★ PERCENTAGE STANDARD ERROR (%SE):   {result.percentage_se:.1f} %
========================================================================================
"""
            st.code(report_str, language="text")

        with tab3:
            st.markdown(f"""
            - **Between-Village Mean Square ($Text0$):** `{result.between_village_ms:,.2f}`
            - **Within-Village Mean Square ($Text1$):** `{result.within_village_ms}`
            - **Mean Square Difference ($Text2$):** `{result.ms_difference}`
            - **Green Yield Variance ($Text3$):** `{result.green_yield_variance:,.2f}`
            - **Dry Yield Variance ($Text4$):** `{result.dry_yield_variance:,.2f}`
            """)

    except Exception as e:
        st.error(f"Error during calculation: {e}")
else:
    st.info("👈 Set your parameters in the left sidebar and click **Calculate Yield & %SE** to start.")
