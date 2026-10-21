# src/mcp_server.py
"""
Model Context Protocol (MCP) server for the Data Entry KPI Target Manager, built on the
official `mcp` Python SDK -- so any MCP client (Claude Desktop, Claude Code, ...) can connect.
It exposes everything the REST API does (see docs/mcp.md for the tool list), except:
  * /auth/register, /auth/login, /auth/logout -- browser sessions; MCP uses API keys instead
    (`whoami` and `change_my_password` cover the rest of /auth);
  * the deprecated flat /targets table (not used by repartition or the UI).
tests/test_mcp_server.py checks that every other REST route has an MCP tool.

Transports
  * stdio (default): `python -m src.mcp_server` -- a local client spawns it as a subprocess.
    There is no account behind it: writes are attributed to $MCP_STDIO_USER (default
    "mcp_agent"), and it may use the admin tools unless MCP_STDIO_ADMIN=false (whoever can
    spawn it can already read and write the database files directly).
  * Streamable HTTP: `python -m src.mcp_server --http` (or MCP_TRANSPORT=http) serves
    http://<MCP_HOST>:<MCP_PORT>/mcp. Every request needs `Authorization: Bearer <api key>`
    (mint one in Data Utilities -> MCP API Keys, or POST /users/{id}/api-keys). The key's
    owner is recorded as `changed_by` on every write and their role decides access to the
    admin tools -- callers can't claim another identity.

Environment: MCP_HOST (default 127.0.0.1), MCP_PORT (8001), MCP_PUBLIC_URL (the URL clients
use, default http://localhost:<port>), MCP_ALLOWED_HOSTS (comma-separated Host headers
accepted when binding to a non-loopback address, default "localhost:*,127.0.0.1:*"),
MAX_UPLOAD_MB (dataset / backup size cap, default 20).
"""
import base64
import binascii
import functools
import os
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

if __package__ in (None, ""):  # `python src/mcp_server.py` -> make `import src...` work
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.auth.middleware.auth_context import get_access_token  # noqa: E402
from mcp.server.auth.provider import AccessToken  # noqa: E402
from mcp.server.auth.settings import AuthSettings  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

from src import data_retriever, export_manager, import_manager  # noqa: E402
from src.config import settings as app_settings  # noqa: E402
from src.data_access.setup import setup_databases  # noqa: E402
from src.kpi_management import crud as kpi_crud  # noqa: E402
from src.kpi_management import splits as splits_crud  # noqa: E402
from src.kpi_management import templates as templates_crud  # noqa: E402
from src.kpi_management import visibility as visibility_crud  # noqa: E402
from src.plants_management import crud as plants_crud  # noqa: E402
from src.services import actuals_service, history_service, split_analyzer  # noqa: E402
from src.target_management import annual as annual_management  # noqa: E402
from src.user_management import access  # noqa: E402
from src.user_management import crud as user_crud  # noqa: E402

PeriodType = Literal["Day", "Week", "Month", "Quarter", "Year"]
SplitLogic = Literal["Month", "Quarter", "Week", "Year"]
Profile = Literal[
    "even_distribution", "annual_progressive", "annual_progressive_weekday_bias",
    "true_annual_sinusoidal", "event_based_spikes_or_dips",
]
CalcType = Literal["Sum", "Average", "Last", "Min", "Max", "Count"]
Direction = Literal["Higher is Better", "Lower is Better", "Range"]
AnalysisPeriod = Literal["Month", "Quarter", "Week"]
ExportTable = Literal["Plants", "KPI Hierarchy", "KPI Definitions", "Plant Visibility", "Annual Targets",
                      "Periodic Targets", "Lean Targets"]
HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Password = Annotated[str, Field(min_length=8, max_length=256)]
IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")]


class TargetValue(BaseModel):
    target_number: int = Field(1, ge=1, le=10, description="Which target scenario (1 = first, e.g. Base)")
    target_value: Optional[float] = Field(None, description="null leaves the stored value unchanged")


class KpiTargets(BaseModel):
    targets: List[TargetValue] = []
    repartition_logic: Optional[SplitLogic] = None
    distribution_profile: Optional[Profile] = None
    repartition_values: Optional[Dict[str, float]] = Field(
        None, description='Per-period weights in percent: month names, "Q1".."Q4" or "W01".."W53"')
    profile_params: Optional[Dict[str, Any]] = None
    global_split_id: Optional[int] = Field(None, description="A split template to use instead of the fields above")


class VisibilityEntry(BaseModel):
    plant_id: int
    is_enabled: bool


