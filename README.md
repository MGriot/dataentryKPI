# Data Entry KPI Target Manager

An advanced Python-based platform for comprehensive management, distribution, and analysis of Key Performance Indicators (KPIs). The system features machine-learning-driven seasonality prediction and dual user interfaces (Tkinter & Streamlit) for maximum flexibility.

## 🌟 Core Features

### 📈 Predictive Analytics
- **Multivariate Seasonality Predictor:** Uses Ordinary Least Squares (OLS) regression to calculate seasonal weights based on historical data and external drivers (e.g., weather, market trends).
- **Interactive Dashboards:** Sequential chronological timelines for multi-year analysis, preventing data overlap and ensuring clear trend visualization.

### 📁 KPI & Plant Management
- **Hierarchical Organization:** Manage deep trees of Groups, Subgroups, and Folders.
- **Template System:** Standardize indicators across different facilities using reusable prototypes.
- **Granular Visibility:** Control KPI availability on a per-plant basis.

### 📦 Robust Data Operations
- **Optimized Export:** Enriched CSV exports with human-readable metadata and unified periodic targets.
- **Integrated Backup:** Full system state packaging into encrypted or standard ZIP archives.

## 📂 Project Structure

```
dataentryKPI/
│
├── src/
│   ├── core/             # DAG Engine, Calculation logic
│   ├── services/         # ML Predictors, Seasonality Analysis
│   ├── interfaces/       # GUIs (Tkinter & Streamlit)
│   ├── data_access/      # DB Setup and Repository pattern
│   ├── kpi_management/   # Structural CRUD (Hierarchy, Templates)
│   ├── target_management/# Annual entry, Repartition logic
│   ├── data_retriever.py # Read-only Data Facade
│   └── export_manager.py # Optimized CSV/ZIP logic
│
├── docs/                 # Comprehensive Technical & User Documentation
├── databases/            # SQLite storage partitioned by domain
├── multivariate_test_data.csv # Sample data for ML predictor
├── main.py               # Unified Launcher
└── requirements.txt      # Project dependencies
```

## 🚀 Getting Started

### 1. Installation
Ensure you have Python 3.10+ installed.
```bash
pip install -r requirements.txt
```

### 2. Run the Application
You can launch either interface from the root entry point:

**Desktop Interface (Tkinter):**
```bash
python main.py tkinter
```

**Web Interface (Streamlit):**
```bash
python main.py streamlit
```

## 📚 Documentation

For a deep dive into the system logic, please refer to the **[Documentation Index](docs/index.md)**:

- **[System Architecture](docs/architecture.md)**: Layered design and data flow.
- **[Database Schema](docs/database_schema.md)**: Partitioned SQLite reference.
- **[Tkinter Manual](docs/gui_tkinter.md)**: Desktop-specific workflows.
- **[Streamlit Manual](docs/gui_streamlit.md)**: Web-specific features.
- **[Core Logic & Algorithms](docs/features.md)**: Details on the Formula Engine and ML Predictor.

## ⚖️ License & History

- This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
- For a detailed history of changes, see the [CHANGELOG](CHANGELOG.md).

---
*Developed with precision for advanced performance monitoring.*
