# test_global_repartition.py
import sqlite3
import json
from src.target_management.repartition import calculate_and_save_all_repartitions
from src.kpi_management.splits import add_global_split
from src.config import settings as app_config

def test_global_repartition():
    print("Testing Global Repartition Logic...")
    
    year = 2026
    plant_id = 1
    kpi_id = 1
    target_num = 1
    
    # 1. Create a Global Split Template
    # Let's say we want 100% in January, 0% elsewhere.
    repart_values = {"January": 100.0}
    for m in ["February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        repart_values[m] = 0.0
        
    import time
    unique_name = f"January Only {int(time.time())}"
    split_id = add_global_split(
        name=unique_name,
        year=year,
        repartition_logic=app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_MONTH"],
        repartition_values=repart_values,
        distribution_profile=app_config.CALCULATION_CONSTANTS["PROFILE_EVEN"],
        profile_params={}
    )
    print(f"Created Global Split ID: {split_id}")
    
    # 2. Assign this split to an annual target
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    with sqlite3.connect(db_targets_path) as conn:
        # Ensure target entry exists
        conn.execute(
            """INSERT OR REPLACE INTO annual_targets 
               (year, plant_id, kpi_id, annual_target1, global_split_id) 
               VALUES (?, ?, ?, ?, ?)""",
            (year, plant_id, kpi_id, 1200.0, split_id)
        )
        conn.commit()
    print(f"Assigned Split ID {split_id} to KPI {kpi_id} for {year}")
    
    # 3. Trigger Repartition
    calculate_and_save_all_repartitions(year, plant_id, kpi_id, target_num)
    
    # 4. Verify results in monthly_targets
    db_months_path = app_config.get_database_path("db_kpi_months.db")
    with sqlite3.connect(db_months_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM monthly_targets WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?",
            (year, plant_id, kpi_id, target_num)
        ).fetchall()
        
        month_data = {row['month_value']: row['target_value'] for row in rows}
        print(f"Monthly Data: {month_data}")
        
        assert abs(month_data['January'] - 1200.0) < 1e-9
        assert abs(month_data['February'] - 0.0) < 1e-9
        print("Global Repartition Logic Verified!")

if __name__ == "__main__":
    test_global_repartition()
