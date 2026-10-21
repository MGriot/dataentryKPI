# src/import_manager.py
"""
Restore from a raw backup ZIP (export_manager.build_backup_zip).

Restore REPLACES the contents of every table present in the backup, in one transaction
across all databases, after taking a file-level snapshot of the current databases under
<db dir>/backups/pre-restore-<timestamp>/. Tables missing from the backup (e.g. older
backups without units/history) are left untouched. User accounts are never touched.

The ZIP is validated before anything is written: only known file names, bounded
uncompressed size, and every CSV column must exist in the target table.
"""
import csv
import datetime
import io
import logging
import sqlite3
import zipfile
from typing import Dict, List

from src.data_access import db
from src.data_access.setup import setup_databases
from src.export_manager import MANIFEST_NAME, NULL_TOKEN, RAW_BACKUP_TABLES

log = logging.getLogger(__name__)

DEFAULT_MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
_RESTORE_DATABASES = sorted({db_name for _, db_name, _ in RAW_BACKUP_TABLES})


class RestoreError(ValueError):
    pass


def _alias(db_name: str) -> str:
    return "r_" + db_name.replace(".db", "")


def _read_backup(zip_bytes: bytes, max_uncompressed_bytes: int) -> Dict[str, dict]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise RestoreError("The uploaded file is not a valid ZIP archive.") from None
    known = {csv_name: (table, db_name) for table, db_name, csv_name in RAW_BACKUP_TABLES}
    with zf:
        infos = zf.infolist()
        unexpected = [i.filename for i in infos if i.filename not in known and i.filename != MANIFEST_NAME]
        if unexpected:
            raise RestoreError(f"Unexpected files in backup: {', '.join(sorted(unexpected)[:5])}")
        if sum(i.file_size for i in infos) > max_uncompressed_bytes:
            raise RestoreError("Backup is too large once uncompressed.")
        present = [i for i in infos if i.filename in known]
        if not present:
            raise RestoreError("No backup tables found in the ZIP (expected raw_*.csv files).")

        parsed = {}
        for info in present:
            table, db_name = known[info.filename]
            text = zf.read(info).decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text))
            try:
                header = next(reader)
            except StopIteration:
                continue
            parsed[table] = {"db": db_name, "header": header, "rows": list(reader)}
    return parsed


def _coerce(value: str, column: dict):
    """CSV text -> SQL value. \\N is NULL; '' is NULL for nullable/numeric columns (older backups)."""
    if value == NULL_TOKEN:
        return None
    col_type = (column["type"] or "").upper()
    numeric = any(t in col_type for t in ("INT", "REAL", "FLOA", "DOUB", "NUM", "BOOL"))
    if value == "" and (numeric or not column["notnull"]):
        return None
    return value


def _snapshot_databases() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = db.path(db.KPIS).parent / "backups" / f"pre-restore-{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    for db_name in db.ALL_DATABASES:
        if db_name == db.USERS or not db.path(db_name).exists():
            continue
        src = sqlite3.connect(db.path(db_name))
        dst = sqlite3.connect(target / db_name)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    return str(target)


def restore_from_zip(zip_bytes: bytes, max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES) -> dict:
    """Validates and restores a backup. Returns {'tables': {table: rows}, 'snapshot': path, 'warnings': [...]}"""
    backup = _read_backup(zip_bytes, max_uncompressed_bytes)
    setup_databases()  # make sure every target table exists with the current schema

    main_db = _RESTORE_DATABASES[0]
    attach = {_alias(d): d for d in _RESTORE_DATABASES if d != main_db}
    restored: Dict[str, int] = {}
    warnings: List[str] = []

    # Validate columns against the live schema before touching anything.
    with db.connect(main_db, attach=attach) as conn:
        for table, item in backup.items():
            schema = "main" if item["db"] == main_db else _alias(item["db"])
            columns = {c["name"]: c for c in conn.execute(f"PRAGMA {schema}.table_info({db.ident(table)})")}
            unknown = [c for c in item["header"] if c not in columns]
            if unknown:
                raise RestoreError(f"Backup table '{table}' has columns this version doesn't know: {', '.join(unknown)}")
            item["schema"], item["columns"] = schema, columns

    snapshot = _snapshot_databases()

    with db.connect(main_db, attach=attach, foreign_keys=False) as conn:
        for table, _, _ in RAW_BACKUP_TABLES:  # parents before children
            item = backup.get(table)
            if not item:
                continue
            target = f"{item['schema']}.{db.ident(table)}"
            header = item["header"]
            conn.execute(f"DELETE FROM {target}")
            if header:
                cols = [item["columns"][c] for c in header]
                placeholders = ", ".join("?" * len(header))
                values = []
                for line_no, row in enumerate(item["rows"], start=2):
                    if len(row) != len(header):
                        raise RestoreError(f"{table}: line {line_no} has {len(row)} values, expected {len(header)}")
                    values.append([_coerce(v, c) for v, c in zip(row, cols)])
                try:
                    conn.executemany(
                        f"INSERT INTO {target} ({', '.join(db.ident(c) for c in header)}) VALUES ({placeholders})", values
                    )
                except sqlite3.IntegrityError as e:
                    raise RestoreError(f"{table}: {e}") from None
            restored[table] = len(item["rows"])
        for schema in ["main", *attach]:
            violations = conn.execute(f"PRAGMA {schema}.foreign_key_check").fetchall()
            if violations:
                warnings.append(f"{len(violations)} row(s) in {schema} reference missing parents")

    setup_databases()  # normalize legacy values (calc types, is_calculated, ...)
    log.info("Restored %s tables from backup (snapshot at %s)", len(restored), snapshot)
    return {"tables": restored, "snapshot": snapshot, "warnings": warnings}
