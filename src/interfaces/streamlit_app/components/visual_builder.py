import streamlit as st
import streamlit.components.v1 as components
import os
import json

# Ensure we use an absolute path for the component directory
_parent_dir = os.path.dirname(os.path.abspath(__file__))
_build_dir = os.path.join(_parent_dir, "frontend")

# Create the component function
_visual_node_editor = components.declare_component("kpi_graph_editor", path=_build_dir)

def visual_node_editor(initial_json, kpi_list, key=None):
    """
    A visual KPI Formula Editor component for Streamlit.
    """
    if not initial_json:
        initial_json = '{"nodes": [], "edges": []}'
    
    if not isinstance(initial_json, str):
        initial_json = json.dumps(initial_json)

    return _visual_node_editor(
        initial_json=initial_json, 
        kpi_list=kpi_list, 
        default=initial_json, 
        height=720,
        key=key
    )
