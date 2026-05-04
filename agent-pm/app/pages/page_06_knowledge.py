"""Page 6: Knowledge Base Management."""

import streamlit as st
import pandas as pd
import os

# Get the path to the app directory
APP_DIR = os.path.dirname(os.path.dirname(__file__))

def render():
    st.markdown("## 📚 Knowledge Base Management")
    st.markdown(
        "Manage the libraries that ground the agent's logic. You can view, edit, or upload "
        "custom knowledge base files."
    )

    tabs = st.tabs(["Production Rates", "Construction Logic", "Procurement Leads", "Building Typologies"])

    # 1. Production Rates
    with tabs[0]:
        st.markdown("#### Production Rates Library")
        path = os.path.join(APP_DIR, "libraries", "production_rates.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            st.dataframe(df, use_container_width=True)
            
            st.markdown("##### Upload Custom Rates")
            uploaded_file = st.file_uploader("Upload CSV", type="csv", key="up_rates")
            if uploaded_file is not None:
                new_df = pd.read_csv(uploaded_file)
                if st.button("💾 Save & Overwrite Library Rates"):
                    new_df.to_csv(path, index=False)
                    st.success("Library updated successfully!")
        else:
            st.error("Production rates library not found.")

    # 2. Construction Logic
    with tabs[1]:
        st.markdown("#### Construction Logic Rules")
        path = os.path.join(APP_DIR, "libraries", "construction_logic.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            st.dataframe(df, use_container_width=True)
            
            st.markdown("##### Upload Custom Rules")
            uploaded_file = st.file_uploader("Upload CSV", type="csv", key="up_logic")
            if uploaded_file is not None:
                new_df = pd.read_csv(uploaded_file)
                if st.button("💾 Save & Overwrite Library Rules"):
                    new_df.to_csv(path, index=False)
                    st.success("Library updated successfully!")

    # 3. Procurement Leads
    with tabs[2]:
        st.markdown("#### Procurement Lead Times")
        path = os.path.join(APP_DIR, "libraries", "procurement_leads.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            st.dataframe(df, use_container_width=True)
            
            st.markdown("##### Upload Custom Leads")
            uploaded_file = st.file_uploader("Upload CSV", type="csv", key="up_proc")
            if uploaded_file is not None:
                new_df = pd.read_csv(uploaded_file)
                if st.button("💾 Save & Overwrite Library Leads"):
                    new_df.to_csv(path, index=False)
                    st.success("Library updated successfully!")

    # 4. Building Typologies
    with tabs[3]:
        st.markdown("#### Building Typologies")
        path = os.path.join(APP_DIR, "libraries", "typologies.json")
        if os.path.exists(path):
            import json
            with open(path) as f:
                data = json.load(f)
            table_data = []
            for key, val in data.items():
                table_data.append({
                    "Typology ID": key,
                    "Name": val.get("name", ""),
                    "Description": val.get("description", ""),
                    "Default GFA (m²)": val.get("default_gfa_m2", ""),
                    "Storeys": val.get("default_storeys", ""),
                    "System": val.get("default_structural_system", "")
                })
            st.dataframe(pd.DataFrame(table_data), use_container_width=True)
            
            st.markdown("##### Upload Custom Typologies")
            uploaded_file = st.file_uploader("Upload JSON", type="json", key="up_typology")
            if uploaded_file is not None:
                new_data = json.load(uploaded_file)
                if st.button("💾 Save & Overwrite Typology Library"):
                    with open(path, 'w') as f:
                        json.dump(new_data, f, indent=4)
                    st.success("Library updated successfully!")
