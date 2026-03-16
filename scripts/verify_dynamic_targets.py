import sqlite3
import json
from src.target_management.annual import save_annual_targets
from src.data_retriever import get_annual_target_entry
from src.data_access.setup import setup_databases

def test_dynamic_targets():
    print("Testing Dynamic Targets (T3+)...")
    setup_databases()
    
    year = 2026
    plant_id = 1
    kpi_id = 1 # Assume KPI 1 exists
    
    # Data with 3 targets
    targets_data = {
        str(kpi_id): {
            "targets": [
                {"target_number": 1, "target_value": 100.0, "is_manual": True},
                {"target_number": 2, "target_value": 200.0, "is_manual": True},
                {"target_number": 3, "target_value": 300.0, "is_manual": True}
            ]
        }
    }
    
    save_annual_targets(year, plant_id, targets_data)
    
    # Verify retrieval
    entry = get_annual_target_entry(year, plant_id, kpi_id)
    print(f"Retrieved Entry for KPI {kpi_id}:")
    for tv in entry.get('target_values', []):
        print(f"  Target {tv['target_number']}: {tv['target_value']}")
    
    target_nums = [tv['target_number'] for tv in entry.get('target_values', [])]
    assert 1 in target_nums
    assert 2 in target_nums
    assert 3 in target_nums
    
    t3 = next(tv for tv in entry['target_values'] if tv['target_number'] == 3)
    assert t3['target_value'] == 300.0
    
    print("Dynamic Targets Verified!")

if __name__ == "__main__":
    try:
        test_dynamic_targets()
    except Exception as e:
        print(f"Test FAILED: {e}")
        import traceback
        traceback.print_exc()
