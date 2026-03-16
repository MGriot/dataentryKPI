# [TARGET-002-SERVICE] · Update service layer for dynamic targets

**Timestamp**: 2026-03-16 22:50 Local Time  
**Author**: Ralph  

## Why
The backend logic was hardcoded for exactly two targets (Target 1 and Target 2). To fulfill the requirement of allowing users to add targets at their discretion, the service layer needed to be generalized.

## What Changed
- `src/data_retriever.py`: Updated `get_annual_target_entry` and `get_annual_targets` to fetch data from the new `kpi_annual_target_values` table. Added `get_kpi_annual_target_values` helper. Maintained backward compatibility for Target 1 and Target 2.
- `src/target_management/annual.py`: Refactored `_save_single_plant_annual_targets` to handle an arbitrary number of targets. Updated formula calculation and master/sub distribution logic to iterate over all present target numbers.
- `src/target_management/repartition.py`: Updated `calculate_and_save_all_repartitions` to use the normalized target data.

## Verification
**Command**: `python scripts/verify_dynamic_targets.py`
**Result**: PASSED ✅
**Output**:
```
Retrieved Entry for KPI 1:
  Target 1: 100.0
  Target 2: 200.0
  Target 3: 300.0
Dynamic Targets Verified!
```

## Notes
The `save_annual_targets` function now accepts a `targets` list in the data map, allowing for T3, T4, etc. Formula evaluation now correctly handles dependencies across different target numbers.
