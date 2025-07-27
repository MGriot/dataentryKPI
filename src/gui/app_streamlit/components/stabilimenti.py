import streamlit as st
import data_retriever
from stabilimenti_management import crud as stabilimenti_manager

def app():
    st.title("🏭 Gestione Stabilimenti")

    # --- Add New Stabilimento ---
    st.header("Aggiungi Nuovo Stabilimento")
    with st.form(key='add_stabilimento_form'):
        new_name = st.text_input("Nome Stabilimento:")
        new_description = st.text_area("Descrizione:")
        new_visible = st.checkbox("Visibile per Inserimento Target", value=True)
        new_color = st.color_picker("Colore:", '#000000')
        add_button = st.form_submit_button("Aggiungi Stabilimento")

        if add_button:
            if new_name:
                try:
                    stabilimenti_manager.add_stabilimento(new_name, new_description, new_visible, new_color)
                    st.success(f"Stabilimento '{new_name}' aggiunto con successo!")
                    st.experimental_rerun() # Rerun to refresh the list
                except Exception as e:
                    st.error(f"Errore nell'aggiungere lo stabilimento: {e}")
            else:
                st.warning("Il nome dello stabilimento non può essere vuoto.")

    # --- Display Existing Stabilimenti ---
    st.header("Stabilimenti Esistenti")
    stabilimenti = data_retriever.get_all_stabilimenti()

    if stabilimenti:
        # Create a list of dictionaries for easier display
        display_data = []
        for s in stabilimenti:
            display_data.append({
                "ID": s['id'],
                "Nome": s['name'],
                "Descrizione": s['description'],
                "Visibile": "Sì" if s['visible'] else "No",
                "Colore": s['color'] # Display color hex
            })
        
        st.dataframe(display_data, use_container_width=True)

        # --- Edit/Delete Stabilimento ---
        st.subheader("Modifica o Elimina Stabilimento")
        
        # Create a mapping from name to ID for selection
        stabilimento_names = {s['name']: s['id'] for s in stabilimenti}
        selected_stabilimento_name = st.selectbox(
            "Seleziona Stabilimento:", 
            options=list(stabilimento_names.keys()),
            key='edit_delete_select'
        )

        if selected_stabilimento_name:
            selected_stabilimento_id = stabilimento_names[selected_stabilimento_name]
            # Retrieve full data for the selected stabilimento
            selected_stabilimento = next((s for s in stabilimenti if s['id'] == selected_stabilimento_id), None)

            if selected_stabilimento:
                with st.form(key='edit_stabilimento_form'):
                    edit_name = st.text_input("Nome:", value=selected_stabilimento['name'], key='edit_name')
                    edit_description = st.text_area("Descrizione:", value=selected_stabilimento['description'], key='edit_description')
                    edit_visible = st.checkbox("Visibile per Inserimento Target", value=selected_stabilimento['visible'], key='edit_visible')
                    edit_color = st.color_picker("Colore:", value=selected_stabilimento['color'], key='edit_color')

                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button("Aggiorna Stabilimento")
                    with col2:
                        delete_button = st.form_submit_button("Elimina Stabilimento")

                    if update_button:
                        if edit_name:
                            try:
                                stabilimenti_manager.update_stabilimento(
                                    selected_stabilimento_id, edit_name, edit_description, edit_visible, edit_color
                                )
                                st.success(f"Stabilimento '{edit_name}' aggiornato con successo!")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Errore nell'aggiornare lo stabilimento: {e}")
                        else:
                            st.warning("Il nome dello stabilimento non può essere vuoto.")

                    if delete_button:
                        if st.checkbox(f"Conferma eliminazione di '{selected_stabilimento_name}'", key='confirm_delete'):
                            try:
                                stabilimenti_manager.delete_stabilimento(selected_stabilimento_id)
                                st.success(f"Stabilimento '{selected_stabilimento_name}' eliminato con successo!")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Errore nell'eliminare lo stabilimento: {e}")
            else:
                st.warning("Seleziona uno stabilimento valido per modificare o eliminare.")
    else:
        st.info("Nessuno stabilimento configurato. Aggiungi un nuovo stabilimento sopra.")
