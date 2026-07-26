# src/api.py
import json
import tempfile
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from src import data_retriever
from src.kpi_management import crud as kpi_crud
from src.kpi_management import splits as splits_crud
from src.kpi_management import templates as templates_crud
from src.kpi_management import visibility as visibility_crud
from src.plants_management import crud as plants_crud
from src.target_management import annual as annual_management
from src.target_management import repartition as repartition_module
from src.services import actuals_service, history_service, split_analyzer
from src import export_manager, import_manager
from src.config import settings as app_config
from src.data_access.setup import setup_databases
from src.user_management import crud as user_crud

app = FastAPI(title="Data Entry KPI Target Manager API", description="Consolidated REST API & Backend Services for KPI targets, actuals, performance, and history.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _run_db_migrations():
    """Ensures database schema is up to date (same migration used by the Tkinter/Streamlit apps)."""
    setup_databases()

# --- Auth gate ---
# Every route requires a valid session (Authorization: Bearer <token>, minted by POST /auth/login or
# /auth/register) except this small allowlist. This is what makes "must log in before entering or
# modifying anything" actually true at the API layer, not just a client-side UI gate.
# NOTE: only register/login/logout are exempt -- /auth/me and /auth/change-password still need a
# validated session (they use Depends(get_current_user), which reads request.state.user, which only
# the branch below sets).
_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/auth/register", "/auth/login", "/auth/logout"}

@app.middleware("http")
async def _require_session(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)  # CORS preflight never carries Authorization
    path = request.url.path
    if path in _PUBLIC_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
    user = user_crud.validate_session(raw_token) if raw_token else None
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated. Log in via POST /auth/login."})

    request.state.user = user
    return await call_next(request)

def get_current_user(request: Request) -> dict:
    """Typed accessor for the user the _require_session middleware already authenticated."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# --- Pydantic Data Models ---
class ActualMeasurementRequest(BaseModel):
    kpi_id: int
    plant_id: int
    measurement_date: str
    actual_value: float

class TargetUpdateRequest(BaseModel):
    kpi_id: int
    plant_id: int
    target_number: int
    period_start: str
    period_end: str
    target_value: float

class KPIIndicatorCreateRequest(BaseModel):
    node_id: int
    name: str
    description: Optional[str] = None
    calculation_type: Optional[str] = "Sum"
    unit_of_measure: Optional[str] = None
    visible: Optional[bool] = True
    owner: Optional[str] = None
    direction: Optional[str] = "Higher is Better"
    threshold_json: Optional[str] = None
    target_granularity: Optional[str] = "Monthly"
    target_count: Optional[int] = 1
    time_filter_type: Optional[str] = "None"
    time_filter_value: Optional[str] = None

class KPINodeCreateRequest(BaseModel):
    parent_id: Optional[int] = None
    name: str
    custom_level_label: Optional[str] = None

class KPISpecUpdateRequest(BaseModel):
    data_updates: Dict[str, Any]

class UnitOfMeasureCreateRequest(BaseModel):
    name: str

class KpiGlobalSplitAssignRequest(BaseModel):
    global_split_id: Optional[int] = None

class PlantCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    visible: bool = True
    color: str = "#000000"

class PlantUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    visible: bool = True
    color: str = "#000000"

class VisibilityEntry(BaseModel):
    plant_id: int
    is_enabled: bool

class VisibilityUpdateRequest(BaseModel):
    visibility_data: List[VisibilityEntry]

class GlobalSplitCreateRequest(BaseModel):
    name: str
    repartition_logic: str
    repartition_values: Dict[str, Any] = {}
    distribution_profile: str
    profile_params: Dict[str, Any] = {}
    years: Optional[List[int]] = None
    afflicted_indicators: Optional[List[Dict[str, Any]]] = None

class GlobalSplitUpdateRequest(BaseModel):
    name: Optional[str] = None
    repartition_logic: Optional[str] = None
    repartition_values: Optional[Dict[str, Any]] = None
    distribution_profile: Optional[str] = None
    profile_params: Optional[Dict[str, Any]] = None
    years: Optional[List[int]] = None
    afflicted_indicators: Optional[List[Dict[str, Any]]] = None

class GlobalSplitIndicatorsUpdateRequest(BaseModel):
    indicators: List[Dict[str, Any]]

class AnnualTargetValueInput(BaseModel):
    target_number: int
    target_value: Optional[float] = None
    is_manual: bool = True
    is_formula_based: bool = False
    formula: Optional[str] = None
    formula_inputs: Optional[Any] = "[]"

class AnnualTargetKpiInput(BaseModel):
    repartition_logic: Optional[str] = None
    repartition_values: Optional[Dict[str, Any]] = None
    distribution_profile: Optional[str] = None
    profile_params: Optional[Dict[str, Any]] = None
    global_split_id: Optional[int] = None
    targets: List[AnnualTargetValueInput] = []

class SaveAnnualTargetsRequest(BaseModel):
    year: int
    plant_id: Union[int, List[int]]
    targets_data_map: Dict[str, AnnualTargetKpiInput]
    initiator_kpi_spec_id: Optional[int] = None

class TemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class TemplateIndicatorCreateRequest(BaseModel):
    indicator_name_in_template: str
    default_calculation_type: str
    default_unit_of_measure: Optional[str] = None
    default_visible: bool = True
    default_description: Optional[str] = ""

class TemplateIndicatorUpdateRequest(BaseModel):
    template_id: int
    name: str
    calc_type: str
    unit: Optional[str] = None
    visible: bool = True
    description: Optional[str] = ""

class UserCreateRequest(BaseModel):
    name: str
    password: str
    email: Optional[str] = ""
    color: Optional[str] = "#3b82f6"

class UserUpdateRequest(BaseModel):
    name: str
    email: Optional[str] = ""
    color: Optional[str] = "#3b82f6"
    is_active: bool = True

class ApiKeyCreateRequest(BaseModel):
    label: str

class RegisterRequest(BaseModel):
    name: str
    password: str
    email: Optional[str] = ""
    color: Optional[str] = "#3b82f6"

class LoginRequest(BaseModel):
    name: str
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# --- Auth: register / login / logout / me / change-password ---
@app.post("/auth/register")
def register(req: RegisterRequest):
    """Creates a new user account and logs them in immediately (returns a session token)."""
    try:
        user_id = user_crud.add_user(req.name, req.password, req.email or "", req.color or "#3b82f6")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session = user_crud.create_session(user_id)
    user = user_crud.get_user_by_id(user_id)
    return {"token": session["token"], "expires_at": session["expires_at"], "user": user}

@app.post("/auth/login")
def login(req: LoginRequest):
    user = user_crud.verify_password(req.name, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid name or password.")
    session = user_crud.create_session(user["id"])
    return {"token": session["token"], "expires_at": session["expires_at"], "user": user}

@app.post("/auth/logout")
def logout(request: Request):
    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
    user_crud.revoke_session(raw_token)
    return {"status": "success"}

@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.post("/auth/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_crud.change_password(current_user["id"], req.current_password, req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}

@app.get("/targets/lean")
def get_lean_targets():
    """Returns a minimal, high-portability list of target data for BI tools."""
    return data_retriever.get_lean_targets()

@app.get("/kpis")
def get_kpis(only_visible: bool = False, plant_id: Optional[int] = None):
    """Returns detailed KPI specifications."""
    return data_retriever.get_all_kpis_detailed(only_visible=only_visible, plant_id=plant_id)

@app.get("/kpis/tree")
def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = None):
    """Returns recursive KPI hierarchy tree."""
    return kpi_crud.get_kpi_tree(root_id=root_id, depth=depth)

@app.post("/kpis")
def create_kpi(req: KPIIndicatorCreateRequest, current_user: dict = Depends(get_current_user)):
    """Creates a new KPI indicator and spec."""
    return kpi_crud.create_kpi_indicator(
        node_id=req.node_id,
        name=req.name,
        description=req.description,
        calculation_type=req.calculation_type,
        unit_of_measure=req.unit_of_measure,
        visible=req.visible,
        owner=req.owner,
        direction=req.direction,
        threshold_json=req.threshold_json,
        target_granularity=req.target_granularity,
        target_count=req.target_count,
        time_filter_type=req.time_filter_type,
        time_filter_value=req.time_filter_value,
        changed_by=current_user["name"]
    )

@app.post("/kpis/nodes")
def add_kpi_node(req: KPINodeCreateRequest):
    """Creates a new node in the KPI tree hierarchy."""
    node_id = kpi_crud.add_kpi_node(req.parent_id, req.name, req.custom_level_label)
    return {"node_id": node_id, "name": req.name}

@app.delete("/kpis/{kpi_id}")
def soft_delete_kpi(kpi_id: int, current_user: dict = Depends(get_current_user)):
    """Soft deletes a KPI indicator (preserves historical target and actual records)."""
    success = kpi_crud.soft_delete_kpi(kpi_id, changed_by=current_user["name"])
    if not success:
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"status": "success", "kpi_id": kpi_id, "is_active": False}

@app.get("/kpis/{kpi_id}/status")
def get_kpi_status(kpi_id: int, plant_id: int, target_value: Optional[float] = None):
    """Evaluates performance status, actuals time filter, and trend for a KPI."""
    return data_retriever.get_kpi_performance_status(kpi_id=kpi_id, plant_id=plant_id, target_value=target_value)

@app.get("/kpis/{kpi_id}/history")
def get_kpi_history(kpi_id: int):
    """Retrieves definition change audit logs for a KPI."""
    return history_service.get_definition_history(kpi_id)

@app.get("/plants")
def get_plants(visible_only: bool = False):
    """Returns all plants."""
    return data_retriever.get_all_plants(visible_only=visible_only)

@app.post("/actuals")
def record_actual(req: ActualMeasurementRequest):
    """Records an actual measurement for a KPI and plant."""
    row_id = actuals_service.record_actual_measurement(
        kpi_id=req.kpi_id,
        plant_id=req.plant_id,
        measurement_date=req.measurement_date,
        actual_value=req.actual_value
    )
    return {"status": "success", "id": row_id}

@app.get("/actuals")
def get_actuals(kpi_id: int, plant_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Retrieves actual measurement series."""
    return actuals_service.get_actual_measurements(kpi_id, plant_id, start_date, end_date)

@app.post("/targets")
def update_target(req: TargetUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Creates or updates a target value and logs target audit history."""
    success = kpi_crud.update_target_value(
        plant_id=req.plant_id,
        kpi_id=req.kpi_id,
        target_number=req.target_number,
        period_start=req.period_start,
        period_end=req.period_end,
        target_value=req.target_value,
        changed_by=current_user["name"]
    )
    return {"status": "success", "updated": success}

@app.get("/targets")
def get_targets(kpi_id: Optional[int] = None, plant_id: Optional[int] = None):
    """Retrieves modern target records."""
    return data_retriever.get_modern_kpi_targets(kpi_id=kpi_id, plant_id=plant_id)

# --- KPI spec update ---
@app.get("/kpis/{kpi_id}")
def get_kpi_by_id(kpi_id: int, plant_id: Optional[int] = None):
    """Fetches a single detailed KPI spec by ID."""
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id, plant_id=plant_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    return kpi

@app.put("/kpis/{kpi_id}")
def update_kpi_spec(kpi_id: int, req: KPISpecUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Updates a KPI's spec fields (description, calculation_type, target_count, etc.)."""
    success = kpi_crud.update_kpi_spec_extended(kpi_id, req.data_updates, changed_by=current_user["name"])
    if not success:
        raise HTTPException(status_code=404, detail="KPI not found or no valid fields to update")
    return {"status": "success", "kpi_id": kpi_id}

@app.get("/units-of-measure")
def list_units_of_measure():
    """Returns the registry of defined units of measure for KPI Explorer's UoM picker."""
    return kpi_crud.get_all_units_of_measure()

@app.post("/units-of-measure")
def create_unit_of_measure(req: UnitOfMeasureCreateRequest):
    """Adds a new unit of measure to the registry (or returns the existing one)."""
    try:
        return kpi_crud.add_unit_of_measure(req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/kpis/{kpi_id}/global-split")
def assign_kpi_global_split(kpi_id: int, req: KpiGlobalSplitAssignRequest):
    """
    Assigns (or clears) the single Global Split Template used to repartition this KPI's targets.
    This is the consolidated home for repartition/split assignment -- Target Entry no longer
    exposes per-target repartition controls, so this is the only place a user sets it.
    """
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    splits_crud.set_kpi_global_split(kpi["indicator_id"], req.global_split_id)
    return {"status": "success", "kpi_id": kpi_id, "global_split_id": req.global_split_id}

@app.get("/kpis/{kpi_id}/visibility")
def get_kpi_visibility(kpi_id: int):
    """Returns explicit plant visibility overrides for a KPI."""
    return visibility_crud.get_plant_visibility_for_kpi(kpi_id)

@app.put("/kpis/{kpi_id}/visibility")
def update_kpi_visibility(kpi_id: int, req: VisibilityUpdateRequest):
    """Updates plant visibility overrides for a KPI."""
    visibility_crud.update_plant_visibility(kpi_id, [v.dict() for v in req.visibility_data])
    return {"status": "success", "kpi_id": kpi_id}

# --- Plants CRUD ---
@app.post("/plants")
def create_plant(req: PlantCreateRequest):
    """Creates a new plant."""
    try:
        plant_id = plants_crud.add_plant(req.name, req.description, req.visible, req.color)
        return {"plant_id": plant_id, "name": req.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/plants/{plant_id}")
def update_plant(plant_id: int, req: PlantUpdateRequest):
    """Updates an existing plant's details."""
    try:
        plants_crud.update_plant(plant_id, req.name, req.description, req.visible, req.color)
        return {"status": "success", "plant_id": plant_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/plants/{plant_id}")
def delete_plant(plant_id: int, force: bool = False):
    """Deletes a plant. Fails if referenced in targets unless force=true."""
    try:
        plants_crud.delete_plant(plant_id, force_delete_if_referenced=force)
        return {"status": "success", "plant_id": plant_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Global Splits ---
@app.get("/global-splits")
def list_global_splits(year: Optional[int] = None):
    return splits_crud.get_all_global_splits(year=year)

@app.get("/global-splits/curve-preview")
def preview_curve_weights(profile: str, logic: str, year: Optional[int] = None):
    """Suggested per-period weights for a distribution curve, to pre-fill a new template's weight cells."""
    return splits_crud.get_curve_weight_suggestions(profile, logic, year)

@app.get("/global-splits/{split_id}")
def get_global_split(split_id: int):
    split = splits_crud.get_global_split(split_id)
    if not split:
        raise HTTPException(status_code=404, detail="Global split not found")
    return split

@app.post("/global-splits")
def create_global_split(req: GlobalSplitCreateRequest):
    split_id = splits_crud.add_global_split(
        name=req.name,
        repartition_logic=req.repartition_logic,
        repartition_values=req.repartition_values,
        distribution_profile=req.distribution_profile,
        profile_params=req.profile_params,
        years=req.years,
        afflicted_indicators=req.afflicted_indicators,
    )
    return {"split_id": split_id, "name": req.name}

@app.put("/global-splits/{split_id}")
def update_global_split(split_id: int, req: GlobalSplitUpdateRequest):
    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    splits_crud.update_global_split(split_id, **kwargs)
    return {"status": "success", "split_id": split_id}

@app.delete("/global-splits/{split_id}")
def delete_global_split(split_id: int):
    splits_crud.delete_global_split(split_id)
    return {"status": "success", "split_id": split_id}

@app.get("/global-splits/{split_id}/indicators")
def get_global_split_indicators(split_id: int):
    return splits_crud.get_indicators_for_global_split(split_id)

@app.put("/global-splits/{split_id}/indicators")
def update_global_split_indicators(split_id: int, req: GlobalSplitIndicatorsUpdateRequest):
    splits_crud.update_global_split_indicators(split_id, req.indicators)
    return {"status": "success", "split_id": split_id}

@app.get("/kpis/{kpi_id}/global-splits")
def get_global_splits_for_kpi(kpi_id: int):
    """Returns the Global Split Template(s) assigned to this KPI's indicator."""
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
    indicator_id = kpi["indicator_id"] if kpi else kpi_id
    return splits_crud.get_global_splits_for_indicator(indicator_id)

# --- Annual targets, repartition & periodic targets ---
@app.get("/targets/annual-entry")
def get_annual_target_entry(year: int, plant_id: int, kpi_id: int):
    """Fetches the annual target record (repartition config + all target_number values) for a KPI/plant/year."""
    entry = data_retriever.get_annual_target_entry(year, plant_id, kpi_id)
    return entry

@app.get("/targets/annual")
def get_annual_targets(plant_id: int, year: int):
    """Fetches all annual target records for a plant/year."""
    return data_retriever.get_annual_targets(plant_id, year)

@app.get("/targets/available-numbers")
def get_available_target_numbers(year: int, plant_id: int, kpi_id: int):
    return data_retriever.get_available_target_numbers_for_kpi(year, plant_id, kpi_id)

@app.post("/targets/annual")
def save_annual_targets_endpoint(req: SaveAnnualTargetsRequest, current_user: dict = Depends(get_current_user)):
    """
    Saves annual targets (repartition config + per-target_number values) for one or more plants,
    triggers formula-cascade calculation, and automatically recalculates all periodic (day/week/
    month/quarter) repartitions for every affected KPI. This is the primary Target Entry save path.
    """
    targets_data_map = {}
    for kpi_id_str, kpi_input in req.targets_data_map.items():
        # Repartition/split config is no longer set from Target Entry (it's assigned once on the
        # KPI in KPI Explorer instead), so these keys are only included when actually provided --
        # otherwise annual.py's "in data_dict_from_ui" check would fire on every save and null out
        # the NOT NULL repartition_logic/distribution_profile columns on the existing row.
        entry = {"targets": [t.dict() for t in kpi_input.targets]}
        if kpi_input.repartition_logic is not None:
            entry["repartition_logic"] = kpi_input.repartition_logic
        if kpi_input.repartition_values:
            entry["repartition_values"] = json.dumps(kpi_input.repartition_values)
        if kpi_input.distribution_profile is not None:
            entry["distribution_profile"] = kpi_input.distribution_profile
        if kpi_input.profile_params:
            entry["profile_params"] = json.dumps(kpi_input.profile_params)
        if kpi_input.global_split_id is not None:
            entry["global_split_id"] = kpi_input.global_split_id
        targets_data_map[kpi_id_str] = entry

    try:
        annual_management.save_annual_targets(
            year=req.year,
            plant_id=req.plant_id,
            targets_data_map=targets_data_map,
            initiator_kpi_spec_id=req.initiator_kpi_spec_id,
            changed_by=current_user["name"],
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/kpis/{kpi_id}/periodic-targets")
def get_kpi_periodic_targets(kpi_id: int, plant_id: int, year: int, period_type: str, target_number: int):
    return data_retriever.get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_number)

@app.get("/kpis/{kpi_id}/periodic-targets/all-plants")
def get_kpi_periodic_targets_all_plants(kpi_id: int, period_type: str, year: Optional[int] = None):
    return data_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year=year)

# --- Multivariate seasonality analysis ---
@app.post("/analysis/multivariate")
async def run_multivariate_analysis(
    file: UploadFile = File(...),
    target_cols: str = Form(...),
    feature_cols: str = Form(...),
    date_col: str = Form(...),
    period_type: str = Form("Month"),
):
    """Uploads a CSV/XLSX dataset and runs the OLS/Ridge/RandomForest seasonality driver race."""
    target_cols_list = json.loads(target_cols) if target_cols.strip().startswith("[") else [c.strip() for c in target_cols.split(",") if c.strip()]
    feature_cols_list = json.loads(feature_cols) if feature_cols.strip().startswith("[") else [c.strip() for c in feature_cols.split(",") if c.strip()]

    suffix = Path(file.filename or "upload.csv").suffix or ".csv"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        weights, coefficients, r_squared, plot_df, winning_model = split_analyzer.analyze_seasonality_from_file(
            tmp_path, target_cols_list, feature_cols_list, date_col, period_type
        )
        return {
            "weights": weights,
            "coefficients": coefficients,
            "r_squared": r_squared,
            "plot_data": plot_df.to_dict("records"),
            "winning_model": winning_model,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- KPI Indicator Templates ---
@app.get("/templates")
def list_templates():
    return data_retriever.get_kpi_indicator_templates()

@app.post("/templates")
def create_template(req: TemplateCreateRequest):
    template_id = templates_crud.add_kpi_indicator_template(req.name, req.description or "")
    return {"template_id": template_id, "name": req.name}

@app.delete("/templates/{template_id}")
def delete_template(template_id: int):
    templates_crud.delete_kpi_indicator_template(template_id)
    return {"status": "success", "template_id": template_id}

@app.get("/templates/{template_id}/indicators")
def get_template_indicators(template_id: int):
    return data_retriever.get_template_defined_indicators(template_id)

@app.post("/templates/{template_id}/indicators")
def add_template_indicator(template_id: int, req: TemplateIndicatorCreateRequest):
    templates_crud.add_indicator_definition_to_template(
        template_id, req.indicator_name_in_template, req.default_calculation_type,
        req.default_unit_of_measure, req.default_visible, req.default_description or ""
    )
    return {"status": "success", "template_id": template_id}

@app.put("/templates/indicators/{definition_id}")
def update_template_indicator(definition_id: int, req: TemplateIndicatorUpdateRequest):
    templates_crud.update_indicator_definition_in_template(
        definition_id, req.template_id, req.name, req.calc_type, req.unit, req.visible, req.description or ""
    )
    return {"status": "success", "definition_id": definition_id}

@app.delete("/templates/indicators/{definition_id}")
def remove_template_indicator(definition_id: int):
    templates_crud.remove_indicator_definition_from_template(definition_id)
    return {"status": "success", "definition_id": definition_id}

# --- Data utilities: CSV export & ZIP backup/restore ---
@app.get("/years")
def get_years():
    return data_retriever.get_distinct_years()

@app.get("/export/lean")
def export_lean_csv():
    export_dir = Path(tempfile.mkdtemp())
    export_manager.export_lean_data_to_csv(str(export_dir))
    file_path = export_dir / "lean_target_data.csv"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="No data available to export")
    return FileResponse(file_path, filename="lean_target_data.csv", media_type="text/csv")

@app.get("/export/csv/{table_key}")
def export_csv_table(table_key: str):
    export_dir = Path(tempfile.mkdtemp())
    result = export_manager.export_single_table(table_key, str(export_dir))
    if result.startswith("Error"):
        raise HTTPException(status_code=400, detail=result)
    filename = export_manager.GLOBAL_CSV_FILES.get(
        {"Plants": "plants", "KPI Hierarchy": "kpi_nodes", "KPI Definitions": "kpi_definitions",
         "Plant Visibility": "kpi_plant_visibility", "Annual Targets": "annual", "Periodic Targets": "periodic"}.get(table_key, "")
    )
    file_path = export_dir / filename if filename else None
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Export produced no file")
    return FileResponse(file_path, filename=filename, media_type="text/csv")

@app.get("/export/all")
def export_all_backup():
    """Dumps raw tables and packages them as a downloadable ZIP backup (restorable via /import/restore)."""
    export_dir = Path(tempfile.mkdtemp())
    written_files = export_manager.export_raw_backup_csvs(str(export_dir))
    if not written_files:
        raise HTTPException(status_code=500, detail="No data available to back up")
    ok, zip_bytes = export_manager.package_all_csvs_as_zip(str(export_dir), return_bytes_for_streamlit=True, file_names=written_files)
    if not ok:
        raise HTTPException(status_code=500, detail=str(zip_bytes))
    import io as _io
    return StreamingResponse(
        _io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=kpi_backup.zip"},
    )

@app.get("/kpis/{kpi_id}/target-history")
def get_kpi_target_history(kpi_id: int, plant_id: Optional[int] = None):
    """Retrieves the audit trail of target value edits for a KPI (who changed what, and when)."""
    return history_service.get_target_history(kpi_id, plant_id=plant_id)

# --- Users (named profiles for audit attribution) ---
@app.get("/users")
def list_users(active_only: bool = False):
    return user_crud.get_all_users(active_only=active_only)

@app.post("/users")
def create_user(req: UserCreateRequest):
    """Admin-style user creation (requires a password, same as /auth/register but doesn't log the caller in)."""
    try:
        user_id = user_crud.add_user(req.name, req.password, req.email or "", req.color or "#3b82f6")
        return {"id": user_id, "name": req.name}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdateRequest):
    try:
        user_crud.update_user(user_id, req.name, req.email or "", req.color or "#3b82f6", req.is_active)
        return {"status": "success", "id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

# --- API Keys (MCP authentication, tied to a user) ---
@app.get("/users/{user_id}/api-keys")
def list_user_api_keys(user_id: int):
    return user_crud.list_api_keys(user_id=user_id)

@app.post("/users/{user_id}/api-keys")
def create_user_api_key(user_id: int, req: ApiKeyCreateRequest):
    """Creates a new MCP API key for a user. The raw key is returned ONCE -- it cannot be retrieved again."""
    if not user_crud.get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return user_crud.create_api_key(user_id, req.label)

@app.delete("/api-keys/{key_id}")
def revoke_api_key(key_id: int):
    user_crud.revoke_api_key(key_id)
    return {"status": "success", "id": key_id}

@app.post("/import/restore")
async def restore_from_backup(file: UploadFile = File(...)):
    """Restores database state by appending records from an uploaded ZIP backup."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        result = import_manager.import_from_zip(tmp_path)
        if result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return {"status": "success", "detail": result}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

