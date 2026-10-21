# src/api.py
"""REST API for the React app (and anyone with a session token). Swagger UI at /docs."""
import logging
import os
import shutil
import tempfile
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator

from src import data_retriever, export_manager, import_manager
from src.config import settings as app_settings
from src.core.formula import FormulaError
from src.data_access.setup import setup_databases
from src.kpi_management import crud as kpi_crud
from src.kpi_management import splits as splits_crud
from src.kpi_management import templates as templates_crud
from src.kpi_management import visibility as visibility_crud
from src.plants_management import crud as plants_crud
from src.services import actuals_service, history_service, split_analyzer
from src.target_management import annual as annual_management
from src.user_management import access
from src.user_management import crud as user_crud

APP_VERSION = "2.1.0"
log = logging.getLogger("kpi.api")


def _env_flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    setup_databases()
    user_crud.purge_expired_sessions()
    yield


bearer_scheme = HTTPBearer(auto_error=False, description="Session token from POST /auth/login")

app = FastAPI(
    title="Data Entry KPI Target Manager API",
    description="REST API for KPI definitions, targets, repartition, splits, plants, users and backups. "
                "Log in with POST /auth/login, then click Authorize and paste the token.",
    version=APP_VERSION,
    lifespan=lifespan,
    dependencies=[Security(bearer_scheme)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Errors -> HTTP ---

@app.exception_handler(annual_management.TargetValidationError)
@app.exception_handler(FormulaError)
@app.exception_handler(import_manager.RestoreError)
async def _bad_request(_request: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(access.AccessDenied)
async def _forbidden(_request: Request, exc: Exception):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. See the server log for details."})


def _bad(exc: Exception, status: int = 400):
    raise HTTPException(status_code=status, detail=str(exc)) from exc


# --- Auth gate ---
# Every route needs a valid session (Authorization: Bearer <token>) except this allowlist.
_PUBLIC_PATHS = {"/", "/health", "/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc",
                 "/auth/register", "/auth/login", "/auth/logout", "/auth/status"}


@app.middleware("http")
async def _require_session(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    user = user_crud.validate_session(raw_token) if raw_token else None
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated. Log in via POST /auth/login."})
    request.state.user = user
    request.state.session_token = raw_token
    return await call_next(request)


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    access.require_admin(user)
    return user


class _LoginRateLimiter:
    """Failed-login throttle: per (client, name) and per client, sliding window, in memory."""

    def __init__(self, per_name: int = 8, per_client: int = 40, window_seconds: int = 900):
        self.per_name, self.per_client, self.window = per_name, per_client, window_seconds
        self._failures: Dict[tuple, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key) -> deque:
        q, cutoff = self._failures[key], time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def check(self, client: str, name: str):
        with self._lock:
            if len(self._recent((client, name.lower()))) >= self.per_name or len(self._recent((client,))) >= self.per_client:
                raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")

    def failed(self, client: str, name: str):
        now = time.monotonic()
        with self._lock:
            self._recent((client, name.lower())).append(now)
            self._recent((client,)).append(now)

    def succeeded(self, client: str, name: str):
        with self._lock:
            self._failures.pop((client, name.lower()), None)


login_limiter = _LoginRateLimiter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --- Models ---

_HEX = r"^#[0-9a-fA-F]{6}$"
Name = Field(..., min_length=1, max_length=200)


class ActualMeasurementRequest(BaseModel):
    kpi_id: int
    plant_id: int
    measurement_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    actual_value: float


class TargetUpdateRequest(BaseModel):
    kpi_id: int
    plant_id: int
    target_number: int = Field(..., ge=1)
    period_start: str
    period_end: str
    target_value: float


class KPIIndicatorCreateRequest(BaseModel):
    node_id: int
    name: str = Name
    description: Optional[str] = None
    calculation_type: Optional[str] = "Sum"
    unit_of_measure: Optional[str] = None
    visible: Optional[bool] = True
    owner: Optional[str] = None
    direction: Optional[str] = "Higher is Better"
    threshold_json: Optional[str] = None
    target_granularity: Optional[str] = "Monthly"
    target_count: int = Field(1, ge=1, le=10)
    time_filter_type: Optional[str] = "None"
    time_filter_value: Optional[str] = None


class KPINodeCreateRequest(BaseModel):
    parent_id: Optional[int] = None
    name: str = Name
    custom_level_label: Optional[str] = None


class KPISpecUpdateRequest(BaseModel):
    data_updates: Dict[str, Any]


class UnitOfMeasureCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class KpiGlobalSplitAssignRequest(BaseModel):
    global_split_id: Optional[int] = None


class PlantRequest(BaseModel):
    name: str = Name
    description: Optional[str] = ""
    visible: bool = True
    color: str = Field("#3b82f6", pattern=_HEX)


class VisibilityEntry(BaseModel):
    plant_id: int
    is_enabled: bool


class VisibilityUpdateRequest(BaseModel):
    visibility_data: List[VisibilityEntry]


class SplitIndicatorLink(BaseModel):
    indicator_id: int
    override_distribution_profile: Optional[str] = None


class GlobalSplitCreateRequest(BaseModel):
    name: str = Name
    repartition_logic: str
    repartition_values: Dict[str, Any] = {}
    distribution_profile: str
    profile_params: Dict[str, Any] = {}
    years: Optional[List[int]] = None
    afflicted_indicators: Optional[List[SplitIndicatorLink]] = None


class GlobalSplitUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    repartition_logic: Optional[str] = None
    repartition_values: Optional[Dict[str, Any]] = None
    distribution_profile: Optional[str] = None
    profile_params: Optional[Dict[str, Any]] = None
    years: Optional[List[int]] = None
    afflicted_indicators: Optional[List[SplitIndicatorLink]] = None


class GlobalSplitIndicatorsUpdateRequest(BaseModel):
    indicators: List[SplitIndicatorLink]


class AnnualTargetValueInput(BaseModel):
    target_number: int = Field(..., ge=1, le=10)
    target_value: Optional[float] = None
    # Accepted for backwards compatibility; per-target formulas are rejected (set them on the KPI).
    is_manual: bool = True
    is_formula_based: bool = False
    formula: Optional[str] = None
    formula_inputs: Optional[Any] = None


class AnnualTargetKpiInput(BaseModel):
    repartition_logic: Optional[str] = None
    repartition_values: Optional[Dict[str, Any]] = None
    distribution_profile: Optional[str] = None
    profile_params: Optional[Dict[str, Any]] = None
    global_split_id: Optional[int] = None
    targets: List[AnnualTargetValueInput] = []


class SaveAnnualTargetsRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2200)
    plant_id: Union[int, List[int]]
    targets_data_map: Dict[str, AnnualTargetKpiInput]
    initiator_kpi_spec_id: Optional[int] = None


class TemplateCreateRequest(BaseModel):
    name: str = Name
    description: Optional[str] = ""


class TemplateIndicatorCreateRequest(BaseModel):
    indicator_name_in_template: str = Name
    default_calculation_type: str = "Sum"
    default_unit_of_measure: Optional[str] = None
    default_visible: bool = True
    default_description: Optional[str] = ""


class TemplateIndicatorUpdateRequest(BaseModel):
    template_id: int
    name: str = Name
    calc_type: str
    unit: Optional[str] = None
    visible: bool = True
    description: Optional[str] = ""


class TemplateApplyRequest(BaseModel):
    node_id: int


class UserCreateRequest(BaseModel):
    name: str = Name
    password: str = Field(..., min_length=8, max_length=256)
    email: Optional[str] = ""
    color: Optional[str] = Field("#3b82f6", pattern=_HEX)
    is_admin: bool = False


class UserUpdateRequest(BaseModel):
    name: str = Name
    email: Optional[str] = ""
    color: Optional[str] = Field("#3b82f6", pattern=_HEX)
    is_active: bool = True
    is_admin: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=256)


class ApiKeyCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)


class RegisterRequest(BaseModel):
    name: str = Name
    password: str = Field(..., min_length=8, max_length=256)
    email: Optional[str] = ""
    color: Optional[str] = Field("#3b82f6", pattern=_HEX)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()


class LoginRequest(BaseModel):
    name: str = Field(..., max_length=200)
    password: str = Field(..., max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=256)
    new_password: str = Field(..., min_length=8, max_length=256)


# --- Health & auth ---

@app.get("/health", tags=["system"])
def health_check():
    return {"status": "healthy", "version": APP_VERSION}


def _registration_open() -> bool:
    return user_crud.count_users() == 0 or _env_flag("ALLOW_REGISTRATION")


@app.get("/auth/status", tags=["auth"])
def auth_status():
    """Public: whether self-registration is open (always true until the first account exists)."""
    has_users = user_crud.count_users() > 0
    return {"has_users": has_users, "registration_open": not has_users or _env_flag("ALLOW_REGISTRATION")}


@app.post("/auth/register", tags=["auth"])
def register(req: RegisterRequest, request: Request):
    """Creates an account and logs it in. The first account becomes admin; afterwards registration
    is closed unless ALLOW_REGISTRATION=true (admins can always create users via POST /users)."""
    if not _registration_open():
        raise HTTPException(status_code=403, detail="Registration is closed. Ask an admin to create your account.")
    login_limiter.check(_client_ip(request), req.name)
    try:
        user_id = user_crud.add_user(req.name, req.password, req.email or "", req.color or "#3b82f6")
    except ValueError as e:
        login_limiter.failed(_client_ip(request), req.name)
        raise HTTPException(status_code=409, detail=str(e)) from e
    session = user_crud.create_session(user_id)
    return {"token": session["token"], "expires_at": session["expires_at"], "user": user_crud.get_user_by_id(user_id)}


@app.post("/auth/login", tags=["auth"])
def login(req: LoginRequest, request: Request):
    client = _client_ip(request)
    login_limiter.check(client, req.name)
    user = user_crud.verify_password(req.name, req.password)
    if not user:
        login_limiter.failed(client, req.name)
        raise HTTPException(status_code=401, detail="Invalid name or password.")
    login_limiter.succeeded(client, req.name)
    session = user_crud.create_session(user["id"])
    return {"token": session["token"], "expires_at": session["expires_at"], "user": user}


@app.post("/auth/logout", tags=["auth"])
def logout(request: Request):
    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    user_crud.revoke_session(raw_token)
    return {"status": "success"}


@app.get("/auth/me", tags=["auth"])
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/auth/change-password", tags=["auth"])
def change_password(req: ChangePasswordRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """Changes your password and signs out your other sessions (this one stays valid)."""
    try:
        user_crud.change_password(current_user["id"], req.current_password, req.new_password,
                                  keep_session_token=getattr(request.state, "session_token", None))
    except ValueError as e:
        _bad(e)
    return {"status": "success"}


# --- KPIs ---

def _kpi_or_404(kpi_id: int) -> dict:
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    return kpi


@app.get("/kpis", tags=["kpis"])
def get_kpis(only_visible: bool = False, plant_id: Optional[int] = None):
    """Active KPI specs. With plant_id, KPIs explicitly disabled for that plant are omitted."""
    return data_retriever.get_all_kpis_detailed(only_visible=only_visible, plant_id=plant_id)


@app.get("/kpis/tree", tags=["kpis"])
def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = Query(None, ge=1)):
    return kpi_crud.get_kpi_tree(root_id=root_id, depth=depth)


@app.post("/kpis", tags=["kpis"])
def create_kpi(req: KPIIndicatorCreateRequest, current_user: dict = Depends(get_current_user)):
    try:
        return kpi_crud.create_kpi_indicator(**req.model_dump(), changed_by=current_user["name"])
    except ValueError as e:
        _bad(e)


@app.post("/kpis/nodes", tags=["kpis"])
def add_kpi_node(req: KPINodeCreateRequest):
    try:
        node_id = kpi_crud.add_kpi_node(req.parent_id, req.name, req.custom_level_label)
    except ValueError as e:
        _bad(e)
    return {"node_id": node_id, "name": req.name.strip()}


@app.delete("/kpis/{kpi_id}", tags=["kpis"])
def soft_delete_kpi(kpi_id: int, current_user: dict = Depends(get_current_user)):
    """Hides a KPI everywhere; its targets, actuals and history are kept."""
    if not kpi_crud.soft_delete_kpi(kpi_id, changed_by=current_user["name"]):
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"status": "success", "kpi_id": kpi_id, "is_active": False}


