import streamlit as st
import pandas as pd
from src.kpi_management import links as kpi_links_manager
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name

def app():
    st.title("🔗 Master/Sub Link Management")

    all_kpis = db_retriever.get_all_kpis_detailed()
    kpi_names = [get_kpi_display_name(kpi) for kpi in all_kpis]

    selected_kpi_name = st.selectbox("Select a KPI to manage:", kpi_names)

    if selected_kpi_name:
        selected_kpi = next((kpi for kpi in all_kpis if get_kpi_display_name(kpi) == selected_kpi_name), None)
        if selected_kpi:
            selected_kpi_id = selected_kpi['id']
            role_details = db_retriever.get_kpi_role_details(selected_kpi_id)

            st.metric("KPI Role", role_details['role'].capitalize())

            if role_details['role'] == 'master':
                st.subheader("Linked Sub-KPIs")
                linked_sub_kpis = db_retriever.get_linked_sub_kpis_detailed(selected_kpi_id)
                if linked_sub_kpis:
                    df = pd.DataFrame(linked_sub_kpis)
                    st.dataframe(df[['id', 'indicator_name', 'distribution_weight']])
                else:
                    st.info("No sub-KPIs linked to this master.")

                # --- Form to add new link ---
                with st.form("link_form"):
                    st.subheader("Link a new Sub-KPI")
                    existing_links = db_retriever.get_all_master_sub_kpi_links()
                    linked_kpi_ids = {link['master_kpi_spec_id'] for link in existing_links} | {link['sub_kpi_spec_id'] for link in existing_links}
                    
                    available_sub_kpis = [kpi for kpi in all_kpis if kpi["id"] != selected_kpi_id and kpi["id"] not in linked_kpi_ids]
                    available_sub_kpi_names = [get_kpi_display_name(kpi) for kpi in available_sub_kpis]
                    
                    selected_sub_kpi_to_link_name = st.selectbox("Available Sub-KPIs", available_sub_kpi_names)
                    weight = st.number_input("Distribution Weight", min_value=0.1, value=1.0, step=0.1)

                    submitted = st.form_submit_button("Link KPI")
                    if submitted:
                        sub_kpi_to_link = next((kpi for kpi in available_sub_kpis if get_kpi_display_name(kpi) == selected_sub_kpi_to_link_name), None)
                        if sub_kpi_to_link:
                            try:
                                kpi_links_manager.link_sub_kpi(selected_kpi_id, sub_kpi_to_link['id'], weight)
                                st.success("KPI linked successfully.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error linking KPI: {e}")

            elif role_details['role'] == 'sub':
                st.subheader("Is Sub-KPI of:")
                master_kpi = db_retriever.get_kpi_detailed_by_id(role_details['master_id'])
                if master_kpi:
                    st.write(get_kpi_display_name(master_kpi))

            else: # Role is None
                st.info("This KPI is not currently part of a master-sub relationship.")