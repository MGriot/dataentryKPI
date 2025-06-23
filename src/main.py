# main.py
import sys
import subprocess
import os
import argparse
from datetime import datetime

# Attempt to import app_config.
# Adjust the import according to your project structure.
try:
    # Option 1: If main.py is in PROJECT_ROOT and app_config is in PROJECT_ROOT/src/
    # Ensure src has an __init__.py to be a package.
    # Add PROJECT_ROOT to PYTHONPATH or run from PROJECT_ROOT.
    # from src import app_config

    # Option 2: If app_config.py is in the same directory as main.py
    import app_config

    # Option 3: If you have a different structure, adjust accordingly.
    # For example, if main.py is in src/ and app_config.py is also in src/
    # import app_config (if running from src/)
    # from . import app_config (if main.py is part of a package)

except ImportError as e:
    # A more robust way for Option 1 might be to add the project root to sys.path
    # current_dir = Path(__file__).resolve().parent
    # project_root = current_dir # If main.py is at root
    # project_root = current_dir.parent # If main.py is in a 'scripts' or 'bin' folder
    # sys.path.insert(0, str(project_root))
    # from src import app_config
    # For this example, we'll keep it simple and rely on PYTHONPATH or simpler structures.
    print(f"Error: Could not import app_config: {e}")
    print("Please ensure 'app_config.py' is in Python's search path (PYTHONPATH),")
    print(
        "or adjust the import statement in 'main.py' to match your project structure."
    )
    print("A common structure is to have 'app_config.py' in a 'src' directory,")
    print(
        "and run 'main.py' from the project root after adding the root to PYTHONPATH."
    )
    sys.exit(1)


