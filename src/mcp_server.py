# src/mcp_server.py
"""
Model Context Protocol (MCP) server for the Data Entry KPI Target Manager, built on the
official `mcp` Python SDK -- so any MCP client (Claude Desktop, Claude Code, ...) can connect.

Transports
  * stdio (default): `python -m src.mcp_server` -- a local client spawns it as a subprocess.
    No per-caller identity; writes are attributed to $MCP_STDIO_USER (default "mcp_agent").
  * Streamable HTTP: `python -m src.mcp_server --http` (or MCP_TRANSPORT=http) serves
    http://<MCP_HOST>:<MCP_PORT>/mcp. Every request needs `Authorization: Bearer <api key>`
    (mint one in Data Utilities -> MCP API Keys, or POST /users/{id}/api-keys). The key's
    owner is recorded as `changed_by` on every write -- callers can't claim another identity.

Environment: MCP_HOST (default 127.0.0.1), MCP_PORT (8001), MCP_PUBLIC_URL (the URL clients
use, default http://localhost:<port>), MCP_ALLOWED_HOSTS (comma-separated Host headers
accepted when binding to a non-loopback address, default "localhost:*,127.0.0.1:*").
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

if __package__ in (None, ""):  # `python src/mcp_server.py` -> make `import src...` work
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.auth.middleware.auth_context import get_access_token  # noqa: E402
from mcp.server.auth.provider import AccessToken  # noqa: E402
from mcp.server.auth.settings import AuthSettings  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

from src import data_retriever  # noqa: E402
from src.data_access.setup import setup_databases  # noqa: E402
from src.kpi_management import crud as kpi_crud  # noqa: E402
from src.kpi_management import splits as splits_crud  # noqa: E402
from src.target_management import annual as annual_management  # noqa: E402
from src.user_management import crud as user_crud  # noqa: E402

PeriodType = Literal["Day", "Week", "Month", "Quarter", "Year"]
SplitLogic = Literal["Month", "Quarter", "Week", "Year"]
Profile = Literal[
    "even_distribution", "annual_progressive", "annual_progressive_weekday_bias",
    "true_annual_sinusoidal", "event_based_spikes_or_dips",
]
CalcType = Literal["Sum", "Average", "Last", "Min", "Max", "Count"]
Direction = Literal["Higher is Better", "Lower is Better", "Range"]


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


def _actor() -> str:
    """Who a write is attributed to: the API key's owner over HTTP, $MCP_STDIO_USER over stdio."""
    token = get_access_token()
    if token is not None:
        return token.client_id
    return os.environ.get("MCP_STDIO_USER", "mcp_agent")


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
            "repartition across plants. KPI ids are spec ids (`id` from list_kpis). Saving a target "
            "recalculates formula KPIs and periodic targets automatically."
        ),
        **auth_kwargs,
    )

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request):
        return JSONResponse({"status": "healthy"})

    # --- Hierarchy & KPIs ---

    @server.tool()
    def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """KPI folder hierarchy (with each folder's indicators), optionally from root_id / limited to depth."""
        return kpi_crud.get_kpi_tree(root_id=root_id, depth=depth)

    @server.tool()
    def add_kpi_node(name: str, parent_id: Optional[int] = None, custom_level_label: Optional[str] = None) -> Dict[str, Any]:
        """Creates a folder in the KPI hierarchy (parent_id null = top level)."""
        return {"node_id": kpi_crud.add_kpi_node(parent_id, name, custom_level_label), "name": name}

    @server.tool()
    def create_kpi_indicator(
        node_id: int,
        name: str,
        description: Optional[str] = None,
        calculation_type: CalcType = "Sum",
        unit_of_measure: Optional[str] = None,
        owner: Optional[str] = None,
        direction: Direction = "Higher is Better",
        target_granularity: str = "Monthly",
        target_count: int = 1,
    ) -> Dict[str, Any]:
        """Creates a KPI (indicator + spec) in a folder. Sum/Count split additively; Average/Last/Min/Max are levels."""
        return kpi_crud.create_kpi_indicator(
            node_id=node_id, name=name, description=description, calculation_type=calculation_type,
            unit_of_measure=unit_of_measure, owner=owner, direction=direction,
            target_granularity=target_granularity, target_count=target_count, changed_by=_actor(),
        )

    @server.tool()
    def list_kpis(only_visible: bool = False, plant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Active KPI specs (optionally visible-only, or as visible for a plant)."""
        return data_retriever.get_all_kpis_detailed(only_visible=only_visible, plant_id=plant_id)

    @server.tool()
    def update_kpi_spec(kpi_id: int, data_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates spec fields, e.g. {"unit_of_measure": "t", "formula_string": "[3] / [4]"}.

        Allowed: description, calculation_type, unit_of_measure, visible, formula_json, formula_string,
        default_distribution_profile, owner, direction, threshold_json, target_granularity, target_count,
        time_filter_type, time_filter_value, target_labels. A formula makes the KPI calculated.
        """
        unknown = sorted(set(data_updates) - set(kpi_crud.UPDATABLE_SPEC_FIELDS))
        if unknown:
            raise ValueError(f"Field(s) can't be updated: {', '.join(unknown)}")
        if not kpi_crud.update_kpi_spec_extended(kpi_id, data_updates, changed_by=_actor()):
            raise ValueError(f"KPI {kpi_id} not found")
        return {"status": "success", "kpi_id": kpi_id, "updated": True}

    @server.tool()
    def soft_delete_kpi(kpi_id: int) -> Dict[str, Any]:
        """Hides a KPI everywhere (its targets, actuals and history are kept)."""
        if not kpi_crud.soft_delete_kpi(kpi_id, changed_by=_actor()):
            raise ValueError(f"KPI {kpi_id} not found")
        return {"status": "success", "kpi_id": kpi_id, "is_active": False}

    @server.tool()
    def list_units_of_measure() -> List[Dict[str, Any]]:
        """The registry of units of measure."""
        return kpi_crud.get_all_units_of_measure()

    @server.tool()
    def create_unit_of_measure(name: str) -> Dict[str, Any]:
        """Adds a unit of measure (or returns the existing one)."""
        return kpi_crud.add_unit_of_measure(name)

    @server.tool()
    def list_plants(visible_only: bool = False) -> List[Dict[str, Any]]:
        """Facilities/plants."""
        return data_retriever.get_all_plants(visible_only=visible_only)

    # --- Targets ---

    @server.tool()
    def update_target_value(kpi_id: int, plant_id: int, year: int, value: float, target_number: int = 1) -> Dict[str, Any]:
        """Sets a KPI's annual target for a plant/year and recalculates formula KPIs and all periodic targets."""
        annual_management.save_annual_targets(
            year=year, plant_id=plant_id,
            targets_data_map={str(kpi_id): {"targets": [{"target_number": target_number, "target_value": value}]}},
            initiator_kpi_spec_id=kpi_id, changed_by=_actor(),
        )
        return {"status": "success", "kpi_id": kpi_id, "plant_id": plant_id, "year": year, "target_number": target_number}

    @server.tool()
    def get_annual_target(year: int, plant_id: int, kpi_id: int) -> Optional[Dict[str, Any]]:
        """A KPI's annual target record for a plant/year with every target scenario's value (null if none)."""
        return data_retriever.get_annual_target_entry(year, plant_id, kpi_id)

    @server.tool()
    def get_periodic_targets(kpi_id: int, plant_id: int, year: int, period_type: PeriodType, target_number: int = 1) -> List[Dict[str, Any]]:
        """A KPI's repartitioned targets for one plant, chronologically: [{period, target_value}]."""
        return data_retriever.get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_number)

    @server.tool()
    def get_periodic_targets_all_plants(kpi_id: int, period_type: PeriodType, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """A KPI's repartitioned targets across all plants."""
        return data_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year=year)

    @server.tool()
    def get_performance_status(kpi_id: int, plant_id: int, target_value: Optional[float] = None) -> Dict[str, Any]:
        """Latest actual vs target (on_track / warning / out_of_range) with trend."""
        return data_retriever.get_kpi_performance_status(kpi_id=kpi_id, plant_id=plant_id, target_value=target_value)

    # --- Global split templates ---

    @server.tool()
    def list_global_splits(year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Split templates (with year: those covering it; year-agnostic presets always included)."""
        return splits_crud.get_all_global_splits(year=year)

    @server.tool()
    def get_global_split(split_id: int) -> Optional[Dict[str, Any]]:
        """One split template."""
        return splits_crud.get_global_split(split_id)

    @server.tool()
    def create_global_split(
        name: str,
        repartition_logic: SplitLogic,
        distribution_profile: Profile,
        repartition_values: Optional[Dict[str, float]] = None,
        profile_params: Optional[Dict[str, Any]] = None,
        years: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Creates a split template. Weights are per-period percentages keyed by month name
        ("January"...), "Q1".."Q4" or "W01".."W53". Omit years for a year-agnostic template."""
        split_id = splits_crud.add_global_split(
            name=name, repartition_logic=repartition_logic, repartition_values=repartition_values or {},
            distribution_profile=distribution_profile, profile_params=profile_params or {}, years=years,
        )
        return {"split_id": split_id, "name": name}

    @server.tool()
    def update_global_split(
        split_id: int,
        name: Optional[str] = None,
        repartition_logic: Optional[SplitLogic] = None,
        distribution_profile: Optional[Profile] = None,
        repartition_values: Optional[Dict[str, float]] = None,
        profile_params: Optional[Dict[str, Any]] = None,
        years: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Updates the given fields of a split template; KPIs using it are recalculated."""
        users = {i["indicator_id"] for i in splits_crud.get_indicators_for_global_split(split_id)}
        if not splits_crud.update_global_split(
            split_id, name=name, repartition_logic=repartition_logic, repartition_values=repartition_values,
            distribution_profile=distribution_profile, profile_params=profile_params, years=years,
        ):
            raise ValueError(f"Global split {split_id} not found")
        annual_management.recalculate_indicators(users, changed_by=_actor())
        return {"status": "success", "split_id": split_id}

    @server.tool()
    def delete_global_split(split_id: int) -> Dict[str, Any]:
        """Deletes a split template; KPIs that used it fall back to an even split and are recalculated."""
        if not splits_crud.get_global_split(split_id):
            raise ValueError(f"Global split {split_id} not found")
        annual_management.recalculate_indicators(splits_crud.delete_global_split(split_id), changed_by=_actor())
        return {"status": "success", "split_id": split_id}

    @server.tool()
    def get_curve_weight_suggestions(profile: Profile, logic: SplitLogic, year: Optional[int] = None) -> Dict[str, float]:
        """Suggested per-period weights (percent) for a curve -- a starting point for a template."""
        return splits_crud.get_curve_weight_suggestions(profile, logic, year)

    @server.tool()
    def get_kpi_global_split(kpi_id: int) -> List[Dict[str, Any]]:
        """The split template assigned to a KPI (empty list = default even split)."""
        kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
        if not kpi:
            raise ValueError(f"KPI {kpi_id} not found")
        return splits_crud.get_global_splits_for_indicator(kpi["indicator_id"])

    @server.tool()
    def set_kpi_global_split(kpi_id: int, global_split_id: Optional[int] = None) -> Dict[str, Any]:
        """Assigns (or clears, with null) a KPI's split template and recalculates its targets."""
        kpi = data_retriever.get_kpi_detailed_by_id(kpi_id)
        if not kpi:
            raise ValueError(f"KPI {kpi_id} not found")
        splits_crud.set_kpi_global_split(kpi["indicator_id"], global_split_id)
        annual_management.recalculate_kpis([kpi_id], changed_by=_actor())
        return {"status": "success", "kpi_id": kpi_id, "global_split_id": global_split_id}

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
