# Data Entry KPI Target Manager

An advanced Python-based platform for comprehensive management and analysis of Key Performance Indicators (KPIs). It offers sophisticated target distribution algorithms, flexible KPI definition through templates, and support for master/sub-KPI relationships. The system provides dual user interfaces: a native desktop application built with Tkinter for rich interactive features and offline capability, and a web-based interface using Streamlit for browser accessibility and easy deployment. All data is managed using a SQLite database backend, with robust CSV export/import functionalities.

## Features

### Advanced Target Distribution
- **Multiple Mathematical Models:** Supports even, progressive/regressive, sinusoidal (seasonal), and quarterly patterns, including weekly bias adjustments.
- **Hierarchical Period Management:** Distributes targets across annual, quarterly, monthly, weekly, and daily periods.
- **Formula-Based Calculations:** Allows for complex calculations with dependencies.

### KPI Management
- **Template-Based Definitions:** Define KPIs using customizable templates.
- **Master/Sub KPI Relationships:** Establishes hierarchical links between KPIs.
- **Weighted Distributions:** Apply weights for precise target allocation.
- **Custom Calculation Rules & Unit Conversion:** Define specific rules and handle diverse unit conversions.

### Multi-Interface Support
- **Desktop Application (Tkinter):**
    - Native performance and rich interactive features.
    - Offline capability.
- **Web Interface (Streamlit):</b>
    - Browser-based access with a modern web interface.
    - Easy deployment and accessibility.

### Robust Data Management
- **SQLite Database Backend:** Stores all KPI structures, targets, and historical data.
- **CSV Export/Import:** Facilitates data exchange with external systems.
- **Historical Tracking & Analysis:** Enables target vs. actual analysis over time.

## Project Structure

```
dataentryKPI/
│
├── src/                  # Application source code (Python modules)
│   ├── app_config.py     # Application-wide configuration
│   ├── database_manager.py # (Assumed, based on description) Manages database interactions
│   ├── data_retriever.py # Handles data fetching logic
│   ├── export_manager.py # Manages data export functionalities (e.g., CSV)
│   ├── import_manager.py # Manages data import functionalities (e.g., CSV)
│   ├── gui/              # Contains UI implementations
│   │   ├── app_tkinter/  # Tkinter desktop application
│   │   │   └── main.py   # Entry point for Tkinter app
│   │   └── app_streamlit/ # Streamlit web application
│   │       └── main.py   # Entry point for Streamlit app
│   └── ...               # Other core modules (kpi_management, target_management, etc.)
├── docs/                 # Comprehensive documentation in Markdown format
│   ├── index.md          # Documentation index
│   ├── usage_tkinter.md  # User guide for Tkinter app
│   ├── usage_streamlit.md # User guide for Streamlit app
│   ├── architecture.md   # System architecture overview
│   ├── target_generation.md # Details on target distribution algorithms
│   ├── theoretical_framework.md # Underlying theoretical concepts
│   ├── database_schema.md # Database structure
│   └── configuration.md  # Configuration guide
├── requirements.txt      # Python dependencies
├── config.ini            # Centralized application configuration
├── README.md             # This file
└── main.py               # Main entry point for launching either GUI
```

## Getting Started

### Prerequisites
Ensure you have Python 3.x installed.

### 1. Clone the repository
```bash
git clone <repository_url>
cd dataentryKPI
```

### 2. Install Dependencies
Install all required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Run the Application
You can run either the Tkinter desktop application or the Streamlit web application.

#### Tkinter Desktop Application
```bash
python main.py tkinter
```
The application window will open, providing access to all features through a tabbed interface.

#### Streamlit Web Application
```bash
python main.py streamlit
```
The application will launch in your web browser (usually at `http://localhost:8501`).

For detailed usage instructions, refer to the [Documentation](#documentation) section.

## Documentation

For complete documentation, please see our [Documentation Index](docs/index.md), which includes:

### User Guides
- [Tkinter Desktop Guide](docs/usage_tkinter.md)
- [Streamlit Web Guide](docs/usage_streamlit.md)

### Technical Documentation
- [Architecture Overview](docs/architecture.md)
- [Target Generation Logic](docs/target_generation.md)
- [Theoretical Framework](docs/theoretical_framework.md)
- [Database Schema](docs/database_schema.md)
- [Configuration Guide](docs/configuration.md)

## Customization

The application can be customized by modifying the Python code within the `src` directory. This allows for:
- Adding new KPIs and distribution logic.
- Modifying data entry options and UI elements.
- Extending application functionality with new features.

Refer to the [Architecture Overview](docs/architecture.md) for guidance on extending or adapting the system.

## Contributing

Contributions are welcome! Please follow these steps:
1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes and ensure tests are added/updated.
4.  Submit a pull request with a clear description of your changes.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For questions or feedback, please contact Matteo Griot at matteo.griot@gmail.com.