# test_splits_crud.py
from src.kpi_management.splits import add_global_split, update_global_split, delete_global_split, get_global_split, get_all_global_splits
from src.interfaces.common_ui.constants import REPARTITION_LOGIC_YEAR, PROFILE_ANNUAL_PROGRESSIVE
import os

def test_splits():
    print("Testing Global Splits CRUD...")
    
    # 1. Add
    name = "Test Split 2026"
    year = 2026
    split_id = add_global_split(
        name=name,
        year=year,
        repartition_logic=REPARTITION_LOGIC_YEAR,
        repartition_values={"Jan": 0.1, "Feb": 0.9},
        distribution_profile=PROFILE_ANNUAL_PROGRESSIVE,
        profile_params={}
    )
    print(f"Added split with ID: {split_id}")
    
    # 2. Get
    split = get_global_split(split_id)
    assert split['name'] == name
    assert split['repartition_values'] == {"Jan": 0.1, "Feb": 0.9}
    print("Get verified.")
    
    # 3. Update
    update_global_split(split_id, name="Updated Test Split 2026")
    split = get_global_split(split_id)
    assert split['name'] == "Updated Test Split 2026"
    print("Update verified.")
    
    # 4. Get All
    all_splits = get_all_global_splits(year=2026)
    assert len(all_splits) >= 1
    print(f"Get all verified. Found {len(all_splits)} splits for 2026.")
    
    # 5. Delete
    delete_global_split(split_id)
    split = get_global_split(split_id)
    assert split is None
    print("Delete verified.")
    
    print("All tests passed!")

if __name__ == "__main__":
    test_splits()
