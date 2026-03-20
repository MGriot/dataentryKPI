# Tkinter Desktop Interface Manual

The desktop interface provides a high-performance, native environment for managing large datasets and complex KPI structures. It uses a Tabbed interface (`ttk.Notebook`) to organize workflows.

## 🎯 Target Entry Tab

The primary workspace for data entry.

### 1. Filters & Navigation
- **Year/Plant Selection**: Select the context from the top toolbar. Changing these filters triggers a full reload of the KPI tree.
- **Hierarchy Tree**: The sidebar displays a nested tree of KPI Groups > Subgroups > Indicators.
- **Search**: Use the "🔍" bar to filter the tree and the visible entry cards.

### 2. KPI Cards
Each visible KPI is rendered as a "Card" containing:
- **Target Inputs**: Fields for `Target 1` and `Target 2`.
- **History**: Small blue labels showing values from `Y-1` and `Y-2` for context.
- **Manual Override**: A checkbox (labeled "M") allows you to break a "Master/Sub" link and enter a value manually.
- **Formula Indicator**: Calculated KPIs have a distinct visual style and locked input fields (unless "Override" is checked).

### 3. Actions
- **Save All Changes**: Commits all modified targets to the database. This triggers a background thread to calculate formulas and distribute daily values.
- **Apply to All Plants**: A checkbox to broadcast the current values to every active facility.

## 🗂️ KPI Management Tab

A comprehensive "Control Panel" split into four sub-tabs:

### 1. 📁 KPI Explorer
- **Tree View**: Manage the folder structure. Right-click or use toolbar buttons to add Groups, Folders, or KPIs.
- **Inspector**: Selecting a node shows its properties on the right panel.
- **Visual Formula Editor**: For calculated KPIs, clicking "🛠️ Open Visual Editor" launches a node-based graph editor to visually design dependencies.

### 2. 📋 Templates
Create reusable KPI "prototypes". Indicators added here can be instantiated in bulk across multiple subgroups.

### 3. ✂️ Global Splits
Manage seasonal distribution profiles.
- **Predictor**: Use the "Multivariate Seasonality Predictor" (if available) to upload historical CSVs and generate weight curves automatically.

### 4. 🔗 Master/Sub Links
Define parent-child relationships.
- **Weighting**: Assign percentage weights (0.0 - 1.0) to determine how a Master's target is distributed to its children.

## 📈 Analysis Tab

### 1. Single KPI Focus
- Select a specific KPI to view its performance over time.
- **Chart**: A matplotlib line chart showing the trend.
- **Table**: A detailed data grid with columns for Year, Period, and Targets.

### 2. Global Overview
- Generates a "Dashboard" view with small sparkline charts for all KPIs, allowing a quick health check of the entire system.

## 🏭 Plants & Settings

- **Plant Management**: Add/Edit facilities. Assign brand colors which are reflected in the Analysis charts.
- **Data Management**: Backup the entire system state to a ZIP file or restore from a previous archive.
