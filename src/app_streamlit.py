# app_streamlit.py

import streamlit as st
import pandas as pd
import database_manager as db  # Assicurati che database_manager.py sia nello stesso percorso
import json
import datetime
import calendar

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(layout="wide", page_title="Gestione Target KPI")

st.title("📊 Applicazione Gestione Target KPI")
st.markdown("Utilizza la barra laterale per navigare tra le diverse sezioni.")

# --- BARRA LATERALE DI NAVIGAZIONE ---
page = st.sidebar.radio(
    "Seleziona una pagina",
    (
        "Inserimento Target",
        "Gestione KPI",
        "Gestione Stabilimenti",
        "Visualizzazione Risultati",
    ),
)


# --- FUNZIONI DI UTILITÀ PER LA UI ---
@st.cache_data  # Manteniamo il caching per queste funzioni che non cambiano spesso
def get_kpi_df():
    kpis = db.get_kpis()
    if not kpis:
        return pd.DataFrame(
            columns=[
                "ID",
                "Nome",
                "Descrizione",
                "Tipo Calcolo",
                "Unità di Misura",
                "Visibile",
            ]
        )
    df = pd.DataFrame(
        kpis,
        columns=[
            "ID",
            "Nome",
            "Descrizione",
            "Tipo Calcolo",
            "Unità di Misura",
            "Visibile",
        ],
    )
    df["Visibile"] = df["Visibile"].apply(lambda x: True if x == 1 else False)
    df["Unità di Misura"] = df["Unità di Misura"].fillna("")
    return df


@st.cache_data
def get_stabilimenti_df():
    stabilimenti = db.get_stabilimenti()
    if not stabilimenti:
        return pd.DataFrame(columns=["ID", "Nome", "Visibile"])
    df = pd.DataFrame(stabilimenti, columns=["ID", "Nome", "Visibile"])
    df["Visibile"] = df["Visibile"].apply(lambda x: True if x == 1 else False)
    return df


def handle_kpi_edit():
    if (
        "kpi_editor" not in st.session_state
        or "edited_rows" not in st.session_state.kpi_editor
    ):
        return
    edited_rows = st.session_state.kpi_editor["edited_rows"]
    current_kpi_df = get_kpi_df()  # Usa la versione cachata per riferimento

    for idx, changes in edited_rows.items():
        try:
            row_data = current_kpi_df.iloc[idx]
            kpi_id = int(row_data["ID"])
            updated_data = row_data.to_dict()
            updated_data.update(changes)

            unit_of_measure = updated_data.get("Unità di Misura", "")

            db.update_kpi(
                kpi_id,
                updated_data["Nome"],
                updated_data["Descrizione"],
                updated_data["Tipo Calcolo"],
                unit_of_measure,
                bool(updated_data["Visibile"]),
            )
            st.toast(f"KPI ID {kpi_id} aggiornato.")
        except IndexError:
            st.error(f"Errore: riga con indice {idx} non trovata. Ricarica la pagina.")
        except Exception as e:
            st.error(f"Errore nell'aggiornamento del KPI ID {kpi_id}: {e}")
    get_kpi_df.clear()  # Pulisce la cache per forzare il ri-caricamento al prossimo accesso


def handle_stabilimento_edit():
    if (
        "stabilimento_editor" not in st.session_state
        or "edited_rows" not in st.session_state.stabilimento_editor
    ):
        return
    edited_rows = st.session_state.stabilimento_editor["edited_rows"]
    current_stabilimenti_df = get_stabilimenti_df()

    for idx, changes in edited_rows.items():
        try:
            row_data = current_stabilimenti_df.iloc[idx]
            stabilimento_id = int(row_data["ID"])
            updated_data = row_data.to_dict()
            updated_data.update(changes)

            db.update_stabilimento(
                stabilimento_id, updated_data["Nome"], bool(updated_data["Visibile"])
            )
            st.toast(f"Stabilimento ID {stabilimento_id} aggiornato.")
        except IndexError:
            st.error(f"Errore: riga con indice {idx} non trovata. Ricarica la pagina.")
        except Exception as e:
            st.error(
                f"Errore nell'aggiornamento dello stabilimento ID {stabilimento_id}: {e}"
            )
    get_stabilimenti_df.clear()


