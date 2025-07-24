# Configuration Guide

## Overview

The Data Entry KPI system is highly configurable through various settings and parameters. This guide covers all configuration options and their effects.

## Configuration Files

### 1. settings.json

Primary configuration file located in the root directory:

```json
{
  "display_names": {
    "target1": "Budget",
    "target2": "Forecast"
  },
  "database": {
    "path": "databases/",
    "backup_path": "backups/"
  },
  "export": {
    "csv_path": "csv_exports/",
    "date_format": "%Y-%m-%d"
  },
  "ui": {
    "theme": "light",
    "language": "it"
  }
}
```

### 2. Environment Variables

Optional environment variables for overriding settings:

```bash
DATAENTRY_DB_PATH=custom/path/to/db
DATAENTRY_EXPORT_PATH=custom/path/to/exports
DATAENTRY_LOG_LEVEL=DEBUG
```

## Database Configuration

### 1. Connection Settings
```python
# src/db_core/setup.py
DB_CONFIG = {
    'timeout': 30,
    'isolation_level': None,  # Autocommit mode
    'check_same_thread': False
}
```

### 2. Backup Configuration
```python
BACKUP_CONFIG = {
    'interval': 24*60*60,  # Daily
    'keep_days': 30,       # Keep 30 days of backups
    'compress': True       # Use compression
}
```

## Distribution Profiles

### 1. Profile Parameters

```python
# src/target_management/repartition.py
PROFILE_PARAMS = {
    'EVEN': {},
    'ANNUAL_PROGRESSIVE': {
        'weight_initial': 0.5,
        'weight_final': 1.5
    },
    'SINUSOIDAL': {
        'amplitude': 0.5,
        'phase_offset': 0
    }
}
```

### 2. Custom Profiles

To add a new profile:

1. Define the profile function:
```python
def custom_profile(params):
    def weight_function(i, n):
        # Calculate weights
        return weight
    return weight_function
```

2. Register in PROFILES:
```python
PROFILES['CUSTOM'] = custom_profile
```

## Logging Configuration

### 1. File Logging

```python
# src/logging_config.py
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/app.log',
            'formatter': 'detailed'
        }
    },
    'loggers': {
        'dataentry': {
            'handlers': ['file'],
            'level': 'INFO'
        }
    }
}
```

### 2. Log Rotation

```python
# logging_config.py
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=1024*1024,  # 1MB
    backupCount=5
)
```

## UI Configuration

### 1. Tkinter Settings

```python
# src/gui/app_tkinter/config.py
TKINTER_CONFIG = {
    'geometry': '1024x768',
    'min_size': (800, 600),
    'theme': 'clam',
    'font': ('Helvetica', 10)
}
```

### 2. Streamlit Settings

```toml
# .streamlit/config.toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[server]
port = 8501
address = "localhost"
```

## Export Configuration

### 1. CSV Export

```python
CSV_EXPORT_CONFIG = {
    'delimiter': ',',
    'quoting': csv.QUOTE_MINIMAL,
    'date_format': '%Y-%m-%d',
    'encoding': 'utf-8-sig'  # With BOM for Excel
}
```

### 2. Excel Export

```python
EXCEL_EXPORT_CONFIG = {
    'date_format': 'YYYY-MM-DD',
    'sheet_name': 'KPI_Data',
    'freeze_panes': (1, 0)
}
```

## Performance Tuning

### 1. Database Optimization

```python
DB_PERFORMANCE = {
    'pragma_temp_store': 2,      # Memory-based temp storage
    'pragma_cache_size': -2000,  # 2MB cache
    'pragma_journal_mode': 'WAL' # Write-Ahead Logging
}
```

### 2. Application Settings

```python
APP_PERFORMANCE = {
    'batch_size': 1000,         # Batch processing size
    'cache_timeout': 300,       # Cache timeout (seconds)
    'max_workers': 4            # Thread pool size
}
```

## Security Settings

### 1. Formula Evaluation

```python
FORMULA_SECURITY = {
    'allowed_functions': [
        'sum', 'avg', 'min', 'max',
        'round', 'ceil', 'floor'
    ],
    'max_iterations': 100,
    'timeout': 5  # seconds
}
```

### 2. Input Validation

```python
VALIDATION_RULES = {
    'max_formula_length': 1000,
    'max_target_value': 1e9,
    'min_target_value': -1e9
}
```

## See Also

- [Architecture Overview](architecture.md) for system design
- [Database Schema](database_schema.md) for database settings
- [Target Generation](target_generation.md) for distribution settings
