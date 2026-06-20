"""
Dell MCP — SQLite Persistence and Governance Database Manager
==============================================================

Provides standard database schema initialization and query layers for:
  - OpenAPI endpoint indexing (Contract A)
  - Clustered workflows (Contract B) and approval status
  - Governance audit logs
  - Pipeline stages execution status

Includes a modern async SQLAlchemy layer for runtime proxy management.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Integer, ForeignKey, Float

# ===========================================================================
# Synchronous Database Persistence (Legacy & Admin Dashboards)
# ===========================================================================


from sqlalchemy import create_engine, text

# File path resolved relative to project root
DB_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "governance.db"

SYNC_DB_URL = f"sqlite:///{DB_FILE}"

sync_engine = create_engine(SYNC_DB_URL, echo=False)

from sqlalchemy import event

@event.listens_for(sync_engine, "connect")
def set_sqlite_pragma_sync(dbapi_connection, connection_record):
    dbapi_connection.row_factory = sqlite3.Row
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

def get_db_connection():
    """Create a raw connection to the SQLite database via SQLAlchemy engine to share locking."""
    import os

    def clear_wal_shm():
        for ext in ["-wal", "-shm"]:
            f = DB_FILE.parent / f"{DB_FILE.name}{ext}"
            if f.exists():
                try:
                    os.remove(f)
                except Exception:
                    pass

    try:
        conn = sync_engine.raw_connection()
        conn.row_factory = sqlite3.Row
        # Perform a quick integrity check to catch corruption/WAL mismatch early
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check(1);")
        cursor.close()
        return conn
    except Exception as e:
        err_msg = str(e).lower()
        if "malformed" in err_msg or "corrupt" in err_msg:
            clear_wal_shm()
            try:
                conn = sync_engine.raw_connection()
                conn.row_factory = sqlite3.Row
                return conn
            except Exception:
                # If still malformed, the main db file itself is corrupt.
                # Delete the main db file to allow automatic schema regeneration.
                if DB_FILE.exists():
                    try:
                        os.remove(DB_FILE)
                    except Exception:
                        pass
                conn = sync_engine.raw_connection()
                conn.row_factory = sqlite3.Row
                return conn
        raise e



def init_db_sync() -> None:
    """Initialize SQLite tables for governance and audit trails if they don't exist."""
    with get_db_connection() as conn:
        # 1. Pipeline status tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_status (
                stage TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
            """)

        # 2. Ingested OpenAPI endpoints
        conn.execute("""
            CREATE TABLE IF NOT EXISTS endpoints (
                operation_id TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                required_params TEXT NOT NULL,  -- JSON serialized list of strings
                community_id TEXT,
                request_schema TEXT,
                response_schema TEXT
            )
            """)

        # 2b. Graph Edges
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                weight REAL NOT NULL
            )
            """)

        # 3. Discovered workflow clusters
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                system_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                cluster_size INTEGER NOT NULL,
                confidence REAL NOT NULL,
                generated_description TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,  -- 0=pending, 1=approved, 2=rejected
                rejection_reason TEXT,
                community_id TEXT
            )
            """)
        
        # Automatic Migration
        try:
            cursor = conn.execute("PRAGMA table_info(workflows)")
            columns = [row["name"] for row in cursor.fetchall()]
            if columns and "system_name" not in columns:
                conn.execute("ALTER TABLE workflows ADD COLUMN system_name TEXT DEFAULT 'legacy'")
                conn.execute("ALTER TABLE workflows ADD COLUMN display_name TEXT DEFAULT 'legacy'")
                if "workflow_name" in columns:
                    conn.execute("UPDATE workflows SET display_name = workflow_name, system_name = workflow_name")
        except Exception:
            pass

        try:
            cursor = conn.execute("PRAGMA table_info(endpoints)")
            columns = [row["name"] for row in cursor.fetchall()]
            if columns and "request_schema" not in columns:
                conn.execute("ALTER TABLE endpoints ADD COLUMN request_schema TEXT")
                conn.execute("ALTER TABLE endpoints ADD COLUMN response_schema TEXT")
        except Exception:
            pass

        # 4. Audit trail events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                workflow_name TEXT,
                description TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)

        # 5. Endpoint steps
        conn.execute("""
            CREATE TABLE IF NOT EXISTS endpoint_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                operation_id TEXT NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                required_params TEXT NOT NULL,
                request_schema TEXT,
                response_schema TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
            """)

        # 6. Capability registry
        conn.execute("""
            CREATE TABLE IF NOT EXISTS capability_registry (
                operation_id TEXT PRIMARY KEY,
                capability_name TEXT NOT NULL,
                compatibility_domain TEXT NOT NULL,
                default_risk_level TEXT NOT NULL,
                parameters_schema TEXT,
                risk_profile_id TEXT,
                is_manual_override INTEGER DEFAULT 0,
                discovery_confidence REAL DEFAULT 1.0
            )
            """)

        # 7. Compatibility rules
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compatibility_rules (
                id TEXT PRIMARY KEY,
                rule_name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                rule_version INTEGER NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                created_by TEXT NOT NULL,
                superseded_by TEXT,
                change_reason TEXT,
                rule_config TEXT
            )
            """)

        # 8. Compatibility dependencies links
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compatibility_dependencies (
                rule_id TEXT NOT NULL,
                prerequisite_rule_id TEXT NOT NULL,
                PRIMARY KEY (rule_id, prerequisite_rule_id),
                FOREIGN KEY (rule_id) REFERENCES compatibility_rules(id) ON DELETE CASCADE,
                FOREIGN KEY (prerequisite_rule_id) REFERENCES compatibility_rules(id) ON DELETE CASCADE
            )
            """)

        # 9. Device inventory (Stateful Facts cache)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_inventory (
                id TEXT PRIMARY KEY,
                target_ip TEXT UNIQUE NOT NULL,
                device_model TEXT NOT NULL,
                bios_version TEXT NOT NULL,
                lifecycle_controller_version TEXT,
                firmware_inventory TEXT,
                last_scanned TEXT NOT NULL
            )
            """)

        # 10. Compatibility execution reports
        conn.execute("""
            CREATE TABLE IF NOT EXISTS compatibility_reports (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                target_ip TEXT NOT NULL,
                status TEXT NOT NULL,
                compatibility_score INTEGER NOT NULL,
                risk_score INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
            """)

        # 11. Risk profiles
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_profiles (
                id TEXT PRIMARY KEY,
                profile_name TEXT NOT NULL,
                base_risk_level TEXT NOT NULL,
                method_adjustments TEXT,
                order_coefficient REAL NOT NULL,
                max_risk_score INTEGER NOT NULL
            )
            """)

        # 12. Create temporal rules index
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rules_temporal
            ON compatibility_rules(effective_from, effective_to)
            """)

        # Seed default risk profiles if they don't exist
        default_profiles = [
            ("default_read_only", "Default Read-Only", "READ_ONLY", "{}", 0.0, 100),
            ("default_config_change", "Default Config Change", "CONFIG_CHANGE", '{"POST": 5, "PUT": 10, "PATCH": 5}', 1.0, 100),
            ("default_destructive", "Default Destructive", "DESTRUCTIVE", '{"POST": 10, "PUT": 15, "DELETE": 20}', 2.0, 100)
        ]
        for p_id, name, risk, adjustments, coeff, max_score in default_profiles:
            conn.execute(
                """
                INSERT OR IGNORE INTO risk_profiles (id, profile_name, base_risk_level, method_adjustments, order_coefficient, max_risk_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (p_id, name, risk, adjustments, coeff, max_score)
            )

        # Populate default statuses if empty
        for stage in [
            "ingestionStatus",
            "graphStatus",
            "clusteringStatus",
            "mcpRuntimeStatus",
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO pipeline_status (stage, status) VALUES (?, ?)",
                (stage, "idle"),
            )
        conn.commit()




def set_pipeline_status(stage: str, status: str) -> None:
    """Set status of a pipeline stage (ingestion, graph, clustering, mcp)."""
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_status (stage, status) VALUES (?, ?)",
            (stage, status),
        )
        conn.commit()


def get_pipeline_statuses() -> Dict[str, str]:
    """Retrieve all pipeline stages statuses."""
    with sync_engine.connect() as conn:
        result = conn.execute(text("SELECT stage, status FROM pipeline_status"))
        return {row.stage: row.status for row in result.mappings()}


def log_audit_event(
    event_type: str,
    status: str,
    description: str,
    workflow_name: Optional[str] = None,
    actor: str = "system",
) -> None:
    """Create a new audit trail event in the database."""
    event_id = (
        f"evt_{datetime.now(timezone.utc).timestamp()}_{hash(description) & 0xffff}"
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_events (id, event_type, status, workflow_name, description, actor, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                status,
                workflow_name,
                description,
                actor,
                timestamp,
            ),
        )
        conn.commit()


def save_endpoints(endpoints_list: List[Dict[str, Any]]) -> None:
    """Bulk save endpoints (Contract A) and clear old indices."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM endpoints")
        for ep in endpoints_list:
            req_schema = ep.get("request_schema")
            resp_schema = ep.get("response_schema")
            conn.execute(
                """
                INSERT INTO endpoints (operation_id, method, url, required_params, community_id, request_schema, response_schema)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ep["operation_id"],
                    ep["method"],
                    ep["url"],
                    json.dumps(ep.get("required_params", [])),
                    ep.get("community_id"),
                    json.dumps(req_schema) if req_schema is not None else None,
                    json.dumps(resp_schema) if resp_schema is not None else None,
                ),
            )
        conn.commit()


def save_edges(edges_list: List[Dict[str, Any]]) -> None:
    """Bulk save derived graph edges, clearing old ones."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM edges")
        for edge in edges_list:
            conn.execute(
                """
                INSERT INTO edges (source, target, weight)
                VALUES (?, ?, ?)
                """,
                (edge["source"], edge["target"], edge["weight"]),
            )
        conn.commit()