class ApiKeyVerifier:
    """Resolves `Authorization: Bearer <api key>` to the key's (active) owner."""

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        user = user_crud.validate_api_key(token)
        if not user:
            return None
        return AccessToken(token=token, client_id=user["name"], scopes=[], subject=str(user["id"]),
                           claims={"user_id": user["id"], "api_key_id": user["api_key_id"]})


def _public_url(port: int) -> str:
    return os.environ.get("MCP_PUBLIC_URL", f"http://localhost:{port}").rstrip("/")


def _env_flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _caller() -> Dict[str, Any]:
    """The user behind this call: the API key's owner over HTTP (re-read, so a role change or
    deactivation applies at once), or the local stdio operator (no account, id None)."""
    token = get_access_token()
    if token is not None:
        user = user_crud.get_user_by_id(int(token.subject))
        if not user or not user["is_active"]:
            raise ToolError("This API key's account is no longer active.")
        return user
    return {"id": None, "name": os.environ.get("MCP_STDIO_USER", "mcp_agent"),
            "is_admin": _env_flag("MCP_STDIO_ADMIN", True)}


def _actor() -> str:
    """Who a write is attributed to (`changed_by`)."""
    return _caller()["name"]


def _kpi(kpi_id: int) -> Dict[str, Any]:
    kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
    if not kpi:
        raise ToolError(f"KPI {kpi_id} not found")
    return kpi


def _split_links(kpi_ids: Optional[List[int]]) -> Optional[List[Dict[str, Any]]]:
    """KPI (spec) ids -> the indicator links the split tables store."""
    if kpi_ids is None:
        return None
    return [{"indicator_id": _kpi(k)["indicator_id"], "override_distribution_profile": None} for k in kpi_ids]


def _split_indicator_ids(split_id: int) -> set:
    return {i["indicator_id"] for i in splits_crud.get_indicators_for_global_split(split_id)}


def _decode_base64(data: str, what: str) -> bytes:
    limit = app_settings.max_upload_bytes()
    if len(data) > limit * 4 // 3 + 4:
        raise ToolError(f"The {what} is larger than {limit // (1024 * 1024)} MB.")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ToolError(f"The {what} is not valid base64.") from None
    if not raw:
        raise ToolError(f"The {what} is empty.")
    return raw


