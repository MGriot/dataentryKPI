# [SPLIT-LOGIC] · Advanced Split Logic (Multivariate)

**Timestamp**: 2026-03-17 01:15 Local Time  
**Author**: Ralph  

## Why
Users need a way to distribute annual targets based on actual historical trends (e.g., last year's seasonality) rather than just mathematical presets. Multivariate analysis allows mapping external data (like sales or production volume) to KPI repartitioning logic.

## What Changed
- `src/target_management/repartition.py`:
    - Added `suggest_split_from_trend`: Core algorithm to calculate weights from a numeric series.
    - Added `get_seasonal_weights_from_df`: Integration helper to group DataFrame data by month/quarter and generate suggestions.
- `src/interfaces/streamlit_app/components/global_splits.py`:
    - **Data Upload**: Added `st.file_uploader` for CSV and XLSX files.
    - **Mapping UI**: Added selectboxes for users to manually map "Date" and "Value" columns from their uploaded data.
    - **Trend Analysis**: Integrated the suggestion engine to show a JSON preview of the calculated weights.
    - **Workflow**: Provided an "Analyze" and "Apply" flow to facilitate data-driven template creation.

## Verification
**Command**: Manual UI verification with a sample CSV.
**Result**: PASSED ✅
**Observation**: Uploading a CSV with 'Date' and 'Sales' columns correctly groups data by month and suggests percentages that total 100%. Suggestions are displayed in a clear JSON format for the user.