def get_edges() -> List[Dict[str, Any]]:
    """Retrieve all graph edges."""
    with sync_engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM edges"))
        return [dict(row) for row in result.mappings()]


def get_all_endpoints() -> List[Dict[str, Any]]:
    """Retrieve all endpoints with parsed parameters."""
    with sync_engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM endpoints"))
        results = []
        for row in result.mappings():
            results.append(
                {
                    "operation_id": row["operation_id"],
                    "method": row["method"],
                    "url": row["url"],
                    "required_params": json.loads(row["required_params"]),
                    "community_id": row["community_id"],
                }
            )
        return results


def save_workflows(workflows_list: List[Dict[str, Any]]) -> None:
    """Bulk save discovered workflow clusters, preserving approved status if exists."""
    with get_db_connection() as conn:
        # Load existing approval status for preservation
        cursor = conn.execute(
            "SELECT id, approved, rejection_reason, system_name, display_name, generated_description FROM workflows"
        )
        existing = {row["id"]: dict(row) for row in cursor.fetchall()}

        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        for wf in workflows_list:
            wf_id = wf["id"]
            approved = 0
            rejection_reason = None
            system_name = wf.get("system_name") or wf.get("workflow_name") or "unknown_workflow"
            display_name = wf.get("display_name") or wf.get("workflow_name") or system_name
            wf_desc = wf.get("generated_description") or f"Operations workflow for {display_name}"

            if wf_id in existing:
                approved = existing[wf_id]["approved"]
                rejection_reason = existing[wf_id]["rejection_reason"]
                
                # System name never changes after creation
                system_name = existing[wf_id]["system_name"]
                
                # Keep edited values if the user had modified them (only check display name)
                if existing[wf_id]["display_name"] != display_name:
                    display_name = existing[wf_id]["display_name"]
                if existing[wf_id]["generated_description"] != wf_desc:
                    wf_desc = existing[wf_id]["generated_description"]

            conn.execute(
                """
                INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved, rejection_reason, community_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wf_id,
                    system_name,
                    display_name,
                    wf["risk_level"],
                    wf["cluster_size"],
                    wf["confidence"],
                    wf_desc,
                    approved,
                    rejection_reason,
                    wf.get("community_id", wf_id),
                ),
            )

            comm_id = wf.get("community_id", wf_id)
            cursor = conn.execute(
                "SELECT * FROM endpoints WHERE community_id = ? ORDER BY operation_id",
                (comm_id,),
            )
            eps = cursor.fetchall()
            for i, ep in enumerate(eps):
                conn.execute(
                    """
                    INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, request_schema, response_schema, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        wf_id,
                        i + 1,
                        ep["operation_id"],
                        ep["method"],
                        ep["url"],
                        ep["required_params"],
                        None,
                        None,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        conn.commit()


def get_workflows(
    approved_only: bool = False, pending_only: bool = False
) -> List[Dict[str, Any]]:
    """Retrieve workflows and associate underlying endpoints based on community_id."""
    with sync_engine.connect() as conn:
        query = "SELECT * FROM workflows"
        if approved_only:
            query += " WHERE approved = 1"
        elif pending_only:
            query += " WHERE approved = 0"

        wf_result = conn.execute(text(query))
        workflows = [dict(row) for row in wf_result.mappings()]

        # Map endpoints to their workflows by community_id
        ep_result = conn.execute(text("SELECT * FROM endpoints"))
        endpoints = [dict(row) for row in ep_result.mappings()]

        from collections import defaultdict

        community_to_endpoints = defaultdict(list)
        for ep in endpoints:
            if ep["community_id"]:
                community_to_endpoints[ep["community_id"]].append(
                    {
                        "operationId": ep["operation_id"],
                        "method": ep["method"],
                        "url": ep["url"],
                        "path": ep["url"],
                    }
                )

        results = []
        for wf in workflows:
            wf_id = wf["id"]
            comm_id = wf["community_id"] or wf_id
            underlying = community_to_endpoints[comm_id]

            # In case some nodes were direct mapping or Leiden generated empty groups, default to itself
            if not underlying:
                # Search for direct match
                underlying = [
                    {
                        "operationId": ep["operation_id"],
                        "method": ep["method"],
                        "url": ep["url"],
                        "path": ep["url"],
                    }
                    for ep in endpoints
                    if ep["operation_id"] == wf_id
                ]

            results.append(
                {
                    "id": wf_id,
                    "systemName": wf["system_name"],
                    "displayName": wf["display_name"],
                    "workflowName": wf["display_name"],
                    "riskLevel": wf["risk_level"],
                    "clusterSize": len(underlying) or wf["cluster_size"],
                    "confidence": wf["confidence"],
                    "generatedDescription": wf["generated_description"],
                    "approved": wf["approved"],
                    "rejectionReason": wf["rejection_reason"],
                    "communityId": comm_id,
                    "underlyingEndpoints": underlying,
                }
            )
        return results


# ===========================================================================
# Asynchronous Database & ORM Management (SQLAlchemy)
# ===========================================================================

ASYNC_DB_URL = f"sqlite+aiosqlite:///{DB_FILE}"

engine = create_async_engine(ASYNC_DB_URL, echo=False)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class Workflow(Base):
    """
    SQLAlchemy model representing a workflow cluster.
    """

    __tablename__ = "workflows"

    id = Column(String, primary_key=True)
    system_name = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    risk_level = Column(String)
    cluster_size = Column(Integer)
    confidence = Column(Float)
    generated_description = Column(String)
    approved = Column(Integer, default=0)
    rejection_reason = Column(String)
    community_id = Column(String)

    steps = relationship(
        "EndpointStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="EndpointStep.step_order",
    )


class EndpointStep(Base):
    """
    SQLAlchemy model representing a specific API endpoint/step inside a workflow.
    """

    __tablename__ = "endpoint_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_order = Column(Integer, nullable=False)
    operation_id = Column(String, nullable=False)
    method = Column(String, nullable=False)
    url = Column(String, nullable=False)
    required_params = Column(String, nullable=False)
    request_schema = Column(String)
    response_schema = Column(String)
    created_at = Column(String, nullable=False)

    workflow = relationship("Workflow", back_populates="steps")


class CapabilityRegistry(Base):
    __tablename__ = "capability_registry"

    operation_id = Column(String, primary_key=True)
    capability_name = Column(String, nullable=False)
    compatibility_domain = Column(String, nullable=False)
    default_risk_level = Column(String, nullable=False)
    parameters_schema = Column(String)
    risk_profile_id = Column(String)
    is_manual_override = Column(Integer, default=0)
    discovery_confidence = Column(Float, default=1.0)


class CompatibilityRule(Base):
    __tablename__ = "compatibility_rules"

    id = Column(String, primary_key=True)
    rule_name = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    rule_version = Column(Integer, nullable=False)
    effective_from = Column(String, nullable=False)
    effective_to = Column(String)
    created_by = Column(String, nullable=False)
    superseded_by = Column(String)
    change_reason = Column(String)
    rule_config = Column(String)


class CompatibilityDependency(Base):
    __tablename__ = "compatibility_dependencies"

    rule_id = Column(String, primary_key=True)
    prerequisite_rule_id = Column(String, primary_key=True)


class DeviceInventory(Base):
    __tablename__ = "device_inventory"

    id = Column(String, primary_key=True)
    target_ip = Column(String, unique=True, nullable=False)
    device_model = Column(String, nullable=False)
    bios_version = Column(String, nullable=False)
    lifecycle_controller_version = Column(String)
    firmware_inventory = Column(String)
    last_scanned = Column(String, nullable=False)


class CompatibilityReport(Base):
    __tablename__ = "compatibility_reports"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, nullable=False)
    target_ip = Column(String, nullable=False)
    status = Column(String, nullable=False)
    compatibility_score = Column(Integer, nullable=False)
    risk_score = Column(Integer, nullable=False)
    report_json = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id = Column(String, primary_key=True)
    profile_name = Column(String, nullable=False)
    base_risk_level = Column(String, nullable=False)
    method_adjustments = Column(String)
    order_coefficient = Column(Float, nullable=False)
    max_risk_score = Column(Integer, nullable=False)