def build_server(http: bool = False, port: int = 8001) -> MCPServer:
    auth_kwargs: Dict[str, Any] = {}
    if http:
        public = _public_url(port)
        auth_kwargs = {
            "token_verifier": ApiKeyVerifier(),
            "auth": AuthSettings(issuer_url=public, resource_server_url=f"{public}/mcp", validate_token_resource=False),
        }
    server = MCPServer(
        name="Data Entry KPI Target Manager",
        instructions=(
            "Manage KPI definitions, annual targets and their automatic day/week/month/quarter "
            "repartition across plants. KPI ids are spec ids (`id` from list_kpis; `kpi_id` everywhere). "
            "Saving a target, changing a formula/calculation type or editing a split template "
            "recalculates formula KPIs and periodic targets automatically. Formulas reference other "
            "KPIs as [kpi_id], e.g. \"[3] / [4]\". User, password, API-key and restore tools follow the "
            "app's roles: admins manage everyone, other users only themselves. Call whoami to see yours."
        ),
        **auth_kwargs,
    )

    def tool(*, read_only: bool = False, destructive: bool = False, idempotent: bool = False):
        """Registers a tool with hints for clients, and turns anticipated failures (bad input,
        not found, not allowed) into tool errors the model can read. Anything else is a crash and
        the SDK reports only "Error executing tool <name>"."""

        def register(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except (KeyError, IndexError):
                    raise
                except (ValueError, LookupError, access.AccessDenied) as e:
                    raise ToolError(str(e)) from e

            annotations = ToolAnnotations(read_only_hint=read_only, destructive_hint=destructive,
                                          idempotent_hint=read_only or idempotent, open_world_hint=False)
            server.tool(annotations=annotations)(wrapper)
            return fn

        return register

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request):
        return JSONResponse({"status": "healthy"})

    # --- Hierarchy & KPIs ---

    @tool(read_only=True)
    def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """KPI folder hierarchy (with each folder's indicators), optionally from root_id / limited to depth."""
        return kpi_crud.get_kpi_tree(root_id=root_id, depth=depth)

    @tool()
    def add_kpi_node(name: str, parent_id: Optional[int] = None, custom_level_label: Optional[str] = None) -> Dict[str, Any]:
        """Creates a folder in the KPI hierarchy (parent_id null = top level)."""
        return {"node_id": kpi_crud.add_kpi_node(parent_id, name, custom_level_label), "name": name.strip()}

    @tool()
    def create_kpi_indicator(
        node_id: int,
        name: str,
        description: Optional[str] = None,
        calculation_type: CalcType = "Sum",
        unit_of_measure: Optional[str] = None,
        visible: bool = True,
        owner: Optional[str] = None,
        direction: Direction = "Higher is Better",
        threshold_json: Optional[Dict[str, Any]] = None,
        target_granularity: str = "Monthly",
        target_count: Annotated[int, Field(ge=1, le=10)] = 1,
        time_filter_type: Literal["None", "Rolling"] = "None",
        time_filter_value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a KPI (indicator + spec) in a folder. Sum/Count split additively; Average/Last/Min/Max are levels.

        threshold_json e.g. {"warning_margin": 0.05, "error_margin": 0.15}; time_filter "Rolling" + "30" =
        status over the last 30 days of actuals. To make it a formula KPI, set formula_string with update_kpi_spec.
        """
        return kpi_crud.create_kpi_indicator(
            node_id=node_id, name=name, description=description, calculation_type=calculation_type,
            unit_of_measure=unit_of_measure, visible=visible, owner=owner, direction=direction,
            threshold_json=threshold_json, target_granularity=target_granularity, target_count=target_count,
            time_filter_type=time_filter_type, time_filter_value=time_filter_value, changed_by=_actor(),
        )

    @tool(read_only=True)
    def list_kpis(only_visible: bool = False, plant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Active KPI specs (optionally visible-only, or without those disabled for a plant)."""
        return data_retriever.get_all_kpis_detailed(only_visible=only_visible, plant_id=plant_id)

    @tool(read_only=True)
    def get_kpi(kpi_id: int, plant_id: Optional[int] = None) -> Dict[str, Any]:
        """One KPI's full spec (formula, thresholds, target count and labels, hierarchy path)."""
        kpi = data_retriever.get_kpi_detailed_by_id(kpi_id, plant_id=plant_id)
        if not kpi:
            raise ToolError(f"KPI {kpi_id} not found")
        return kpi

    @tool(idempotent=True)
    def update_kpi_spec(kpi_id: int, data_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates spec fields, e.g. {"unit_of_measure": "t", "formula_string": "[3] / [4]"}.

        Allowed: description, calculation_type, unit_of_measure, visible, formula_json, formula_string,
        default_distribution_profile, owner, direction, threshold_json, target_granularity, target_count,
        time_filter_type, time_filter_value, target_labels (JSON like {"1": "Budget", "2": "Committed"}).
        A formula makes the KPI calculated (validated: syntax, known KPIs, no cycles); an empty one clears it.
        """
        unknown = sorted(set(data_updates) - set(kpi_crud.UPDATABLE_SPEC_FIELDS))
        if unknown:
            raise ToolError(f"Field(s) can't be updated: {', '.join(unknown)}")
        if not kpi_crud.update_kpi_spec_extended(kpi_id, data_updates, changed_by=_actor()):
            raise ToolError(f"KPI {kpi_id} not found")
        return {"status": "success", "kpi_id": kpi_id, "updated": True}

    @tool(destructive=True, idempotent=True)
    def soft_delete_kpi(kpi_id: int) -> Dict[str, Any]:
        """Hides a KPI everywhere (its targets, actuals and history are kept)."""
        if not kpi_crud.soft_delete_kpi(kpi_id, changed_by=_actor()):
            raise ToolError(f"KPI {kpi_id} not found")
        return {"status": "success", "kpi_id": kpi_id, "is_active": False}

    @tool(read_only=True)
    def get_kpi_definition_history(kpi_id: int) -> List[Dict[str, Any]]:
        """Audit trail of a KPI's definition: who created/changed/deleted it, when, old and new values."""
        return history_service.get_definition_history(kpi_id)

    @tool(read_only=True)
    def get_kpi_target_history(kpi_id: int, plant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Audit trail of a KPI's annual target values (optionally for one plant)."""
        return history_service.get_target_history(kpi_id, plant_id=plant_id)

    @tool(read_only=True)
    def get_kpi_visibility(kpi_id: int) -> List[Dict[str, Any]]:
        """Per-plant visibility overrides [{plant_id, is_enabled}]. Plants not listed see the KPI."""
        return visibility_crud.get_plant_visibility_for_kpi(kpi_id)

    @tool(idempotent=True)
    def set_kpi_visibility(kpi_id: int, visibility: List[VisibilityEntry]) -> Dict[str, Any]:
        """Enables/disables a KPI for specific plants (upsert; other plants are unchanged)."""
        if not visibility_crud.update_plant_visibility(kpi_id, [v.model_dump() for v in visibility]):
            raise ToolError(f"KPI {kpi_id} not found")
        return {"status": "success", "kpi_id": kpi_id}

    @tool(read_only=True)
    def list_units_of_measure() -> List[Dict[str, Any]]:
        """The registry of units of measure."""
        return kpi_crud.get_all_units_of_measure()

    @tool(idempotent=True)
    def create_unit_of_measure(name: Annotated[str, Field(min_length=1, max_length=50)]) -> Dict[str, Any]:
        """Adds a unit of measure (or returns the existing one)."""
        return kpi_crud.add_unit_of_measure(name)

    # --- Plants ---

    @tool(read_only=True)
    def list_plants(visible_only: bool = False) -> List[Dict[str, Any]]:
        """Facilities/plants."""
        return data_retriever.get_all_plants(visible_only=visible_only)

    @tool()
    def create_plant(name: str, description: str = "", visible: bool = True, color: HexColor = "#3b82f6") -> Dict[str, Any]:
        """Adds a facility/plant."""
        return {"plant_id": plants_crud.add_plant(name, description, visible, color), "name": name.strip()}

    @tool(idempotent=True)
    def update_plant(plant_id: int, name: Optional[str] = None, description: Optional[str] = None,
                     visible: Optional[bool] = None, color: Optional[HexColor] = None) -> Dict[str, Any]:
        """Edits a plant; omitted fields keep their current value."""
        current = plants_crud.get_plant_by_id(plant_id)
        if not current:
            raise ToolError(f"Plant {plant_id} not found")
        plants_crud.update_plant(
            plant_id,
            current["name"] if name is None else name,
            current["description"] if description is None else description,
            bool(current["visible"]) if visible is None else visible,
            current["color"] if color is None else color,
        )
        return {"status": "success", "plant_id": plant_id}

    @tool(destructive=True)
    def delete_plant(plant_id: int, force: bool = False) -> Dict[str, Any]:
        """Deletes a plant. Refuses if it has targets/actuals unless force=true, which deletes those too."""
        plants_crud.delete_plant(plant_id, force_delete_if_referenced=force)
        return {"status": "success", "plant_id": plant_id}

    # --- Targets ---

    @tool()
    def update_target_value(kpi_id: int, plant_id: int, year: int, value: float, target_number: int = 1) -> Dict[str, Any]:
        """Sets a KPI's annual target for a plant/year and recalculates formula KPIs and all periodic targets.
        For several KPIs/plants at once, or to set repartition settings, use save_annual_targets."""
        annual_management.save_annual_targets(
            year=year, plant_id=plant_id,
            targets_data_map={str(kpi_id): {"targets": [{"target_number": target_number, "target_value": value}]}},
            initiator_kpi_spec_id=kpi_id, changed_by=_actor(),
        )
        return {"status": "success", "kpi_id": kpi_id, "plant_id": plant_id, "year": year, "target_number": target_number}

    @tool()
    def save_annual_targets(
        year: Annotated[int, Field(ge=1900, le=2200)],
        plant_id: Union[int, List[int]],
        targets_by_kpi: Dict[str, KpiTargets],
    ) -> Dict[str, Any]:
        """Saves annual targets for one plant or a list of plants (broadcast), atomically.

        targets_by_kpi is keyed by kpi_id, e.g. {"3": {"targets": [{"target_number": 1, "target_value": 1200}],
        "repartition_logic": "Month", "repartition_values": {"January": 10, ...}}}. Formula KPIs and all
        periodic targets are recalculated. Calculated (formula) KPIs can't be given values.
        """
        data: Dict[str, Any] = {}
        for kpi_id, entry in targets_by_kpi.items():
            item = entry.model_dump(exclude_none=True)
            item["targets"] = [t.model_dump() for t in entry.targets]
            data[str(kpi_id)] = item
        annual_management.save_annual_targets(year=year, plant_id=plant_id, targets_data_map=data, changed_by=_actor())
        return {"status": "success", "year": year, "plant_id": plant_id, "kpis": sorted(data, key=int)}

    @tool(read_only=True)
    def get_annual_target(year: int, plant_id: int, kpi_id: int) -> Optional[Dict[str, Any]]:
        """A KPI's annual target record for a plant/year with every target scenario's value (null if none)."""
        return data_retriever.get_annual_target_entry(year, plant_id, kpi_id)

    @tool(read_only=True)
    def list_annual_targets(plant_id: int, year: int) -> List[Dict[str, Any]]:
        """Every KPI's annual target record for a plant and year."""
        return data_retriever.get_annual_targets(plant_id, year)

    @tool(read_only=True)
    def get_available_target_numbers(year: int, plant_id: int, kpi_id: int) -> List[Any]:
        """Which target numbers (scenarios) have values for a KPI/plant/year."""
        return data_retriever.get_available_target_numbers_for_kpi(year, plant_id, kpi_id)

    @tool(read_only=True)
    def list_years() -> List[Any]:
        """Years that have annual targets."""
        return data_retriever.get_distinct_years()

    @tool(read_only=True)
    def get_periodic_targets(kpi_id: int, plant_id: int, year: int, period_type: PeriodType, target_number: int = 1) -> List[Dict[str, Any]]:
        """A KPI's repartitioned targets for one plant, chronologically: [{period, target_value}]."""
        return data_retriever.get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_number)

    @tool(read_only=True)
    def get_periodic_targets_all_plants(kpi_id: int, period_type: PeriodType, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """A KPI's repartitioned targets across all plants."""
        return data_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year=year)

    @tool(read_only=True)
    def get_lean_targets() -> List[Dict[str, Any]]:
        """Every periodic target as flat BI-friendly rows (Indicator, Plant, Year, PeriodType, PeriodValue, TargetID, Value)."""
        return data_retriever.get_lean_targets()

    # --- Actuals & performance ---

    @tool(idempotent=True)
    def record_actual(kpi_id: int, plant_id: int, measurement_date: IsoDate, actual_value: float) -> Dict[str, Any]:
        """Records (or overwrites) a measured value for a KPI/plant/day."""
        _kpi(kpi_id)
        if not plants_crud.get_plant_by_id(plant_id):
            raise ToolError(f"Plant {plant_id} not found")
        row_id = actuals_service.record_actual_measurement(kpi_id, plant_id, measurement_date, actual_value)
        return {"status": "success", "id": row_id}

    @tool(read_only=True)
    def list_actuals(kpi_id: int, plant_id: int, start_date: Optional[IsoDate] = None,
                     end_date: Optional[IsoDate] = None) -> List[Dict[str, Any]]:
        """Measured values for a KPI/plant, oldest first, optionally within [start_date, end_date]."""
        return actuals_service.get_actual_measurements(kpi_id, plant_id, start_date, end_date)

    @tool(read_only=True)
    def get_performance_status(kpi_id: int, plant_id: int, target_value: Optional[float] = None) -> Dict[str, Any]:
        """Latest actual vs target (on_track / warning / out_of_range) with trend."""
        _kpi(kpi_id)
        return data_retriever.get_kpi_performance_status(kpi_id=kpi_id, plant_id=plant_id, target_value=target_value)

    # --- Global split templates ---

    @tool(read_only=True)
    def list_global_splits(year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Split templates (with year: those covering it; year-agnostic presets always included)."""
        return splits_crud.get_all_global_splits(year=year)

    @tool(read_only=True)
    def get_global_split(split_id: int) -> Dict[str, Any]:
        """One split template."""
        split = splits_crud.get_global_split(split_id)
        if not split:
            raise ToolError(f"Global split {split_id} not found")
        return split

    @tool()
    def create_global_split(
        name: str,
        repartition_logic: SplitLogic,
        distribution_profile: Profile,
        repartition_values: Optional[Dict[str, float]] = None,
        profile_params: Optional[Dict[str, Any]] = None,
        years: Optional[List[int]] = None,
        kpi_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Creates a split template. Weights are per-period percentages keyed by month name
        ("January"...), "Q1".."Q4" or "W01".."W53". Omit years for a year-agnostic template.
        kpi_ids links KPIs to it right away (their targets are recalculated)."""
        links = _split_links(kpi_ids)
        split_id = splits_crud.add_global_split(
            name=name, repartition_logic=repartition_logic, repartition_values=repartition_values or {},
            distribution_profile=distribution_profile, profile_params=profile_params or {}, years=years,
            afflicted_indicators=links,
        )
        if links:
            annual_management.recalculate_indicators([link["indicator_id"] for link in links], changed_by=_actor())
        return {"split_id": split_id, "name": name.strip()}

    @tool(idempotent=True)
    def update_global_split(
        split_id: int,
        name: Optional[str] = None,
        repartition_logic: Optional[SplitLogic] = None,
        distribution_profile: Optional[Profile] = None,
        repartition_values: Optional[Dict[str, float]] = None,
        profile_params: Optional[Dict[str, Any]] = None,
        years: Optional[List[int]] = None,
        kpi_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Updates the given fields of a split template (kpi_ids replaces its linked KPIs);
        every KPI using it before or after is recalculated."""
        before = _split_indicator_ids(split_id)
        if not splits_crud.update_global_split(
            split_id, name=name, repartition_logic=repartition_logic, repartition_values=repartition_values,
            distribution_profile=distribution_profile, profile_params=profile_params, years=years,
            afflicted_indicators=_split_links(kpi_ids),
        ):
            raise ToolError(f"Global split {split_id} not found")
        annual_management.recalculate_indicators(before | _split_indicator_ids(split_id), changed_by=_actor())
        return {"status": "success", "split_id": split_id}

    @tool(destructive=True)
    def delete_global_split(split_id: int) -> Dict[str, Any]:
        """Deletes a split template; KPIs that used it fall back to an even split and are recalculated."""
        if not splits_crud.get_global_split(split_id):
            raise ToolError(f"Global split {split_id} not found")
        annual_management.recalculate_indicators(splits_crud.delete_global_split(split_id), changed_by=_actor())
        return {"status": "success", "split_id": split_id}

    @tool(read_only=True)
    def get_global_split_kpis(split_id: int) -> List[Dict[str, Any]]:
        """KPIs linked to a split template: [{kpi_id, indicator_id, name, override_distribution_profile}]."""
        if not splits_crud.get_global_split(split_id):
            raise ToolError(f"Global split {split_id} not found")
        by_indicator = {k["indicator_id"]: k for k in data_retriever.get_all_kpis_detailed()}
        out = []
        for link in splits_crud.get_indicators_for_global_split(split_id):
            kpi = by_indicator.get(link["indicator_id"])
            out.append({
                "kpi_id": kpi["id"] if kpi else None,
                "indicator_id": link["indicator_id"],
                "name": kpi["indicator_name"] if kpi else None,
                "override_distribution_profile": link.get("override_distribution_profile"),
            })
        return out

    @tool(idempotent=True)
    def set_global_split_kpis(split_id: int, kpi_ids: List[int]) -> Dict[str, Any]:
        """Replaces the KPIs linked to a split template; KPIs added or removed are recalculated."""
        if not splits_crud.get_global_split(split_id):
            raise ToolError(f"Global split {split_id} not found")
        before = _split_indicator_ids(split_id)
        links = _split_links(kpi_ids) or []
        splits_crud.update_global_split_indicators(split_id, links)
        annual_management.recalculate_indicators(before | {link["indicator_id"] for link in links}, changed_by=_actor())
        return {"status": "success", "split_id": split_id, "kpi_ids": kpi_ids}

    @tool(read_only=True)
    def get_curve_weight_suggestions(profile: Profile, logic: SplitLogic, year: Optional[int] = None) -> Dict[str, float]:
        """Suggested per-period weights (percent) for a curve -- a starting point for a template."""
        return splits_crud.get_curve_weight_suggestions(profile, logic, year)

    @tool(read_only=True)
    def get_kpi_global_split(kpi_id: int) -> List[Dict[str, Any]]:
        """The split template assigned to a KPI (empty list = default even split)."""
        return splits_crud.get_global_splits_for_indicator(_kpi(kpi_id)["indicator_id"])

    @tool(idempotent=True)
    def set_kpi_global_split(kpi_id: int, global_split_id: Optional[int] = None) -> Dict[str, Any]:
        """Assigns (or clears, with null) a KPI's split template and recalculates its targets."""
        splits_crud.set_kpi_global_split(_kpi(kpi_id)["indicator_id"], global_split_id)
        annual_management.recalculate_kpis([kpi_id], changed_by=_actor())
        return {"status": "success", "kpi_id": kpi_id, "global_split_id": global_split_id}

    # --- Seasonality predictor ---

    @tool(read_only=True)
    def analyze_seasonality(
        target_cols: List[str],
        date_col: str,
        period_type: AnalysisPeriod = "Month",
        feature_cols: Optional[List[str]] = None,
        csv_text: Optional[str] = None,
        file_base64: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Derives seasonal weights from historical data: races OLS, Ridge and Random Forest on the target
        column(s) (with optional driver columns) and returns weights in percent keyed like split templates
        ("January".., "Q1".., "W01"..), ready for create_global_split's repartition_values.

        Pass the data as csv_text, or as file_base64 with a filename ending in .csv or .xlsx.
        """
        if (csv_text is None) == (file_base64 is None):
            raise ToolError("Pass exactly one of csv_text or file_base64.")
        if csv_text is not None:
            data, suffix = csv_text.encode("utf-8"), ".csv"
            if len(data) > app_settings.max_upload_bytes():
                raise ToolError(f"The dataset is larger than {app_settings.max_upload_bytes() // (1024 * 1024)} MB.")
        else:
            suffix = Path(filename or "").suffix.lower()
            if suffix not in (".csv", ".txt", ".xlsx", ".xls"):
                raise ToolError("filename must end in .csv or .xlsx.")
            data = _decode_base64(file_base64, "dataset")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / f"upload{suffix}"
            path.write_bytes(data)
            weights, coefficients, r_squared, plot_df, model = split_analyzer.analyze_seasonality_from_file(
                str(path), [c.strip() for c in target_cols], [c.strip() for c in feature_cols or []],
                date_col.strip(), period_type,
            )
        return {"weights": weights, "coefficients": coefficients, "r_squared": r_squared,
                "plot_data": plot_df.to_dict("records"), "winning_model": model, "period_type": period_type}

    # --- KPI indicator templates ---

    @tool(read_only=True)
    def list_templates() -> List[Dict[str, Any]]:
        """KPI indicator templates (reusable sets of KPI definitions applied to folders)."""
        return data_retriever.get_kpi_indicator_templates()

    @tool()
    def create_template(name: str, description: str = "") -> Dict[str, Any]:
        """Creates an empty KPI indicator template."""
        return {"template_id": templates_crud.add_kpi_indicator_template(name, description), "name": name.strip()}

    @tool(destructive=True)
    def delete_template(template_id: int) -> Dict[str, Any]:
        """Deletes a template and unlinks its folders (KPIs created from it are kept)."""
        if not templates_crud.delete_kpi_indicator_template(template_id):
            raise ToolError(f"Template {template_id} not found")
        return {"status": "success", "template_id": template_id}

    @tool(read_only=True)
    def list_template_indicators(template_id: int) -> List[Dict[str, Any]]:
        """The KPI definitions in a template."""
        return data_retriever.get_template_defined_indicators(template_id)

    @tool()
    def add_template_indicator(template_id: int, name: str, calculation_type: CalcType = "Sum",
                               unit_of_measure: Optional[str] = None, visible: bool = True,
                               description: str = "") -> Dict[str, Any]:
        """Adds a KPI definition to a template; folders using the template get the KPI too."""
        definition_id = templates_crud.add_indicator_definition_to_template(
            template_id, name, calculation_type, unit_of_measure, visible, description, changed_by=_actor())
        return {"status": "success", "template_id": template_id, "definition_id": definition_id}

    @tool(idempotent=True)
    def update_template_indicator(definition_id: int, template_id: int, name: str, calculation_type: CalcType,
                                  unit_of_measure: Optional[str] = None, visible: bool = True,
                                  description: str = "") -> Dict[str, Any]:
        """Edits a template's KPI definition; the change propagates to KPIs in folders using the template."""
        if not templates_crud.update_indicator_definition_in_template(
                definition_id, template_id, name, calculation_type, unit_of_measure, visible, description,
                changed_by=_actor()):
            raise ToolError(f"Template indicator {definition_id} not found in template {template_id}")
        return {"status": "success", "definition_id": definition_id}

    @tool(destructive=True)
    def remove_template_indicator(definition_id: int) -> Dict[str, Any]:
        """Removes a KPI definition from a template; the matching KPIs in linked folders are soft-deleted."""
        if not templates_crud.remove_indicator_definition_from_template(definition_id, changed_by=_actor()):
            raise ToolError(f"Template indicator {definition_id} not found")
        return {"status": "success", "definition_id": definition_id}

    @tool(idempotent=True)
    def apply_template(template_id: int, node_id: int) -> Dict[str, Any]:
        """Links a folder to a template and creates its KPIs there (later template edits propagate)."""
        applied = templates_crud.apply_template_to_node(template_id, node_id, changed_by=_actor())
        return {"status": "success", "template_id": template_id, "node_id": node_id, "applied": applied}

    # --- Data utilities ---

    @tool(read_only=True)
    def export_csv(table: ExportTable) -> Dict[str, Any]:
        """One human-readable table as CSV text (for analysis/BI; not restorable -- use export_backup)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            if table == "Lean Targets":
                path = export_manager.export_lean_data_to_csv(tmp_dir)
            else:
                path = export_manager.export_single_table(table, tmp_dir)
            return {"filename": path.name, "csv": path.read_text(encoding="utf-8")}

    @tool(read_only=True)
    def export_backup() -> Dict[str, Any]:
        """Full backup of all KPI data as a base64 ZIP (restorable with restore_backup; user accounts excluded)."""
        data = export_manager.build_backup_zip()
        return {"filename": "kpi_backup.zip", "size_bytes": len(data), "zip_base64": base64.b64encode(data).decode("ascii")}

    @tool(destructive=True)
    def restore_backup(zip_base64: str) -> Dict[str, Any]:
        """Admin only. REPLACES all KPI data with a backup from export_backup (one transaction). The current
        databases are snapshotted to <databases>/backups/pre-restore-<timestamp>/ first."""
        access.require_admin(_caller())
        data = _decode_base64(zip_base64, "backup")
        result = import_manager.restore_from_zip(data, max_uncompressed_bytes=app_settings.max_upload_bytes() * 25)
        return {"status": "success", **result}

    # --- Users & API keys (same rules as the REST API: src/user_management/access.py) ---

    @tool(read_only=True)
    def whoami() -> Dict[str, Any]:
        """The account this connection acts as (the API key's owner), or the local stdio operator."""
        caller = dict(_caller())
        caller["transport"] = "http" if get_access_token() is not None else "stdio"
        return caller

    @tool(read_only=True)
    def list_users(active_only: bool = False) -> List[Dict[str, Any]]:
        """Users. Admins get full profiles; everyone else gets id/name/color/is_active only."""
        return access.list_users(_caller(), active_only=active_only)

    @tool()
    def create_user(name: str, password: Password, email: str = "", color: HexColor = "#3b82f6",
                    is_admin: bool = False) -> Dict[str, Any]:
        """Admin only: creates an account (the user can change the password after logging in)."""
        return {"id": access.create_user(_caller(), name, password, email, color, is_admin=is_admin), "name": name.strip()}

    @tool(idempotent=True)
    def update_user(user_id: int, name: Optional[str] = None, email: Optional[str] = None,
                    color: Optional[HexColor] = None, is_active: Optional[bool] = None,
                    is_admin: Optional[bool] = None) -> Dict[str, Any]:
        """Edits a profile; omitted fields are unchanged. Users edit their own name/email/color;
        admins can edit anyone, including is_active (deactivating revokes sessions and keys) and is_admin."""
        caller = _caller()
        access.require_self_or_admin(caller, user_id)
        current = user_crud.get_user_by_id(user_id)
        if not current:
            raise ToolError(f"User {user_id} not found")
        access.update_user(
            caller, user_id,
            current["name"] if name is None else name,
            current["email"] if email is None else email,
            current["color"] if color is None else color,
            current["is_active"] if is_active is None else is_active,
            is_admin,
        )
        return {"status": "success", "id": user_id}

    @tool(idempotent=True)
    def reset_user_password(user_id: int, new_password: Password) -> Dict[str, Any]:
        """Admin only: sets a new password for a user and signs them out everywhere."""
        access.reset_password(_caller(), user_id, new_password)
        return {"status": "success", "id": user_id}

    @tool()
    def change_my_password(current_password: str, new_password: Password) -> Dict[str, Any]:
        """Changes the password of the API key's owner and signs out their browser sessions (HTTP only)."""
        caller = _caller()
        if caller["id"] is None:
            raise ToolError("Not available over stdio: there is no signed-in account. Use reset_user_password.")
        user_crud.change_password(caller["id"], current_password, new_password)
        return {"status": "success"}

    @tool(read_only=True)
    def list_api_keys(user_id: int) -> List[Dict[str, Any]]:
        """A user's MCP API keys (prefix, label, last use; never the key itself). Your own, or anyone's as admin."""
        return access.list_api_keys(_caller(), user_id)

    @tool()
    def create_api_key(user_id: int, label: Annotated[str, Field(min_length=1, max_length=100)]) -> Dict[str, Any]:
        """Mints an MCP API key for yourself (admins: for anyone). raw_key is returned ONCE -- store it."""
        return access.create_api_key(_caller(), user_id, label)

    @tool(destructive=True, idempotent=True)
    def revoke_api_key(key_id: int) -> Dict[str, Any]:
        """Revokes an API key (yours, or anyone's as admin). It stops working immediately."""
        access.revoke_api_key(_caller(), key_id)
        return {"status": "success", "id": key_id}

    return server


def build_http_app(port: int = 8001, host: str = "127.0.0.1"):
    """The Streamable HTTP ASGI app (API-key auth), as served by `--http`."""
    security = None
    if host not in ("127.0.0.1", "localhost", "::1"):
        allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",") if h.strip()]
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed,
            allowed_origins=[f"http://{h}" for h in allowed] + [f"https://{h}" for h in allowed],
        )
    return build_server(http=True, port=port).streamable_http_app(
        stateless_http=True, json_response=True, host=host, transport_security=security
    )


def main(argv: Optional[List[str]] = None):
    argv = sys.argv[1:] if argv is None else argv
    transport = "http" if "--http" in argv else os.environ.get("MCP_TRANSPORT", "stdio").lower()
    setup_databases()
    if transport != "http":
        build_server(http=False).run("stdio")
        return

    import uvicorn

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8001"))
    print(f"MCP server (Streamable HTTP) on http://{host}:{port}/mcp", file=sys.stderr)
    uvicorn.run(build_http_app(port=port, host=host), host=host, port=port)


if __name__ == "__main__":
    main()