# --- PAGINA: GESTIONE KPI ---
if page == "Gestione KPI":
    st.header("⚙️ Gestione Indicatori Chiave di Performance (KPI)")
    with st.expander("Aggiungi un nuovo KPI", expanded=False):
        with st.form("new_kpi_form", clear_on_submit=True):
            new_name = st.text_input("Nome KPI *")
            new_desc = st.text_area("Descrizione")
            new_type = st.selectbox("Tipologia di Calcolo *", ("Incrementale", "Media"))
            new_unit = st.text_input("Unità di Misura (es. %, €, Unità, Giorni)")
            new_visible = st.checkbox("Visibile nel data entry", value=True)
            submitted = st.form_submit_button("Aggiungi KPI")
            if submitted:
                if not new_name:
                    st.error("Il nome del KPI è obbligatorio.")
                else:
                    try:
                        db.add_kpi(new_name, new_desc, new_type, new_unit, new_visible)
                        st.success(f"KPI '{new_name}' aggiunto!")
                        get_kpi_df.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
    st.subheader("Elenco KPI Esistenti")
    if st.button("Ricarica elenco KPI"):
        get_kpi_df.clear()
        st.rerun()
    try:
        kpi_df_display = get_kpi_df()
        st.data_editor(
            kpi_df_display,
            key="kpi_editor",
            on_change=handle_kpi_edit,
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True),
                "Descrizione": st.column_config.TextColumn(width="large"),
                "Unità di Misura": st.column_config.TextColumn("Unità Misura"),
                "Visibile": st.column_config.CheckboxColumn("Visibile", default=True),
            },
            hide_index=True,
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Impossibile caricare i KPI: {e}")

# --- PAGINA: GESTIONE STABILIMENTI ---
elif page == "Gestione Stabilimenti":
    st.header("🏭 Gestione Stabilimenti")
    with st.expander("Aggiungi un nuovo stabilimento", expanded=False):
        with st.form("new_stabilimento_form", clear_on_submit=True):
            new_name = st.text_input("Nome Stabilimento *")
            new_visible = st.checkbox("Visibile nel data entry", value=True)
            submitted = st.form_submit_button("Aggiungi Stabilimento")
            if submitted:
                if not new_name:
                    st.error("Il nome è obbligatorio.")
                else:
                    try:
                        db.add_stabilimento(new_name, new_visible)
                        st.success(f"Stabilimento '{new_name}' aggiunto!")
                        get_stabilimenti_df.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
    st.subheader("Elenco Stabilimenti Esistenti")
    if st.button("Ricarica elenco Stabilimenti"):
        get_stabilimenti_df.clear()
        st.rerun()
    try:
        stabilimenti_df_display = get_stabilimenti_df()
        st.data_editor(
            stabilimenti_df_display,
            key="stabilimento_editor",
            on_change=handle_stabilimento_edit,
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True),
                "Visibile": st.column_config.CheckboxColumn("Visibile", default=True),
            },
            hide_index=True,
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Impossibile caricare gli stabilimenti: {e}")

