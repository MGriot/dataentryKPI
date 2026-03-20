# Data Entry KPI Documentation

Welcome to the documentation for the Data Entry KPI system. This application provides a comprehensive solution for managing, distributing, and analyzing Key Performance Indicators (KPIs) across multiple facilities.

## 🚀 Quick Start

- **Desktop App (Tkinter):** `python main.py tkinter`
- **Web App (Streamlit):** `python main.py streamlit`

## 📚 Documentation Sections

### 🖥️ User Interfaces
- **[Tkinter Desktop Manual](gui_tkinter.md):** Detailed guide for the desktop application, covering target entry, hierarchy management, and advanced analysis tools.
- **[Streamlit Web Manual](gui_streamlit.md):** Guide for the web interface, focusing on remote data entry, parity features, and the new predictive analytics dashboard.

### 🛠️ Technical Reference
- **[System Architecture](architecture.md):** Overview of the codebase structure, service layers, and data flow.
- **[Database Schema](database_schema.md):** Detailed reference of the SQLite tables, relationships, and data models.
- **[Core Features & Logic](features.md):** Explanations of key algorithms including:
    - **Dynamic Target Distribution:** How annual targets are split into daily/weekly/monthly values.
    - **Formula Engine:** How "On-the-Fly" calculations and DAG-based formulas work.
    - **Multivariate Seasonality:** The predictive model for determining split weights.

## 🔑 Key Capabilities

1.  **Unified Management:** Manage KPI hierarchies (Groups > Subgroups > Indicators) centrally.
2.  **Smart Distribution:** Automatically split annual targets using profiles (Sinusoidal, Progressive, etc.) or predictive models.
3.  **Dependency Handling:** Define "Master/Sub" relationships where child KPIs automatically inherit portions of a parent target.
4.  **Flexible Calculation:** Use Python-like formulas or visual Node Editors to create calculated KPIs that update in real-time.
5.  **Multi-Platform:** Access the same data and features via a native desktop app or a responsive web interface.
