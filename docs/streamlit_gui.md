# Streamlit Web Application Guide

## Overview

The Streamlit web application provides a browser-based interface for entering, managing, and distributing KPI targets. It is focused **exclusively** on data entry and target repartition, not on visualization or analytics. The web interface is ideal for collaborative or remote access scenarios, allowing multiple users to manage KPI targets from any device with a browser.

## How to Launch

1. Navigate to the project directory containing the source code (e.g., `src` or `ora`).
2. Run the application:

    ```bash
    streamlit run app_streamlit.py
    ```

3. The application will open in your web browser (usually at `http://localhost:8501`). If it does not open automatically, copy the URL from the terminal and paste it into your browser.

## Main Features and Workflow

- **Annual KPI Target Entry:** Select year and facility, enter annual targets for each KPI, and specify manual or automatic calculation for sub-KPIs.
- **Distribution Profile and Logic:** Choose a distribution profile (even, progressive, sinusoidal, event-based), set repartition logic (monthly, quarterly, weekly, daily), and enter custom period allocations or event adjustments as needed.
- **KPI Structure Management:** Manage KPI groups, subgroups, indicators, and templates. Define master/sub-KPI relationships and assign distribution weights.
- **Facility Management:** Add, edit, or remove facilities (stabilimenti) and set their visibility.
- **Data Export:** Download all entered and calculated target data as CSV, Excel, or ZIP files.

## How to Use

1. **Start the App:** Run `streamlit run app_streamlit.py` and open the provided URL.
2. **Navigate Using the Sidebar:** Select the year, facility, and navigate between management sections (target entry, KPI structure, templates, facilities, export).
3. **Enter or Edit Targets:** Fill in annual targets and select distribution options for each KPI. Use the "Save" button to persist your changes.
4. **Manage Structure:** Add or modify groups, subgroups, indicators, and templates as needed.
5. **Export Data:** Go to the export section to download your data in the desired format.
6. **Refresh as Needed:** If you make structural changes, use the refresh button or reload the page.

## Tips

- **Validation:** The app validates your input (e.g., sum of custom repartition percentages must be 100%). Error messages will be shown if there are issues.
- **Collaboration:** Multiple users can use the web interface simultaneously if hosted on a shared server.
- **Persistence:** All data is stored in local SQLite databases in the project directory.
- **Customization:** You can modify the Streamlit app code to adjust the UI, add new logic, or integrate with authentication systems.

## Notes

- The Streamlit application does **not** provide dashboards, charts, or analytics. It is strictly for data entry and target repartition.
- All data is stored locally in SQLite databases.
- For troubleshooting, check the Streamlit logs or contact the maintainer.

