# main.py
import sys
import subprocess
import os
import argparse
from datetime import datetime
from pathlib import Path  # Added for robust path handling

# Attempt to import app_config.
# This section is crucial and depends on your project structure.
# Ensure app_config.py is in your PYTHONPATH or accessible.
try:
    import app_config
except ImportError as e:
    # Try to add project root to sys.path if app_config is in a subdirectory like 'src'
    # and main.py is at the project root.
    # This is a common pattern.
    try:
        current_script_path = Path(__file__).resolve()
        project_root = (
            current_script_path.parent
        )  # Assuming main.py is at the project root
        # If app_config is in 'src' directory at project_root
        # sys.path.insert(0, str(project_root / "src")) # Or just project_root if app_config is there
        sys.path.insert(0, str(project_root))  # If app_config.py is at the project root
        import app_config
    except Exception as e_retry:
        print(f"Error: Could not import app_config. Initial error: {e}")
        print(f"Retry error: {e_retry}")
        print("Please ensure 'app_config.py' is in Python's search path (PYTHONPATH),")
        print(
            "or adjust the import statement in 'main.py' to match your project structure."
        )
        print("Commonly, app_config.py is at the project root or in a 'src' directory,")
        print("and main.py is run from the project root.")
        sys.exit(1)

# --- Database Setup (Optional Addition to main.py) ---
# If you want main.py to handle initial database setup, you could add a command for it.
# For example: python main.py --setup-db
# This would then import and call:
# from db_core.setup import setup_databases
# And in the argparse section, you'd add an argument for it.
# For now, this is left out as main.py is primarily a UI launcher.
# The UI application itself (e.g., app_streamlit.py) should ensure databases are set up
# or call the setup function on its first run or startup.