@app.get("/kpis/{kpi_id}/status", tags=["kpis"])
def get_kpi_status(kpi_id: int, plant_id: int, target_value: Optional[float] = None,
                   target_number: int = Query(1, ge=1, le=10)):
    """Latest actual vs target. Without target_value, uses the stored target (scenario target_number)
    for the latest actual's day -- 404 if there is none."""
    _kpi_or_404(kpi_id)
    try:
        return data_retriever.get_kpi_performance_status(
            kpi_id=kpi_id, plant_id=plant_id, target_value=target_value, target_number=target_number)
    except LookupError as e:
        _bad(e, 404)


@app.get("/kpis/{kpi_id}/history", tags=["kpis"])
def get_kpi_history(kpi_id: int):
    return history_service.get_definition_history(kpi_id)


@app.get("/kpis/{kpi_id}/target-history", tags=["kpis"])
def get_kpi_target_history(kpi_id: int, plant_id: Optional[int] = None):
    return history_service.get_target_history(kpi_id, plant_id=plant_id)


@app.get("/kpis/{kpi_id}", tags=["kpis"])
def get_kpi_by_id(kpi_id: int, plant_id: Optional[int] = None):
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id, plant_id=plant_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    return kpi


@app.put("/kpis/{kpi_id}", tags=["kpis"])
def update_kpi_spec(kpi_id: int, req: KPISpecUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Updates spec fields. Setting formula_string (e.g. "[3] / [4]") makes the KPI calculated;
    the formula is validated (syntax, known KPIs, no cycles) and targets are recalculated."""
    unknown = sorted(set(req.data_updates) - set(kpi_crud.UPDATABLE_SPEC_FIELDS))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Field(s) can't be updated: {', '.join(unknown)}")
    try:
        ok = kpi_crud.update_kpi_spec_extended(kpi_id, req.data_updates, changed_by=current_user["name"])
    except ValueError as e:
        _bad(e)
    if not ok:
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"status": "success", "kpi_id": kpi_id}


@app.get("/units-of-measure", tags=["kpis"])
def list_units_of_measure():
    return kpi_crud.get_all_units_of_measure()


@app.post("/units-of-measure", tags=["kpis"])
def create_unit_of_measure(req: UnitOfMeasureCreateRequest):
    try:
        return kpi_crud.add_unit_of_measure(req.name)
    except ValueError as e:
        _bad(e)


@app.put("/kpis/{kpi_id}/global-split", tags=["kpis"])
def assign_kpi_global_split(kpi_id: int, req: KpiGlobalSplitAssignRequest, current_user: dict = Depends(get_current_user)):
    """Assigns (or clears) the split template used to repartition this KPI, then recalculates its targets."""
    kpi = _kpi_or_404(kpi_id)
    try:
        splits_crud.set_kpi_global_split(kpi["indicator_id"], req.global_split_id)
    except ValueError as e:
        _bad(e, 404)
    annual_management.recalculate_kpis([kpi_id], changed_by=current_user["name"])
    return {"status": "success", "kpi_id": kpi_id, "global_split_id": req.global_split_id}


@app.get("/kpis/{kpi_id}/visibility", tags=["kpis"])
def get_kpi_visibility(kpi_id: int):
    return visibility_crud.get_plant_visibility_for_kpi(kpi_id)


@app.put("/kpis/{kpi_id}/visibility", tags=["kpis"])
def update_kpi_visibility(kpi_id: int, req: VisibilityUpdateRequest):
    if not visibility_crud.update_plant_visibility(kpi_id, [v.model_dump() for v in req.visibility_data]):
        raise HTTPException(status_code=404, detail="KPI not found")
    return {"status": "success", "kpi_id": kpi_id}


@app.get("/kpis/{kpi_id}/global-splits", tags=["kpis"])
def get_global_splits_for_kpi(kpi_id: int):
    return splits_crud.get_global_splits_for_indicator(_kpi_or_404(kpi_id)["indicator_id"])


# --- Plants ---

@app.get("/plants", tags=["plants"])
def get_plants(visible_only: bool = False):
    return data_retriever.get_all_plants(visible_only=visible_only)


@app.post("/plants", tags=["plants"])
def create_plant(req: PlantRequest):
    try:
        plant_id = plants_crud.add_plant(req.name, req.description, req.visible, req.color)
    except ValueError as e:
        _bad(e, 409)
    return {"plant_id": plant_id, "name": req.name.strip()}


@app.put("/plants/{plant_id}", tags=["plants"])
def update_plant(plant_id: int, req: PlantRequest):
    try:
        plants_crud.update_plant(plant_id, req.name, req.description, req.visible, req.color)
    except plants_crud.PlantNotFoundError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e, 409)
    return {"status": "success", "plant_id": plant_id}


@app.delete("/plants/{plant_id}", tags=["plants"])
def delete_plant(plant_id: int, force: bool = False):
    """Deletes a plant. Refuses (409) if it has targets/actuals unless force=true, which deletes them too."""
    try:
        plants_crud.delete_plant(plant_id, force_delete_if_referenced=force)
    except plants_crud.PlantNotFoundError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e, 409)
    return {"status": "success", "plant_id": plant_id}


# --- Global splits ---

@app.get("/global-splits", tags=["splits"])
def list_global_splits(year: Optional[int] = None):
    return splits_crud.get_all_global_splits(year=year)


@app.get("/global-splits/curve-preview", tags=["splits"])
def preview_curve_weights(profile: str, logic: str, year: Optional[int] = None):
    """Suggested per-period weights for a curve, to pre-fill a template's weight cells."""
    return splits_crud.get_curve_weight_suggestions(profile, logic, year)


@app.get("/global-splits/{split_id}", tags=["splits"])
def get_global_split(split_id: int):
    split = splits_crud.get_global_split(split_id)
    if not split:
        raise HTTPException(status_code=404, detail="Global split not found")
    return split


def _links(items) -> Optional[list]:
    return None if items is None else [i.model_dump() for i in items]


@app.post("/global-splits", tags=["splits"])
def create_global_split(req: GlobalSplitCreateRequest, current_user: dict = Depends(get_current_user)):
    try:
        split_id = splits_crud.add_global_split(
            name=req.name, repartition_logic=req.repartition_logic, repartition_values=req.repartition_values,
            distribution_profile=req.distribution_profile, profile_params=req.profile_params, years=req.years,
            afflicted_indicators=_links(req.afflicted_indicators),
        )
    except ValueError as e:
        _bad(e)
    if req.afflicted_indicators:
        annual_management.recalculate_indicators([i.indicator_id for i in req.afflicted_indicators], current_user["name"])
    return {"split_id": split_id, "name": req.name.strip()}


@app.put("/global-splits/{split_id}", tags=["splits"])
def update_global_split(split_id: int, req: GlobalSplitUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Updates a template; every KPI using it gets its targets recalculated."""
    before = {i["indicator_id"] for i in splits_crud.get_indicators_for_global_split(split_id)}
    try:
        found = splits_crud.update_global_split(
            split_id, name=req.name, repartition_logic=req.repartition_logic, repartition_values=req.repartition_values,
            distribution_profile=req.distribution_profile, profile_params=req.profile_params, years=req.years,
            afflicted_indicators=_links(req.afflicted_indicators),
        )
    except ValueError as e:
        _bad(e)
    if not found:
        raise HTTPException(status_code=404, detail="Global split not found")
    after = {i["indicator_id"] for i in splits_crud.get_indicators_for_global_split(split_id)}
    annual_management.recalculate_indicators(before | after, current_user["name"])
    return {"status": "success", "split_id": split_id}


@app.delete("/global-splits/{split_id}", tags=["splits"])
def delete_global_split(split_id: int, current_user: dict = Depends(get_current_user)):
    if not splits_crud.get_global_split(split_id):
        raise HTTPException(status_code=404, detail="Global split not found")
    affected = splits_crud.delete_global_split(split_id)
    annual_management.recalculate_indicators(affected, current_user["name"])
    return {"status": "success", "split_id": split_id}


@app.get("/global-splits/{split_id}/indicators", tags=["splits"])
def get_global_split_indicators(split_id: int):
    return splits_crud.get_indicators_for_global_split(split_id)


@app.put("/global-splits/{split_id}/indicators", tags=["splits"])
def update_global_split_indicators(split_id: int, req: GlobalSplitIndicatorsUpdateRequest,
                                   current_user: dict = Depends(get_current_user)):
    if not splits_crud.get_global_split(split_id):
        raise HTTPException(status_code=404, detail="Global split not found")
    before = {i["indicator_id"] for i in splits_crud.get_indicators_for_global_split(split_id)}
    try:
        splits_crud.update_global_split_indicators(split_id, _links(req.indicators))
    except ValueError as e:
        _bad(e)
    annual_management.recalculate_indicators(before | {i.indicator_id for i in req.indicators}, current_user["name"])
    return {"status": "success", "split_id": split_id}


# --- Targets ---

@app.get("/targets/lean", tags=["targets"])
def get_lean_targets():
    """Minimal, BI-friendly list of all periodic targets."""
    return data_retriever.get_lean_targets()


@app.post("/targets", tags=["targets"], deprecated=True)
def update_target_value(req: TargetUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Legacy flat target table (explicit start/end). Not used by repartition or the UI --
    use POST /targets/annual instead."""
    kpi_crud.update_target_value(**req.model_dump(), changed_by=current_user["name"])
    return {"status": "success", "updated": True}


@app.get("/targets", tags=["targets"], deprecated=True)
def get_targets(kpi_id: Optional[int] = None, plant_id: Optional[int] = None):
    """Rows of the legacy flat target table (see POST /targets)."""
    return data_retriever.get_modern_kpi_targets(kpi_id=kpi_id, plant_id=plant_id)


@app.get("/targets/annual-entry", tags=["targets"])
def get_annual_target_entry(year: int, plant_id: int, kpi_id: int):
    return data_retriever.get_annual_target_entry(year, plant_id, kpi_id)


@app.get("/targets/annual", tags=["targets"])
def get_annual_targets(plant_id: int, year: int):
    return data_retriever.get_annual_targets(plant_id, year)


@app.get("/targets/available-numbers", tags=["targets"])
def get_available_target_numbers(year: int, plant_id: int, kpi_id: int):
    return data_retriever.get_available_target_numbers_for_kpi(year, plant_id, kpi_id)


@app.post("/targets/annual", tags=["targets"])
def save_annual_targets_endpoint(req: SaveAnnualTargetsRequest, current_user: dict = Depends(get_current_user)):
    """Saves annual targets for one or more plants, recalculates dependent formula KPIs and all
    periodic (day/week/month/quarter) targets -- atomically. Blank values are left unchanged."""
    targets_data_map = {}
    for kpi_id_str, kpi_input in req.targets_data_map.items():
        entry = kpi_input.model_dump(exclude_none=True)
        entry["targets"] = [t.model_dump() for t in kpi_input.targets]
        targets_data_map[kpi_id_str] = entry
    annual_management.save_annual_targets(
        year=req.year, plant_id=req.plant_id, targets_data_map=targets_data_map,
        initiator_kpi_spec_id=req.initiator_kpi_spec_id, changed_by=current_user["name"],
    )
    return {"status": "success"}


@app.get("/kpis/{kpi_id}/periodic-targets", tags=["targets"])
def get_kpi_periodic_targets(kpi_id: int, plant_id: int, year: int, period_type: str, target_number: int = 1):
    """[{period, target_value}] in chronological order. period_type: Day, Week, Month, Quarter or Year."""
    try:
        return data_retriever.get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_number)
    except ValueError as e:
        _bad(e)


@app.get("/kpis/{kpi_id}/periodic-targets/all-plants", tags=["targets"])
def get_kpi_periodic_targets_all_plants(kpi_id: int, period_type: str, year: Optional[int] = None):
    try:
        return data_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year=year)
    except ValueError as e:
        _bad(e)


