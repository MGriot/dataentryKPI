# main.py

import sys
import subprocess
import os


def main():
    """
    Avvia l'interfaccia utente specificata tramite argomenti da riga di comando.

    Uso:
        python main.py streamlit  -> per avviare l'interfaccia web
        python main.py tkinter   -> per avviare l'interfaccia desktop
    """
    if len(sys.argv) < 2:
        print("Errore: specificare l'interfaccia da avviare.")
        print("Uso: python main.py [streamlit|tkinter]")
        sys.exit(1)

    choice = sys.argv[1].lower()
    python_executable = sys.executable
    current_script_dir = os.path.dirname(os.path.abspath(__file__))

    if choice == "streamlit":
        print("Avvio dell'interfaccia Streamlit...")
        streamlit_app_path = os.path.join(current_script_dir, "app_streamlit.py")
        command = [python_executable, "-m", "streamlit", "run", streamlit_app_path]
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError:
            print(
                f"Errore: impossibile trovare 'app_streamlit.py' al percorso specificato: {streamlit_app_path}"
            )
            print(
                "Assicurati che il file 'app_streamlit.py' si trovi nella stessa cartella di 'main.py'."
            )
        except subprocess.CalledProcessError as e:
            print(f"Si è verificato un errore durante l'esecuzione di Streamlit: {e}")

    elif choice == "tkinter":
        print("Avvio dell'interfaccia Tkinter...")
        tkinter_app_path = os.path.join(current_script_dir, "app_tkinter.py")
        command = [python_executable, tkinter_app_path]
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError:
            print(
                f"Errore: impossibile trovare 'app_tkinter.py' al percorso specificato: {tkinter_app_path}"
            )
            print(
                "Assicurati che il file 'app_tkinter.py' si trovi nella stessa cartella di 'main.py'."
            )
        except subprocess.CalledProcessError as e:
            print(f"Si è verificato un errore durante l'esecuzione di Tkinter: {e}")

    else:
        print(f"Scelta non valida: '{choice}'")
        print("Le scelte disponibili sono 'streamlit' o 'tkinter'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