async def init_db() -> None:
    """Initialize database tables asynchronously if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def sync_governance_to_mcp_proxy() -> None:
    """
    Synchronizes all workflows and their steps from governance.db (sync sqlite)
    to mcp_proxy.db (async SQLAlchemy/aiosqlite).
    Preserves status mapping:
      - 0 -> pending
      - 1 -> approved
      - 2 -> rejected
    """
    import sqlite3
    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload

    # Retrieve data from governance.db
    try:
        with sync_engine.connect() as conn:
            gov_workflows = [dict(row) for row in conn.execute(text("SELECT * FROM workflows")).mappings()]
            gov_endpoints = [dict(row) for row in conn.execute(text("SELECT * FROM endpoints")).mappings()]
    except Exception as e:
        print(f"Error accessing governance db for sync: {e}")
        return

    # Group endpoints by community_id
    from collections import defaultdict

    community_to_endpoints = defaultdict(list)
    for ep in gov_endpoints:
        if ep["community_id"]:
            community_to_endpoints[ep["community_id"]].append(ep)

    async with async_session() as session:
        for gwf in gov_workflows:
            wf_id = gwf["id"]
            comm_id = gwf["community_id"] or wf_id

            # Map status
            status_map = {0: "pending", 1: "approved", 2: "rejected"}
            status_str = status_map.get(gwf["approved"], "pending")

            # Check if this workflow already exists in mcp_proxy.db
            result = await session.execute(
                select(Workflow)
                .where(Workflow.id == wf_id)
                .options(selectinload(Workflow.steps))
            )
            wf = result.scalar_one_or_none()

            if not wf:
                wf = Workflow(
                    id=wf_id,
                    system_name=gwf["system_name"],
                    display_name=gwf["display_name"],
                    generated_description=gwf["generated_description"],
                    risk_level=gwf["risk_level"],
                )
                # Map status correctly (Wait, original Workflow model didn't have status, it had approved. Ah! The DB model doesn't have status, wait... original code mapped it to `status` which isn't a column on Workflow!)
                # Wait, I noticed earlier the Workflow model has `approved` but the sync code was using `status` and `name`! Let me fix this bug while I'm at it.
                wf.approved = gwf["approved"]
                session.add(wf)
            else:
                # Update existing
                wf.display_name = gwf["display_name"]
                wf.generated_description = gwf["generated_description"]
                wf.risk_level = gwf["risk_level"]
                wf.approved = gwf["approved"]

            # Synchronize steps
            underlying = community_to_endpoints[comm_id]
            if not underlying:
                underlying = [ep for ep in gov_endpoints if ep["operation_id"] == wf_id]

            # Clear old steps and recreate
            wf.steps.clear()
            for idx, ep in enumerate(underlying):
                step = EndpointStep(
                    step_order=idx + 1,
                    operation_id=ep["operation_id"],
                    method=ep["method"],
                    url=ep["url"],
                    required_params=ep.get("required_params", "[]"),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                wf.steps.append(step)

        await session.commit()
