"""Module folder names, the same under every top folder (00_database, 01_raw_data, 02_artifacts, 05_backup):
<top>/<NN_module>/… with the numbers and names of the app's modules. 00 = the master list (States page, once a
year); 1 – 8 = the modules in the work page's left list."""

MASTER_LIST = "00_masterlist"
IMPORT_SCHEDULES = "01_importschedules"
CONTROL_REGISTER = "02_controlregister"
VIEW_SCHEDULE = "03_viewschedule"
DATA_VALIDATION = "04_datavalidation"
ESTIMATES = "05_estimates"
ESTIMATE_REPORT = "06_estimatereport"
RC7 = "07_rc7"
ANNEXURES = "08_annexures"

MODULES = [MASTER_LIST, IMPORT_SCHEDULES, CONTROL_REGISTER, VIEW_SCHEDULE, DATA_VALIDATION, ESTIMATES, ESTIMATE_REPORT,
           RC7, ANNEXURES]
