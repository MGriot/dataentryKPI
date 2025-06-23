# Data Entry KPI Target Manager

A modular, extensible platform for managing, distributing, and analyzing Key Performance Indicator (KPI) targets for data entry processes. Supports both desktop (Tkinter) and web (Streamlit) interfaces, with robust database and export capabilities.

---

## Project Structure

```
dataentryKPI/
│
├── src/                  # Application source code (Python modules)
│   ├── app_config.py
│   ├── database_manager.py
│   ├── data_retriever.py
│   ├── export_manager.py
│   ├── app_tkinter.py
│   ├── app_streamlit.py
│   └── ...
├── docs/                 # Documentation (Markdown)
│   ├── usage_tkinter.md
│   ├── usage_streamlit.md
│   ├── architecture.md
│   ├── target_generation.md
│   └── ...
├── requirements.txt
├── config.ini
├── README.md
└── main.py
```

- **src/**: All core logic, interfaces, and configuration.
- **docs/**: In-depth documentation (see below).
- **main.py**: Entry point for launching interfaces.
- **config.ini**: Centralized configuration.

---

## Documentation

- [Usage: Tkinter Desktop](docs/usage_tkinter.md)
- [Usage: Streamlit Web](docs/usage_streamlit.md)
- [Architecture Overview](docs/architecture.md)
- [Automatic Target Generation Logic](docs/target_generation.md)

---

## Quick Start

1. **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd dataentryKPI
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Run the desired interface:**
    - **Tkinter Desktop:**
        ```bash
        python main.py tkinter
        ```
    - **Streamlit Web:**
        ```bash
        python main.py streamlit
        ```

See [docs/usage_tkinter.md](docs/usage_tkinter.md) and [docs/usage_streamlit.md](docs/usage_streamlit.md) for detailed guides.

---

## Technical Highlights

- **Automatic Target Generation:**  
  The system supports automatic distribution of annual KPI targets into quarters, months, weeks, and days using customizable mathematical profiles (progressive, sinusoidal, parabolic, etc.).  
  See [docs/target_generation.md](docs/target_generation.md) for a deep technical dive.

- **Database-Driven:**  
  All KPI structures, targets, and results are stored in SQLite databases, with modular CRUD logic.

- **Flexible Export:**  
  Export all targets and dictionaries to CSV/ZIP for integration with external systems.

- **Modular UI:**  
  Both desktop and web UIs share the same backend logic for consistency.

---

## Customization

You can customize the application by modifying the Python code in the `src` directory. See [docs/architecture.md](docs/architecture.md) for guidance on extending or adapting the system.

---
2. Run the application:

    ```bash
    python app_tkinter.py
    ```

3. The application window will open, providing access to all features through a tabbed interface.

### Streamlit Web Application

For a detailed guide, see [streamlit_gui](docs/streamlit_gui.md).

**Quick Start:**
1. Navigate to the source directory (e.g., `src`):

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