def run_application(
    command_list, app_name_from_config, resolved_log_dir_path, app_script_path_to_check
):
    """
    Runs an application as a subprocess, redirecting stdout and stderr
    to log files in the already existing resolved_log_dir_path.
    It first checks if the application script exists.
    """
    app_script_path = Path(app_script_path_to_check)
    if not app_script_path.exists():
        print(
            f"Error: Could not find application script '{app_script_path.name}' "
            f"at the specified path: {app_script_path}"
        )
        print(
            f"Please ensure the file '{app_script_path.name}' "
            "is correctly specified by SCRIPT_NAME in config.ini ([Interface.*] section) "
            "and its path is correctly resolved."
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_app_name = app_name_from_config.lower().replace(" ", "_").replace("-", "_")

    # Ensure resolved_log_dir_path is a Path object
    log_dir = Path(resolved_log_dir_path)
    log_dir.mkdir(parents=True, exist_ok=True)  # Ensure log directory exists

    stdout_log_file = log_dir / f"{safe_app_name}_{timestamp}_stdout.log"
    stderr_log_file = log_dir / f"{safe_app_name}_{timestamp}_stderr.log"

    print(f"Starting the {app_name_from_config} interface...")
    print(f"Standard output will be logged to: {stdout_log_file}")
    print(f"Standard errors will be logged to: {stderr_log_file}")

    try:
        with open(stdout_log_file, "w", encoding="utf-8") as f_stdout, open(
            stderr_log_file, "w", encoding="utf-8"
        ) as f_stderr:
            process_result = subprocess.run(
                command_list,
                check=True,
                text=True,
                stdout=f_stdout,
                stderr=f_stderr,
            )
        print(f"The {app_name_from_config} application terminated successfully.")

    except FileNotFoundError:
        print(
            f"Error: Executable not found in the command list. "
            f"Ensure Python and necessary modules (e.g., Streamlit if using '-m streamlit') "
            f"are installed and in the system's PATH."
        )
        print(f"Command that caused the error: {' '.join(map(str, command_list))}")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running {app_name_from_config}.")
        print(f"Return code: {e.returncode}")
        print(f"Consult the log files for details:")
        print(f"  Output (may contain useful info): {stdout_log_file}")
        print(f"  Errors: {stderr_log_file}")
    except Exception as e:
        print(
            f"An unexpected error occurred while starting {app_name_from_config}: {e}"
        )
        print(f"Consult the log files for details, if available:")
        print(f"  Output: {stdout_log_file}")
        print(f"  Errors: {stderr_log_file}")


def main():
    """
    Starts the user interface specified via command-line arguments.
    Configurations are read via app_config.py (which loads them from config.ini).
    The log directory is managed by app_config.py.
    """
    # Ensure app_config has loaded necessary configurations
    if not hasattr(app_config, "INTERFACE_CONFIGURATIONS") or not hasattr(
        app_config, "LOG_DIR_PATH"
    ):
        print(
            "Error: app_config.py did not load INTERFACE_CONFIGURATIONS or LOG_DIR_PATH."
        )
        print("Please check your app_config.py and config.ini setup.")
        sys.exit(1)

    available_interfaces = list(app_config.INTERFACE_CONFIGURATIONS.keys())
    if not available_interfaces:
        print(
            "Error: No interface configurations found via app_config.py (from config.ini)."
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Starts the specified user interface. "
        "Logs are saved in the directory defined in config.ini.",
        epilog=f"Example usage: python main.py {available_interfaces[0] if available_interfaces else 'streamlit'}",
    )
    parser.add_argument(
        "interface",
        choices=available_interfaces,
        type=str.lower,
        help=f"The interface to start. Available: {', '.join(available_interfaces)}.",
    )
    # Optional argument for database setup
    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Initialize and set up the databases if they don't exist or need schema updates.",
    )
    # Optional argument for CSV export
    parser.add_argument(
        "--export-csv", action="store_true", help="Run the global CSV export process."
    )

    args = parser.parse_args()
    choice = args.interface

    # Handle --setup-db if provided
    if args.setup_db:
        print("Attempting to set up databases...")
        try:
            from db_core.setup import setup_databases  # Import when needed

            setup_databases()
            print("Database setup process completed.")
        except ImportError:
            print(
                "ERROR: Could not import 'setup_databases' from 'db_core.setup'. Ensure modules are structured correctly."
            )
        except Exception as e_setup:
            print(f"ERROR during database setup: {e_setup}")
            print(traceback.format_exc())
        # Decide if to exit after setup or continue to launch UI
        # For now, let's assume it can continue or just be a setup task.
        # If you want it to be exclusive:
        # if args.setup_db:
        #     sys.exit(0) # Exit after setup

    # Handle --export-csv if provided
    if args.export_csv:
        print("Attempting global CSV export...")
        try:
            from export_manager import (
                export_all_data_to_global_csvs,
                package_all_csvs_as_zip,
            )

            # Ensure CSV_EXPORT_BASE_PATH is available from app_config for the export function
            if not hasattr(app_config, "CSV_EXPORT_BASE_PATH"):
                print(
                    "ERROR: CSV_EXPORT_BASE_PATH not defined in app_config. Cannot export CSVs."
                )
            else:
                export_base_path = Path(app_config.CSV_EXPORT_BASE_PATH)
                export_all_data_to_global_csvs(str(export_base_path))
                # Optionally, also package them
                zip_success, zip_result = package_all_csvs_as_zip(
                    csv_base_path_str=str(export_base_path),
                    output_zip_filepath_str=str(
                        export_base_path / "global_data_export.zip"
                    ),
                )
                if zip_success:
                    print(f"CSV export and ZIP packaging successful: {zip_result}")
                else:
                    print(
                        f"CSV export successful, but ZIP packaging failed: {zip_result}"
                    )

            print("Global CSV export process completed.")
        except ImportError:
            print(
                "ERROR: Could not import 'export_all_data_to_global_csvs' from 'export_manager'."
            )
        except Exception as e_export:
            print(f"ERROR during CSV export: {e_export}")
            print(traceback.format_exc())
        # Decide if to exit after export. For now, assume it can continue or be an export task.
        # if args.export_csv:
        #     sys.exit(0)

    # Proceed to launch UI if no exclusive task like --setup-db or --export-csv caused an exit
    # (Currently, they don't cause an exit, so UI will always be attempted if 'interface' is given)

    python_executable = sys.executable
    current_main_script_dir = Path(__file__).resolve().parent
    resolved_log_dir = Path(app_config.LOG_DIR_PATH)
    selected_config = app_config.INTERFACE_CONFIGURATIONS.get(choice)

    if selected_config:
        app_script_filename = selected_config["script_name"]
        # Assume script_name in config is relative to main.py's directory
        # or an absolute path. For better robustness, ensure it's resolved correctly.
        # If app_script_filename is intended to be relative to project root:
        # project_root_for_scripts = Path(app_config.PROJECT_ROOT) # Assuming PROJECT_ROOT is in app_config
        # app_script_path = project_root_for_scripts / app_script_filename
        # For now, using current_main_script_dir as base:
        app_script_path = current_main_script_dir / app_script_filename

        command_parts = [
            Path(python_executable)
        ]  # Ensure python_executable is Path for consistency
        module_args_str = selected_config.get("command_module_args", "").strip()

        if (
            choice == "streamlit"
            and "streamlit" in module_args_str
            and "run" in module_args_str
        ):
            command_parts.append("-m")
            command_parts.extend(module_args_str.split())
            command_parts.append(app_script_path)
        elif module_args_str:
            command_parts.extend(module_args_str.split())
            command_parts.append(app_script_path)
        else:
            command_parts.append(app_script_path)

        run_application(
            [
                str(part) for part in command_parts
            ],  # Convert all parts to string for subprocess
            selected_config["app_name"],
            resolved_log_dir,
            app_script_path,
        )
    else:
        print(
            f"Error: Invalid interface choice '{choice}' (should have been caught by argparse)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