# --- PAGINA: INSERIMENTO TARGET ---
elif page == "Inserimento Target":
    st.header("🎯 Inserimento Target Annuali")
    col1, col2 = st.columns(2)
    with col1:
        current_year = datetime.datetime.now().year
        selected_year = st.number_input(
            "Anno", min_value=2020, max_value=2050, value=current_year
        )
    with col2:
        stabilimenti_visibili = db.get_stabilimenti(only_visible=True)
        if not stabilimenti_visibili:
            st.warning("Nessuno stabilimento visibile. Aggiungine uno.")
            st.stop()
        stabilimenti_dict = {
            s["name"]: s["id"] for s in stabilimenti_visibili
        }  # Usa i nomi dei campi corretti
        selected_stabilimento_name = st.selectbox(
            "Stabilimento", options=list(stabilimenti_dict.keys())
        )
        if not selected_stabilimento_name:
            st.warning("Seleziona uno stabilimento.")
            st.stop()
        selected_stabilimento_id = stabilimenti_dict[selected_stabilimento_name]

    st.markdown("---")
    kpis_visibili = db.get_kpis(only_visible=True)
    if not kpis_visibili:
        st.warning("Nessun KPI visibile. Aggiungine uno.")
        st.stop()

    targets_to_save = {}
    all_valid = True
    with st.form("targets_form"):
        for kpi in kpis_visibili:  # Itera sui dizionari/righe
            kpi_id = kpi["id"]
            kpi_name = kpi["name"]
            kpi_unit = kpi["unit_of_measure"]
            kpi_calc_type = kpi["calculation_type"]

            expander_label = f"🎯 Target per: {kpi_name}"
            if kpi_unit:
                expander_label += f" (Unità: {kpi_unit})"

            with st.expander(expander_label, expanded=True):
                existing_target_row = db.get_annual_target(
                    selected_year, selected_stabilimento_id, kpi_id
                )

                default_target = (
                    existing_target_row["annual_target"] if existing_target_row else 0.0
                )
                default_logic = (
                    existing_target_row["repartition_logic"]
                    if existing_target_row
                    else "Mese"
                )
                default_repartition = {}
                if existing_target_row and existing_target_row["repartition_values"]:
                    try:
                        default_repartition = json.loads(
                            existing_target_row["repartition_values"]
                        )
                    except json.JSONDecodeError:
                        st.warning(f"Errore decodifica ripartizione per {kpi_name}.")

                c1_target, c2_target = st.columns([1, 2])
                with c1_target:
                    annual_target_label = "Target Annuale"
                    if kpi_unit:
                        annual_target_label += f" ({kpi_unit})"
                    annual_target = st.number_input(
                        annual_target_label,
                        value=default_target,
                        key=f"target_{kpi_id}",
                        min_value=0.0,
                        format="%.2f",
                    )

                repartition_logic = default_logic  # Default
                repartition_values_input = {}  # Per l'input utente

                # La logica di ripartizione utente è rilevante principalmente per KPI Incrementali
                # Per KPI Media, la mia implementazione applica una ripartizione "generosa" standard.
                # Tuttavia, manteniamo l'input per coerenza e possibile uso futuro.
                if kpi_calc_type == "Incrementale":
                    with c2_target:
                        repartition_logic = st.radio(
                            "Logica di Ripartizione (per KPI Incrementali)",
                            ["Mese", "Trimestre"],
                            index=["Mese", "Trimestre"].index(default_logic),
                            key=f"logic_{kpi_id}",
                            horizontal=True,
                        )
                    st.markdown(
                        f"**Percentuali di ripartizione per {repartition_logic}** (KPI Incrementale)"
                    )
                    if repartition_logic == "Mese":
                        mesi = [calendar.month_name[i] for i in range(1, 13)]
                        cols_rep = st.columns(6)
                        for i, mese in enumerate(mesi):
                            with cols_rep[i % 6]:
                                repartition_values_input[mese] = st.number_input(
                                    f"% {mese}",
                                    value=default_repartition.get(
                                        mese, round(100 / 12, 2)
                                    ),
                                    key=f"rep_{kpi_id}_{mese}",
                                    min_value=0.0,
                                    max_value=100.0,
                                    step=0.01,
                                    format="%.2f",
                                )
                    else:  # Trimestre
                        trimestri = ["Q1", "Q2", "Q3", "Q4"]
                        cols_rep = st.columns(4)
                        for i, q in enumerate(trimestri):
                            with cols_rep[i]:
                                repartition_values_input[q] = st.number_input(
                                    f"% {q}",
                                    value=default_repartition.get(q, 25.0),
                                    key=f"rep_{kpi_id}_{q}",
                                    min_value=0.0,
                                    max_value=100.0,
                                    step=1.0,
                                    format="%.2f",
                                )

                    if annual_target > 0:
                        total_percentage = sum(repartition_values_input.values())
                        if not (99.9 <= total_percentage <= 100.1):
                            st.error(
                                f"Per '{kpi_name}', somma percentuali è {total_percentage:.2f}%. Deve essere ~100%."
                            )
                            all_valid = False
                else:  # KPI Media
                    with c2_target:
                        st.info(
                            "Per KPI di tipo 'Media', la ripartizione 'generosa/permissiva' è applicata automaticamente."
                        )
                        # Manteniamo i campi disabilitati o nascosti, ma salviamo i default
                        repartition_logic = "Mese"  # Default non usato attivamente nel calcolo della media pesata
                        repartition_values_input = {
                            calendar.month_name[i]: round(100 / 12, 2)
                            for i in range(1, 13)
                        }

                if annual_target >= 0:
                    targets_to_save[kpi_id] = {
                        "annual_target": annual_target,
                        "repartition_logic": repartition_logic,
                        "repartition_values": repartition_values_input,
                    }
        submitted = st.form_submit_button("Salva Tutti i Target", type="primary")
        if submitted:
            if not all_valid:
                st.error("Correggi gli errori prima di salvare.")
            elif not targets_to_save:
                st.warning("Nessun target inserito.")
            else:
                try:
                    db.save_annual_targets(
                        selected_year, selected_stabilimento_id, targets_to_save
                    )
                    st.success("Target salvati e ripartizioni ricalcolate!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

# --- PAGINA: VISUALIZZAZIONE RISULTATI ---
elif page == "Visualizzazione Risultati":
    st.header("📈 Visualizzazione Dati Ripartiti")
    filter_c1, filter_c2, filter_c3, filter_c4 = st.columns(4)
    with filter_c1:
        current_year = datetime.datetime.now().year
        sel_year = st.number_input(
            "Anno", min_value=2020, max_value=2050, value=current_year, key="vis_year"
        )
    with filter_c2:
        stabilimenti = db.get_stabilimenti()
        if not stabilimenti:
            st.warning("Nessuno stabilimento disponibile.")
            st.stop()
        s_dict = {s["name"]: s["id"] for s in stabilimenti}
        sel_s_name = st.selectbox(
            "Stabilimento", options=list(s_dict.keys()), key="vis_stab"
        )
        if not sel_s_name:
            st.stop()
        sel_s_id = s_dict[sel_s_name]
    with filter_c3:
        kpis = db.get_kpis()
        if not kpis:
            st.warning("Nessun KPI disponibile.")
            st.stop()
        k_dict = {
            k["name"]: {
                "id": k["id"],
                "unit": k["unit_of_measure"],
                "type": k["calculation_type"],
            }
            for k in kpis
        }
        sel_k_name = st.selectbox("KPI", options=list(k_dict.keys()), key="vis_kpi")
        if not sel_k_name:
            st.stop()
        sel_k_id = k_dict[sel_k_name]["id"]
        sel_k_unit = k_dict[sel_k_name]["unit"]
        sel_k_type = k_dict[sel_k_name]["type"]
    with filter_c4:
        period_type = st.selectbox(
            "Periodicità",
            ["Giorno", "Settimana", "Mese", "Trimestre"],
            index=2,
            key="vis_period",
        )

    try:
        data_ripartiti = db.get_ripartiti_data(
            sel_year, sel_s_id, sel_k_id, period_type
        )
    except Exception as e:
        st.error(f"Errore nel recupero dati ripartiti: {e}")
        data_ripartiti = []  # Evita errori successivi

    if not data_ripartiti:
        st.info(
            "Nessun dato ripartito per la selezione corrente. Prova a salvare dei target."
        )
    else:
        # Converti le Row di sqlite3 in dizionari per pandas
        df_data = [
            {"Periodo": row["Periodo"], "Target": row["Target"]}
            for row in data_ripartiti
        ]
        df = pd.DataFrame(df_data)

        # Ordinamento intelligente basato sul tipo di periodo
        if period_type == "Mese":
            mesi_ordinati = [calendar.month_name[i] for i in range(1, 13)]
            df["Periodo"] = pd.Categorical(
                df["Periodo"], categories=mesi_ordinati, ordered=True
            )
        elif period_type == "Trimestre":
            trimestri_ordinati = ["Q1", "Q2", "Q3", "Q4"]
            df["Periodo"] = pd.Categorical(
                df["Periodo"], categories=trimestri_ordinati, ordered=True
            )
        elif period_type == "Giorno":
            try:
                df["Periodo"] = pd.to_datetime(df["Periodo"])
            except ValueError:
                pass  # Lascia come stringa se non è una data valida

        df = df.sort_values(by="Periodo").reset_index(drop=True)

        st.subheader(
            f"Dati per {sel_k_name} ({sel_k_type}) - {sel_s_name} ({sel_year}) - Periodicità: {period_type}"
        )

        # Calcola totale o media
        summary_value = 0
        summary_label = ""
        if not df.empty:
            if sel_k_type == "Incrementale":
                summary_value = df["Target"].sum()
                summary_label = (
                    f"**Totale Ripartito ({period_type}): {summary_value:,.2f}**"
                )
            else:  # Media
                summary_value = df["Target"].mean()
                summary_label = (
                    f"**Media Ripartita ({period_type}): {summary_value:,.2f}**"
                )

            if sel_k_unit:
                summary_label += f" **({sel_k_unit})**"
            st.markdown(summary_label)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.dataframe(
                df.style.format({"Target": "{:,.2f}"}),
                use_container_width=True,
                height=35 * (len(df) + 1) if not df.empty else 100,
            )
        with chart_col2:
            if not df.empty:
                # Per i grafici, è meglio avere il periodo come indice se non è già una data/ora
                if period_type in ["Mese", "Trimestre"] or isinstance(
                    df["Periodo"].dtype, pd.CategoricalDtype
                ):
                    st.bar_chart(
                        df.set_index("Periodo")["Target"], use_container_width=True
                    )
                else:  # Giorno (già datetime) o Settimana (stringa)
                    st.bar_chart(
                        df.set_index("Periodo")["Target"], use_container_width=True
                    )
