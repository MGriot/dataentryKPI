# Streamlit Web Interface Guide

## Overview

The Streamlit interface provides a modern, web-based approach to KPI management with real-time updates and interactive features.

## Quick Start

### 1. Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py streamlit
```

### 2. Access
Open your browser to:
- Default: http://localhost:8501
- Network: http://[your-ip]:8501

## Features

### 1. Target Entry (🎯)

#### Basic Target Input
1. Select year from dropdown
2. Choose stabilimento
3. For each KPI:
   - Enter Target 1
   - Enter Target 2
   - Configure distribution

#### Formula-Based Targets
1. Enable "Usa Formula"
2. Enter formula:
   ```python
   previous_year * 1.1  # 10% increase
   related_kpi * 0.5    # 50% of related KPI
   ```

#### Distribution Setup
1. Select "Logica di Riparto":
   - ANNO (Annual)
   - MESE (Monthly)
   - TRIMESTRE (Quarterly)
   - SETTIMANA (Weekly)

2. Choose "Profilo di Distribuzione":
   - Even
   - Progressive
   - Sinusoidal
   - More...

### 2. KPI Management

#### Template Setup
1. Navigate to KPI Templates
2. Configure:
   - Name
   - Description
   - Calculation type
   - Base unit

#### KPI Configuration
1. Create from template
2. Set:
   - Description
   - Unit
   - Visibility
   - Calculation method

#### Hierarchy Setup
1. Define master KPIs
2. Add sub-KPIs
3. Configure weights
4. Set distribution rules

### 3. Analysis & Reporting

#### Data Visualization
- Historical trends
- Target vs Actual
- Period comparisons
- Custom charts

#### Export Options
1. CSV Export
   - All targets
   - Selected periods
   - Custom format

2. Excel Export
   - Formatted reports
   - Multiple sheets
   - Chart inclusion

## Advanced Features

### 1. Formula Variables
```python
# Available variables
previous_year    # Previous year's value
ytd_actual      # Year-to-date actual
related_kpi     # Other KPI values
```

### 2. Distribution Profiles

#### Progressive
- Initial weight
- Final weight
- Direction (increasing/decreasing)

#### Sinusoidal
- Amplitude (0-1)
- Phase offset
- Period count

### 3. Data Validation

The system automatically validates:
- Formula syntax
- Weight distributions (sum to 100%)
- Period consistency
- Value ranges

## Best Practices

### 1. Target Entry
- Enter annual targets first
- Verify distributions
- Save frequently
- Document changes

### 2. Formula Usage
- Test with sample data
- Keep formulas simple
- Document dependencies
- Handle edge cases

### 3. Distribution Setup
- Match business patterns
- Consider seasonality
- Review historical data
- Document choices

## Troubleshooting

### 1. Common Issues

#### "Formula Error"
- Check syntax
- Verify variables
- Review dependencies

#### "Invalid Distribution"
- Verify weights sum to 100%
- Check for negative values
- Validate period setup

#### "Save Failed"
- Check required fields
- Verify permissions
- Review validation rules

### 2. Performance Tips

#### Large Datasets
- Use date filters
- Export in batches
- Clear cache if needed

#### Slow Calculations
- Simplify formulas
- Reduce dependencies
- Use appropriate profiles

## See Also

- [Theoretical Framework](theoretical_framework.md)
- [Target Generation](target_generation.md)
- [API Reference](api_reference.md)
- [Configuration Guide](configuration.md)

## Features

-   **Modern Web UI:**
    Manage KPIs, targets, and results via an interactive web interface.

-   **Target Entry:**
    Enter and distribute annual targets with real-time feedback, including advanced options for formula-based targets and detailed repartition profiles.

-   **KPI & Template Management:**
    Full CRUD for groups, subgroups, indicators, and templates.

-   **Results & Export/Import:**
    Visualize distributed targets and download/upload all data (CSV/ZIP).

## See Also

-   [Automatic Target Generation Logic](target_generation.md)
-   [Architecture Overview](architecture.md)
