# API Documentation

## Core Modules

### 1. Target Management API

#### 1.1 Annual Target Management
```python
from target_management import annual

def save_annual_targets(year: int, stabilimento_id: int, targets_data_map: dict) -> None:
    """Save annual targets and trigger distribution calculations.
    
    Args:
        year: Target year
        stabilimento_id: Facility ID
        targets_data_map: Dictionary mapping KPI IDs to target data
        
    Example:
        targets_data = {
            "1": {
                "annual_target1": 1000,
                "annual_target2": 1200,
                "distribution_profile": "PROFILE_EVEN",
                "repartition_logic": "REPARTITION_LOGIC_MESE"
            }
        }
    """

def get_annual_target(stabilimento_id: int, kpi_id: int, year: int) -> dict:
    """Retrieve annual target data for a specific KPI."""

def calculate_period_targets(annual_target: float, profile: str, params: dict) -> dict:
    """Calculate period-specific targets using selected profile."""
```

#### 1.2 Distribution Profiles
```python
from target_management import repartition

def get_weighted_proportions(num_periods: int, initial_factor: float, 
                           final_factor: float, decreasing: bool = False) -> List[float]:
    """Generate progressive/regressive weights."""

def get_sinusoidal_proportions(num_periods: int, amplitude: float, 
                             phase_offset: float) -> List[float]:
    """Generate sinusoidal distribution weights."""

def get_parabolic_proportions(num_periods: int, peak_at_center: bool = True) -> List[float]:
    """Generate parabolic distribution weights."""
```

### 2. KPI Management API

#### 2.1 Template Management
```python
from kpi_management import templates

def create_template(name: str, description: str, calculation_type: str, 
                   base_unit: str) -> int:
    """Create new KPI template."""

def get_template(template_id: int) -> dict:
    """Retrieve template details."""

def update_template(template_id: int, **kwargs) -> None:
    """Update existing template."""
```

#### 2.2 KPI Specifications
```python
from kpi_management import specifications

def create_kpi(template_id: int, description: str, unit: str, 
               calculation_type: str = None) -> int:
    """Create new KPI specification."""

def link_master_sub(master_id: int, sub_id: int, weight: float) -> None:
    """Create master/sub KPI relationship."""

def get_kpi_hierarchy(kpi_id: int) -> dict:
    """Get KPI's position in hierarchy."""
```

### 3. Data Access API

#### 3.1 Database Operations
```python
from db_core import database_manager

def get_connection(db_name: str) -> sqlite3.Connection:
    """Get database connection with proper configuration."""

def execute_query(query: str, params: tuple = None, 
                 db_name: str = None) -> List[sqlite3.Row]:
    """Execute SQL query with error handling."""

def begin_transaction(db_name: str = None) -> None:
    """Start database transaction."""
```

#### 3.2 Data Retrieval
```python
from data_retriever import db_retriever

def get_all_kpis(visible_only: bool = True) -> List[dict]:
    """Retrieve all KPI specifications."""

def get_period_values(kpi_id: int, stabilimento_id: int, 
                     start_date: date, end_date: date) -> List[dict]:
    """Get target values for a date range."""

def get_actual_values(kpi_id: int, stabilimento_id: int,
                     start_date: date, end_date: date) -> List[dict]:
    """Get actual values for comparison."""
```

### 4. Export Management API

#### 4.1 CSV Export
```python
from export_manager import csv_export

def export_targets(year: int, stabilimento_id: int, 
                  format: str = 'csv') -> str:
    """Export target data to CSV."""

def export_kpi_dictionary(format: str = 'csv') -> str:
    """Export KPI definitions and relationships."""
```

#### 4.2 Excel Export
```python
from export_manager import excel_export

def export_analysis(start_date: date, end_date: date, 
                   kpi_ids: List[int], format: str = 'xlsx') -> str:
    """Export analysis data to Excel."""

def export_templates(format: str = 'xlsx') -> str:
    """Export template definitions."""
```

## Event System

### 1. Event Types
```python
from events import EventType

class EventType(Enum):
    TARGET_UPDATED = "target_updated"
    KPI_CREATED = "kpi_created"
    DISTRIBUTION_CHANGED = "distribution_changed"
    CALCULATION_COMPLETED = "calculation_completed"
```

### 2. Event Handling
```python
from events import event_manager

def subscribe(event_type: EventType, handler: Callable) -> None:
    """Subscribe to event notifications."""

def publish(event_type: EventType, data: dict) -> None:
    """Publish event to all subscribers."""
```

## Configuration API

### 1. Settings Management
```python
from app_config import settings

def get_setting(key: str, default: Any = None) -> Any:
    """Retrieve configuration setting."""

def update_setting(key: str, value: Any) -> None:
    """Update configuration setting."""
```

### 2. Profile Configuration
```python
from target_management.profiles import profile_config

def register_profile(name: str, weight_function: Callable) -> None:
    """Register new distribution profile."""

def get_profile_params(profile_name: str) -> dict:
    """Get profile parameters."""
```

## Utility Functions

### 1. Formula Evaluation
```python
from utils import formula_evaluator

def evaluate_formula(formula: str, context: dict) -> float:
    """Safely evaluate formula with context."""

def validate_formula(formula: str) -> bool:
    """Check formula syntax and security."""
```

### 2. Date Handling
```python
from utils import date_utils

def get_period_dates(year: int, period_type: str) -> List[tuple]:
    """Get start/end dates for periods."""

def is_valid_period(start_date: date, end_date: date, 
                   period_type: str) -> bool:
    """Validate period boundaries."""
```

## See Also

- [Theoretical Framework](theoretical_framework.md)
- [Target Generation](target_generation.md)
- [Database Schema](database_schema.md)
- [Configuration Guide](configuration.md)
- [GUI Logic](GUI's%20logic.txt)
