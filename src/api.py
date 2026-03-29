# src/api.py
from fastapi import FastAPI
from src import data_retriever
from typing import List, Optional

app = FastAPI(title="dataentryKPI API", description="External data connection for KPI targets")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/targets/lean")
def get_lean_targets():
    """Returns a minimal, high-portability list of target data for BI tools."""
    return data_retriever.get_lean_targets()

@app.get("/kpis")
def get_kpis():
    """Returns all KPI specifications."""
    return data_retriever.get_all_kpis_detailed()

@app.get("/plants")
def get_plants():
    """Returns all plants."""
    return data_retriever.get_all_plants()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
