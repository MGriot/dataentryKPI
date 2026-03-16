from src.export_manager import export_all_data_to_global_csvs, package_all_csvs_as_zip
from src.import_manager import import_from_zip
from pathlib import Path
import os

# 1. Export
print("Testing Export...")
export_all_data_to_global_csvs("test_exports")

# 2. Package
print("\nTesting Zip Packaging...")
success, message = package_all_csvs_as_zip("test_exports", "test_backup.zip")
print(f"Success: {success}, Message: {message}")

# 3. Import (Restore)
if success:
    print("\nTesting Import (Restore)...")
    result = import_from_zip("test_backup.zip")
    print(f"Result: {result}")

# Cleanup (optional, but good to keep for now to inspect)
# for f in Path("test_exports").glob("*"): f.unlink()
# Path("test_exports").rmdir()
# Path("test_backup.zip").unlink()
