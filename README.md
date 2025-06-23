# Data Entry KPI Target Manager

## Overview

This project is a specialized data entry application for managing and distributing Key Performance Indicator (KPI) targets. It is **not** a dashboard or analytics platform. Its sole purpose is to provide a robust interface for inputting annual KPI targets and automatically splitting them into periodic targets (monthly, weekly, daily) using advanced, configurable logic.

The application is available as both a desktop (Tkinter) and web (Streamlit) interface, providing flexibility for different environments and user preferences.

---

## Table of Contents

- [Features](#features)
- [What This Project Is Not](#what-this-project-is-not)
- [Data Sources & Storage](#data-sources--storage)
- [Installation](#installation)
- [Usage](#usage)
  - [Tkinter Desktop Application](#tkinter-desktop-application)
  - [Streamlit Web Application](#streamlit-web-application)
- [Customization](#customization)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Features

- **Annual Target Input:** Enter yearly targets for each KPI, with support for multiple target values per KPI (e.g., Target 1, Target 2).
- **Manual or Automatic Entry:** Enter targets manually for each period or let the system calculate them based on distribution logic.
- **Flexible Splitting:** Distribute annual targets into months, quarters, weeks, or days using several built-in profiles (even, progressive, sinusoidal, parabolic, event-based).
- **Custom Period Allocations:** Override automatic splits by specifying custom percentages for each period.
- **Event Adjustments:** Apply spikes, dips, or other adjustments to daily targets for specific events or periods.
- **KPI Hierarchy & Templates:** Organize KPIs into groups, subgroups, and indicators. Use templates for reusable indicator sets. Link KPIs in master/subordinate relationships with weighted distribution.
- **Facility Management:** Manage a list of facilities for which KPI targets are tracked, with visibility controls.
- **Data Export:** Export all entered and calculated target data in standard formats (CSV, Excel, ZIP) for use in external dashboards or reporting tools.
- **User Experience:** Desktop (Tkinter) and web (Streamlit) GUIs, with validation and guidance for correct data entry.

---

## What This Project Is Not

- **No Dashboard/Visualization:** This tool does not provide KPI dashboards, charts, or analytics. It is focused solely on target entry and distribution.
- **No Real-Time Data Tracking:** It does not track actual KPI performance or collect operational data—only target values are managed.

---

## Data Sources & Storage

- **SQLite Databases:** All KPI definitions, targets, and distribution logic are stored in local SQLite databases.
- **CSV/Excel Export:** Data can be exported for use in other systems.

---

## Installation

### Prerequisites

- Python 3.7+
- Pip (Python package installer)

### Steps

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    cd dataentryKPI
    ```

2.  Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

---

## Usage

### Tkinter Desktop Application

For a detailed guide, see [docs/tkinter_gui.md](docs/tkinter_gui.md).

**Quick Start:**
1. Navigate to the source directory (e.g., `src` or `ora`):

    ```bash
    cd src
    ```

2. Run the application:

    ```bash
    python app_tkinter.py
    ```

3. The application window will open, providing access to all features through a tabbed interface.

### Streamlit Web Application

For a detailed guide, see [docs/streamlit_gui.md](docs/streamlit_gui.md).

**Quick Start:**
1. Navigate to the source directory (e.g., `src` or `ora`):

    ```bash
    cd src
    ```

2. Run the application:

    ```bash
    streamlit run app_streamlit.py
    ```

3. The application will open in your web browser (usually at `http://localhost:8501`).

---

## Customization

You can customize the application by modifying the Python code in the `src` directory. Specifically, you can:

- Add new KPIs and distribution logic.
- Modify data entry options and UI elements.
- Extend the functionality of the application with new features.

---

## Contributing

Contributions to this project are welcome! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes and write tests.
4.  Submit a pull request with a clear description of your changes.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contact

For questions or feedback, please contact Matteo Griot at matteo.griot@gmail.com.
    cd src
    ```

2.  Run the application:

    ```bash
    streamlit run app_streamlit.py
    ```

3.  The dashboard will open in your web browser (usually at `http://localhost:8501`).

4.  Use the sidebar to select data, apply filters, and navigate between different sections of the dashboard.

## Customization

You can customize the dashboard by modifying the Python code in the `src` directory. Specifically, you can:

*   Add new KPIs and visualizations.
*   Modify data filtering options and UI elements.
*   Implement custom data processing logic.
*   Extend the functionality of the application with new features.

## Contributing

Contributions to this project are welcome! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes and write tests.
4.  Submit a pull request with a clear description of your changes.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For questions or feedback, please contact Matteo Griot at matteo.griot@gmail.com.

