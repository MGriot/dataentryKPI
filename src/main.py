"""
Main launcher for the KPI Management Application.
Launches either the Tkinter or Streamlit GUI based on command-line arguments.
"""
import sys
import subprocess
from pathlib import Path
import argparse

# Ensure the 'src' directory is in the Python path for robust imports
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def main():
    """Parses arguments and launches the selected interface."""
    parser = argparse.ArgumentParser(description="KPI Management App Launcher")
    parser.add_argument(
        "interface",
        choices=["tkinter", "streamlit"],
        nargs="?",  # Make the argument optional
        default="tkinter", # Default to tkinter if no argument is given
        help="Which GUI to launch (tkinter or streamlit). Defaults to tkinter.",
    )
    args = parser.parse_args()
    interface = args.interface.lower()

    if interface == "tkinter":
        print("Launching Tkinter GUI...")
        try:
            # Import the main Tkinter App class and run it
            from gui.app_tkinter.main import KpiApp
            app = KpiApp()
            app.mainloop()
        except ImportError as e:
            print(f"ERROR: Failed to import the Tkinter application. Make sure all components are in place. Details: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while running the Tkinter application: {e}")
            sys.exit(1)

    elif interface == "streamlit":
        print("Launching Streamlit GUI...")
        streamlit_script_path = project_root / "gui" / "app_streamlit.py"

        if not streamlit_script_path.exists():
            print(f"ERROR: Streamlit script not found at {streamlit_script_path}")
            sys.exit(1)

        command = ["streamlit", "run", str(streamlit_script_path)]
        try:
            print(f"Running command: {' '.join(command)}")
            subprocess.run(command, check=True)
        except FileNotFoundError:
            print("ERROR: 'streamlit' command not found. Is Streamlit installed? (pip install streamlit)")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: The Streamlit application exited with an error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while launching Streamlit: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