# --- Actuals ---

@app.post("/actuals", tags=["actuals"])
def record_actual(req: ActualMeasurementRequest):
    _kpi_or_404(req.kpi_id)
    row_id = actuals_service.record_actual_measurement(req.kpi_id, req.plant_id, req.measurement_date, req.actual_value)
    return {"status": "success", "id": row_id}


@app.get("/actuals", tags=["actuals"])
def get_actuals(kpi_id: int, plant_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return actuals_service.get_actual_measurements(kpi_id, plant_id, start_date, end_date)


# --- Uploads ---

def _read_upload(file: UploadFile) -> bytes:
    limit = app_settings.max_upload_bytes()
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File is larger than {limit // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return data


def _split_columns(raw: str) -> List[str]:
    import json
    raw = (raw or "").strip()
    if raw.startswith("["):
        try:
            values = json.loads(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Column list is not valid JSON.") from None
        return [str(v).strip() for v in values if str(v).strip()]
    return [c.strip() for c in raw.split(",") if c.strip()]


@app.post("/analysis/multivariate", tags=["analysis"])
def run_multivariate_analysis(
    file: UploadFile = File(...),
    target_cols: str = Form(...),
    feature_cols: str = Form(""),
    date_col: str = Form(...),
    period_type: str = Form("Month"),
):
    """Uploads a CSV/XLSX dataset and races OLS / Ridge / Random Forest to derive seasonal weights.
    The returned weights use template keys (month names, Q1..Q4, W01..W53) in percent, ready to publish."""
    suffix = Path(file.filename or "upload.csv").suffix.lower()
    if suffix not in (".csv", ".txt", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Upload a .csv or .xlsx file.")
    data = _read_upload(file)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"upload{suffix}"
        tmp_path.write_bytes(data)
        try:
            weights, coefficients, r_squared, plot_df, winning_model = split_analyzer.analyze_seasonality_from_file(
                str(tmp_path), _split_columns(target_cols), _split_columns(feature_cols), date_col.strip(), period_type
            )
        except ValueError as e:
            _bad(e)
        except Exception:
            log.exception("Multivariate analysis failed")
            raise HTTPException(status_code=400, detail="Analysis failed: the file could not be processed.") from None
    return {
        "weights": weights,
        "coefficients": coefficients,
        "r_squared": r_squared,
        "plot_data": plot_df.to_dict("records"),
        "winning_model": winning_model,
        "period_type": period_type,
    }


# --- KPI indicator templates ---

@app.get("/templates", tags=["templates"])
def list_templates():
    return data_retriever.get_kpi_indicator_templates()


@app.post("/templates", tags=["templates"])
def create_template(req: TemplateCreateRequest):
    try:
        template_id = templates_crud.add_kpi_indicator_template(req.name, req.description or "")
    except ValueError as e:
        _bad(e, 409)
    return {"template_id": template_id, "name": req.name.strip()}


@app.delete("/templates/{template_id}", tags=["templates"])
def delete_template(template_id: int):
    """Deletes a template and unlinks its folders (KPIs created from it are kept)."""
    if not templates_crud.delete_kpi_indicator_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "success", "template_id": template_id}


@app.get("/templates/{template_id}/indicators", tags=["templates"])
def get_template_indicators(template_id: int):
    return data_retriever.get_template_defined_indicators(template_id)


@app.post("/templates/{template_id}/indicators", tags=["templates"])
def add_template_indicator(template_id: int, req: TemplateIndicatorCreateRequest, current_user: dict = Depends(get_current_user)):
    try:
        definition_id = templates_crud.add_indicator_definition_to_template(
            template_id, req.indicator_name_in_template, req.default_calculation_type, req.default_unit_of_measure,
            req.default_visible, req.default_description or "", changed_by=current_user["name"],
        )
    except LookupError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e)
    return {"status": "success", "template_id": template_id, "definition_id": definition_id}


@app.put("/templates/indicators/{definition_id}", tags=["templates"])
def update_template_indicator(definition_id: int, req: TemplateIndicatorUpdateRequest, current_user: dict = Depends(get_current_user)):
    try:
        ok = templates_crud.update_indicator_definition_in_template(
            definition_id, req.template_id, req.name, req.calc_type, req.unit, req.visible, req.description or "",
            changed_by=current_user["name"],
        )
    except ValueError as e:
        _bad(e)
    if not ok:
        raise HTTPException(status_code=404, detail="Template indicator not found")
    return {"status": "success", "definition_id": definition_id}


@app.delete("/templates/indicators/{definition_id}", tags=["templates"])
def remove_template_indicator(definition_id: int, current_user: dict = Depends(get_current_user)):
    if not templates_crud.remove_indicator_definition_from_template(definition_id, changed_by=current_user["name"]):
        raise HTTPException(status_code=404, detail="Template indicator not found")
    return {"status": "success", "definition_id": definition_id}


@app.post("/templates/{template_id}/apply", tags=["templates"])
def apply_template(template_id: int, req: TemplateApplyRequest, current_user: dict = Depends(get_current_user)):
    """Links a folder to the template and creates its indicators there (later template edits propagate)."""
    try:
        applied = templates_crud.apply_template_to_node(template_id, req.node_id, changed_by=current_user["name"])
    except LookupError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e)
    return {"status": "success", "template_id": template_id, "node_id": req.node_id, "applied": applied}


# --- Data utilities ---

@app.get("/years", tags=["data"])
def get_years():
    return data_retriever.get_distinct_years()


def _file_download(path: Path, tmp_dir: str, background: BackgroundTasks) -> FileResponse:
    background.add_task(shutil.rmtree, tmp_dir, ignore_errors=True)
    return FileResponse(path, filename=path.name, media_type="text/csv", background=background)


@app.get("/export/lean", tags=["data"])
def export_lean_csv(background: BackgroundTasks):
    tmp_dir = tempfile.mkdtemp(prefix="kpi-export-")
    return _file_download(export_manager.export_lean_data_to_csv(tmp_dir), tmp_dir, background)


@app.get("/export/csv/{table_key}", tags=["data"])
def export_csv_table(table_key: str, background: BackgroundTasks):
    """table_key: Plants, KPI Hierarchy, KPI Definitions, Plant Visibility, Annual Targets, Periodic Targets."""
    if table_key not in export_manager.SINGLE_TABLE_EXPORTS:
        raise HTTPException(status_code=400, detail=f"Unknown table '{table_key}'")
    tmp_dir = tempfile.mkdtemp(prefix="kpi-export-")
    return _file_download(export_manager.export_single_table(table_key, tmp_dir), tmp_dir, background)


@app.get("/export/all", tags=["data"])
def export_all_backup():
    """Full raw backup (ZIP) of all KPI data -- restorable with POST /import/restore. User accounts are not included."""
    return Response(
        content=export_manager.build_backup_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=kpi_backup.zip"},
    )


@app.post("/import/restore", tags=["data"])
def restore_from_backup(file: UploadFile = File(...), _admin: dict = Depends(require_admin)):
    """Admin only. REPLACES all KPI data with the backup's contents (one transaction). The current
    databases are snapshotted to <databases>/backups/pre-restore-<timestamp>/ first."""
    data = _read_upload(file)
    result = import_manager.restore_from_zip(data, max_uncompressed_bytes=app_settings.max_upload_bytes() * 25)
    detail = f"Restored {sum(result['tables'].values())} rows in {len(result['tables'])} tables."
    if result["warnings"]:
        detail += " Warnings: " + "; ".join(result["warnings"])
    return {"status": "success", "detail": detail, **result}


# --- Users (rules shared with the MCP server: src/user_management/access.py) ---

@app.get("/users", tags=["users"])
def list_users(active_only: bool = False, current_user: dict = Depends(get_current_user)):
    """Admins get full profiles; everyone else gets id/name/color only."""
    return access.list_users(current_user, active_only=active_only)


@app.post("/users", tags=["users"])
def create_user(req: UserCreateRequest, current_user: dict = Depends(get_current_user)):
    """Admin only: creates an account (the user can change the password after logging in)."""
    try:
        user_id = access.create_user(current_user, req.name, req.password, req.email or "", req.color or "#3b82f6",
                                     is_admin=req.is_admin)
    except ValueError as e:
        _bad(e, 409)
    return {"id": user_id, "name": req.name.strip()}


@app.put("/users/{user_id}", tags=["users"])
def update_user(user_id: int, req: UserUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Admins can edit anyone (incl. is_active / is_admin); users can edit their own name, email and color."""
    try:
        access.update_user(current_user, user_id, req.name, req.email or "", req.color or "#3b82f6",
                           req.is_active, req.is_admin)
    except LookupError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e, 409)
    return {"status": "success", "id": user_id}


@app.post("/users/{user_id}/reset-password", tags=["users"])
def reset_user_password(user_id: int, req: PasswordResetRequest, current_user: dict = Depends(get_current_user)):
    """Admin only: sets a new password and signs the user out everywhere."""
    try:
        access.reset_password(current_user, user_id, req.new_password)
    except LookupError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e)
    return {"status": "success", "id": user_id}


# --- API keys (MCP authentication) ---

@app.get("/users/{user_id}/api-keys", tags=["users"])
def list_user_api_keys(user_id: int, current_user: dict = Depends(get_current_user)):
    return access.list_api_keys(current_user, user_id)


@app.post("/users/{user_id}/api-keys", tags=["users"])
def create_user_api_key(user_id: int, req: ApiKeyCreateRequest, current_user: dict = Depends(get_current_user)):
    """Creates an MCP API key for yourself (admins: for anyone). The raw key is returned ONCE."""
    try:
        return access.create_api_key(current_user, user_id, req.label)
    except LookupError as e:
        _bad(e, 404)
    except ValueError as e:
        _bad(e)


@app.delete("/api-keys/{key_id}", tags=["users"])
def revoke_api_key(key_id: int, current_user: dict = Depends(get_current_user)):
    try:
        access.revoke_api_key(current_user, key_id)
    except LookupError as e:
        _bad(e, 404)
    return {"status": "success", "id": key_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("API_HOST", "127.0.0.1"), port=int(os.environ.get("API_PORT", "8000")))