def run_application(
    command_list, app_name_from_config, resolved_log_dir_path, app_script_path_to_check
):
    """
    Runs an application as a subprocess, redirecting stdout and stderr
    to log files in the already existing resolved_log_dir_path.
    It first checks if the application script exists.
    """
    # Verify the application script (e.g., app_streamlit.py) exists
    if not os.path.exists(app_script_path_to_check):
        print(
            f"Error: Could not find application script '{os.path.basename(app_script_path_to_check)}' "
            f"at the specified path: {app_script_path_to_check}"
        )
        print(
            f"Please ensure the file '{os.path.basename(app_script_path_to_check)}' "
            "is correctly specified by SCRIPT_NAME in config.ini ([Interface.*] section) "
            "and its path is correctly resolved relative to main.py or as an absolute path."
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize app_name for use in filenames (replace spaces with underscores)
    safe_app_name = app_name_from_config.lower().replace(" ", "_")

    stdout_log_file = os.path.join(
        resolved_log_dir_path, f"{safe_app_name}_{timestamp}_stdout.log"
    )
    stderr_log_file = os.path.join(
        resolved_log_dir_path, f"{safe_app_name}_{timestamp}_stderr.log"
    )

    print(f"Starting the {app_name_from_config} interface...")
    print(f"Standard output will be logged to: {stdout_log_file}")
    print(f"Standard errors will be logged to: {stderr_log_file}")

    try:
        # Open log files for writing
        with open(stdout_log_file, "w", encoding="utf-8") as f_stdout, open(
            stderr_log_file, "w", encoding="utf-8"
        ) as f_stderr:

            # subprocess.run will wait for the process to complete.
            process_result = subprocess.run(
                command_list,
                check=True,  # Raises CalledProcessError if the return code is non-zero
                text=True,  # Decodes stdout/stderr as text (though redirected here)
                stdout=f_stdout,  # Redirect standard output to the log file
                stderr=f_stderr,  # Redirect standard error to the log file
            )
        print(f"The {app_name_from_config} application terminated successfully.")

    except (
        FileNotFoundError
    ):  # Error if the executable in command_list (e.g., python) is not found
        print(
            f"Error: Executable not found in the command list. "
            f"Ensure Python and necessary modules (e.g., Streamlit if using '-m streamlit') "
            f"are installed and in the system's PATH."
        )
        print(f"Command that caused the error: {' '.join(command_list)}")
    except subprocess.CalledProcessError as e:
        # This exception is raised if check=True and the process returns a non-zero exit code
        print(f"An error occurred while running {app_name_from_config}.")
        print(f"Return code: {e.returncode}")
        print(f"Consult the log files for details:")
        print(f"  Output (may contain useful info): {stdout_log_file}")
        print(f"  Errors: {stderr_log_file}")
    except Exception as e:  # Catch-all for other unexpected errors
        print(
            f"An unexpected error occurred while starting {app_name_from_config}: {e}"
        )
        print(f"Consult the log files for details, if available:")
        print(f"  Output: {stdout_log_file}")
        print(f"  Errors: {stderr_log_file}")


def main():
    """
    Starts the user interface specified via command-line arguments.
    Configurations (including log paths and interface commands) are read via
    app_config.py (which loads them from config.ini).
    The log directory is created by app_config.py at the project root level.
    """
    # Get available interface choices from app_config (loaded from config.ini)
    available_interfaces = list(app_config.INTERFACE_CONFIGURATIONS.keys())
    if not available_interfaces:
        print(
            "Error: No interface configurations found via app_config.py (from config.ini)."
        )
        print(
            "Please check your config.ini file for [Interface.*] sections like [Interface.Streamlit]."
        )
        sys.exit(1)

    # Initialize argument parser
    parser = argparse.ArgumentParser(
        description="Starts the specified user interface. "
        "Logs are saved in the directory defined in config.ini (relative to project root).",
        epilog=f"Example usage: python main.py {available_interfaces[0] if available_interfaces else 'streamlit'}",
    )
    # Add argument for interface choice
    parser.add_argument(
        "interface",
        choices=available_interfaces,  # Allowed choices, dynamically loaded
        type=str.lower,  # Convert argument to lowercase
        help=(
            f"The interface to start. Available choices are: "
            f"{', '.join(available_interfaces)}."
        ),
    )
    args = parser.parse_args()  # Parse command-line arguments

    choice = args.interface
    python_executable = sys.executable  # Path to the current Python interpreter

    # Directory where main.py itself is located.
    # Used to resolve relative paths for app_streamlit.py, app_tkinter.py if they are co-located.
    current_main_script_dir = os.path.dirname(os.path.abspath(__file__))

    # Get the fully resolved and already created LOG_DIR_PATH from app_config
    # app_config.py should have already created this directory.
    resolved_log_dir = app_config.LOG_DIR_PATH

    # Get the chosen interface's configuration details from app_config
    selected_config = app_config.INTERFACE_CONFIGURATIONS.get(choice)

    if selected_config:
        app_script_filename = selected_config["script_name"]

        # Construct the full path to the application script (e.g., app_streamlit.py)
        # This assumes SCRIPT_NAME in config.ini is a filename relative to main.py's location.
        # If SCRIPT_NAME is an absolute path or relative to PROJECT_ROOT, this logic would need adjustment
        # or the config value itself should be the fully resolved path.
        app_script_path = os.path.join(current_main_script_dir, app_script_filename)

        # Build the full command to execute
        command_parts = [python_executable]

        # Get command module arguments (e.g., "streamlit run" for Streamlit)
        module_args_str = selected_config.get("command_module_args", "").strip()

        if (
            choice == "streamlit"
            and "streamlit" in module_args_str
            and "run" in module_args_str
        ):
            # Specific handling for "streamlit run" to use "-m"
            command_parts.append("-m")
            command_parts.extend(module_args_str.split())  # e.g., ["streamlit", "run"]
            command_parts.append(app_script_path)
        elif module_args_str:
            # For other cases with module arguments (less common for basic Tkinter script)
            # This might require "-m" depending on the arguments.
            # For simplicity, we assume they are direct commands or that the user
            # configured "python -m my_module" as part of COMMAND_MODULE_ARGS if needed.
            # A more robust solution would be to parse COMMAND_MODULE_ARGS more carefully.
            command_parts.extend(module_args_str.split())
            command_parts.append(app_script_path)
        else:
            # Default: just run the Python script directly (common for Tkinter)
            command_parts.append(app_script_path)

        # Call the helper function to run the application
        run_application(
            command_parts,
            selected_config["app_name"],
            resolved_log_dir,
            app_script_path,
        )
    else:
        # This block should theoretically not be reached due to 'choices' in argparse
        # and the check for available_interfaces.
        print(
            f"Error: Invalid interface choice '{choice}' somehow bypassed validation."
        )
        print(f"Available choices registered are: {', '.join(available_interfaces)}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
