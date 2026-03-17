# [BI-DIRECTIONAL] · Formula-Node Bi-directional Conversion

**Timestamp**: 2026-03-17 01:30 Local Time  
**Author**: Ralph  

## Why
Users need the flexibility to switch between visual node-based modeling and textual formula editing. Bi-directional conversion ensures that the visual representation and the underlying execution string remain synchronized, allowing for easier debugging and formula portability.

## What Changed
- `src/core/node_engine.py`:
    - Added `to_formula()` method to the `KpiDAG` class.
    - Implemented `_to_formula_recursive()` to perform a post-order traversal of the DAG, starting from the `output` node.
    - Added logic to map DAG nodes to Python-like operators (`+`, `-`, `*`, `/`, `**`) and functions (`min`, `max`, `avg`).
    - Handled `[ID]` syntax for KPI inputs to maintain consistency with the calculation engine.

## Verification
**Command**: `python scripts/verify_bidirectional.py`
**Result**: PASSED ✅
**Observation**: A complex DAG with subtractions and multiplications was correctly converted to the string `(([10] - [20]) * 1.2)`. Evaluation results from both the DAG and the generated formula were identical (72.0).
