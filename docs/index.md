# Data Entry KPI Documentation

Welcome to the documentation for the Data Entry KPI system. One shared Python core (SQLite data layer, repartition engine, ML seasonality predictor) is exposed through four interfaces: a **React web app** (primary), a **FastAPI REST API**, an **MCP server** for AI agents, and the original **Tkinter/Streamlit** desktop and web GUIs. All four read and write the same databases.

## 🚀 Quick Start

- **React app (primary):** backend `python -m uvicorn src.api:app --reload`, then `cd frontend && npm run dev`
- **Docker/Podman (all containers):** `podman-compose up --build`
- **Desktop App (Tkinter):** `python src/main.py tkinter`
- **Web App (Streamlit):** `python src/main.py streamlit`
- **MCP server:** `python src/mcp_server.py` (stdio, local) or `python src/mcp_server.py --http` (shared, API-key gated)

See the [repo root README](../README.md) for the full rundown of each option.

## 📚 Documentation Sections

### 🖥️ Current interfaces
- **[System Architecture](architecture.md):** How the four interfaces share one core — module breakdown and data flow.
- **[REST & MCP API Reference](api_reference.md):** Every FastAPI endpoint (grouped by resource) and the MCP tool list, for both transports.
- **[Database Schema](database_schema.md):** Partitioned SQLite tables, including the `db_users.db` audit/API-key tables.

### 🖥️ Legacy user interfaces
- **[Tkinter Desktop Manual](gui_tkinter.md):** Guide for the desktop application.
- **[Streamlit Web Manual](gui_streamlit.md):** Guide for the Streamlit web interface.

### 🛠️ Core logic
- **[Core Features & Logic](features.md):** Dynamic target distribution, the formula engine, and multivariate seasonality prediction — this logic is shared by every interface.
- **[Code-Level Deep Dive](code_depth.md):** DAG engine internals, reconciliation math, the actuals/trend calculation, and exact CSV export layouts, with code references.

## 🔑 Key Capabilities

1.  **Unified Management:** Manage KPI hierarchies (Groups > Subgroups > Indicators) centrally, from any interface.
2.  **Dynamic Target Scenarios:** Each KPI declares its own target count (1..N) — not hardcoded to a Base/Stretch pair.
3.  **Smart Distribution:** Automatically split annual targets using profiles (Sinusoidal, Progressive, etc.), a Global Split template, or ML-predicted weights.
4.  **Dependency-Ordered Calculation:** Formula-based KPIs are recalculated and repartitioned in dependency order (drivers before dependents) whenever any target changes anywhere in the system.
5.  **Flexible Calculation:** Python-like formulas or a visual Node Editor (Tkinter) for calculated KPIs that update in real time.
6.  **Auditability:** Every target and definition edit is attributed to a named profile and timestamped, visible in the React app's KPI Explorer history panel.
7.  **Multi-Platform:** Access the same data via the React app, REST API, MCP (for AI agents), the desktop app, or the Streamlit web app.
