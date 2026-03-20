# Streamlit Web Interface Manual

The Streamlit interface offers a modern, browser-based experience for data entry and analysis. It is designed for ease of access and parity with the desktop application's core features.

## 🧭 Navigation

The application uses a categorized sidebar menu:
- **🎯 Operation**: Daily tasks like Target Entry.
- **📁 KPI Management**: Structural admin tasks.
- **🏭 Configuration**: Plant and System settings.
- **📊 Data & Analysis**: Reporting and Exports.

## 🎯 Target Entry Page

A streamlined interface for rapid data input.

### 1. Context Selection
- **Top Bar**: Select the **Year** and **Plant** from the dropdowns. This context persists across the session.
- **Quick Find Sidebar**: A dedicated search bar filtering the list of KPIs. Clicking a KPI button instantly scrolls it into view.

### 2. Entry Interface
KPIs are displayed in expandable blocks.
- **Inputs**: Number fields for `Target 1` and `Target 2`.
- **History Tooltips**: Hover or view small text to see `Y-1` / `Y-2` values.
- **Logic Toggles**:
    - **Formula**: Check to enable formula calculation.
    - **Manual**: Check to override a parent's distribution.
- **Distribution Settings**: Select the `Profile` (e.g., Even, Progressive) and `Logic` (Month, Quarter) directly on the card.

## 📁 KPI Management Explorer

An advanced hierarchical browser.

### 1. Recursive Tree
The sidebar features a "Russian Doll" nested expander system.
- Drill down through **Groups > Subgroups > Folders**.
- Each level is visually distinct.
- Click "👁️ View Details" on any node to manage it in the main area.

### 2. Property Sheet
When a KPI or Node is selected, the main area becomes a property editor.
- **Specifications**: Edit Unit, Calculation Type, and Visibility.
- **Formula Insight**: View the raw formula string or a JSON representation of the logic DAG.
- **Plant Visibility**: A grid of checkboxes to toggle the KPI's availability per facility.

## ✂️ Global Splits & Predictor

### 1. Template Management
Create and Edit seasonal distribution templates.

### 2. 🚀 Multivariate Seasonality Predictor
A powerful ML-driven tool integrated into the creation/edit workflow.
1. **Upload**: Drag & drop a CSV/Excel file with historical data.
2. **Configure**: Select the "Target" columns (history) and "Driver" columns (weather, production, etc.).
3. **Analyze**: The system trains an OLS regression model.
4. **Visualize**: A Plotly chart displays the fit between Actuals, Drivers, and the Prediction.
5. **Apply**: One-click application of the predicted weights to your split template.

## 📈 Analysis & Results

### 1. Chronological Timeline
The dashboard uses a sequential X-axis logic.
- **Multi-Year Support**: Selecting multiple years (e.g., 2024, 2025) plots them consecutively on a single timeline, rather than overlapping them.
- **Zoom/Pan**: Interactive Plotly charts allow deep inspection of specific periods.

### 2. Global Comparison
- Compare the same KPI across multiple plants or against different target versions (T1 vs T2) on a unified graph.
