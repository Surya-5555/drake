import json
import yaml
import argparse
import csv
from pathlib import Path
from typing import Dict
from pydantic import BaseModel
import logging

from src.core.database import get_workflows

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class Metrics(BaseModel):
    endpoint_count: int
    workflow_count: int
    reduction_percent: float
    coverage_percent: float
    mapped_endpoints: int
    average_endpoints_per_workflow: float
    risk_distribution: Dict[str, int]
    workflow_status: Dict[str, int]
    token_savings_percent: float


def parse_openapi(filepath: Path) -> int:
    """Read total endpoints from original spec dynamically."""
    if not filepath.exists():
        logger.error(f"OpenAPI spec not found at {filepath}")
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            if filepath.suffix in [".yaml", ".yml"]:
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse OpenAPI spec: {e}")
        return 0

    count = 0
    if spec and "paths" in spec:
        for path, path_item in spec["paths"].items():
            if isinstance(path_item, dict):
                for method in ["get", "post", "put", "delete", "patch"]:
                    if method in path_item:
                        count += 1
    return count


def generate_metrics(openapi_path: Path) -> Metrics:
    """Generate metrics by querying the SQLite database and original OpenAPI."""
    endpoint_count = parse_openapi(openapi_path)

    try:
        all_workflows = get_workflows()
    except Exception as e:
        logger.error(f"Failed to fetch workflows from SQLite: {e}")
        all_workflows = []

    approved_workflows = [wf for wf in all_workflows if wf["approved"] == 1]
    pending_workflows = [wf for wf in all_workflows if wf["approved"] == 0]
    rejected_workflows = [wf for wf in all_workflows if wf["approved"] == 2]

    workflow_count = len(approved_workflows)

    mapped_endpoints_set = set()
    for wf in approved_workflows:
        for ep in wf.get("underlyingEndpoints", []):
            mapped_endpoints_set.add(f"{ep.get('method', '')} {ep.get('path', '')}")

    mapped_endpoints = len(mapped_endpoints_set)

    reduction_percent = 0.0
    if endpoint_count > 0:
        reduction_percent = ((endpoint_count - workflow_count) / endpoint_count) * 100

    coverage_percent = 0.0
    if endpoint_count > 0:
        coverage_percent = (mapped_endpoints / endpoint_count) * 100

    avg_endpoints = 0.0
    if workflow_count > 0:
        avg_endpoints = mapped_endpoints / workflow_count

    risk_dist = {"READ_ONLY": 0, "CONFIG_CHANGE": 0, "DESTRUCTIVE": 0}
    for wf in approved_workflows:
        risk = wf.get("riskLevel", "READ_ONLY")
        if risk in risk_dist:
            risk_dist[risk] += 1
        else:
            risk_dist[risk] = 1

    status_dist = {
        "APPROVED": workflow_count,
        "PENDING": len(pending_workflows),
        "REJECTED": len(rejected_workflows),
    }

    raw_tokens = endpoint_count * 50
    workflow_tokens = workflow_count * 100
    token_savings = 0.0
    if raw_tokens > 0:
        token_savings = ((raw_tokens - workflow_tokens) / raw_tokens) * 100

    return Metrics(
        endpoint_count=endpoint_count,
        workflow_count=workflow_count,
        reduction_percent=reduction_percent,
        coverage_percent=coverage_percent,
        mapped_endpoints=mapped_endpoints,
        average_endpoints_per_workflow=avg_endpoints,
        risk_distribution=risk_dist,
        workflow_status=status_dist,
        token_savings_percent=token_savings,
    )


def print_metrics(m: Metrics):
    print("=========================================")
    print("DELL MCP WORKFLOW METRICS")
    print("=========================================")
    print(f"OpenAPI Endpoints: {m.endpoint_count}")
    print(f"Approved Workflows: {m.workflow_count}")
    print(f"Workflow Reduction: {m.reduction_percent:.1f}%")
    print(f"Endpoint Coverage: {m.coverage_percent:.1f}%")
    print(f"Average Endpoints/Workflow: {m.average_endpoints_per_workflow:.0f}")
    print(f"Token Reduction Estimate: {m.token_savings_percent:.1f}%")
    print()
    print("Risk Distribution")
    print("-------------------------")
    for k, v in m.risk_distribution.items():
        print(f"{k}: {v}")
    print()
    print("Workflow Status")
    print("-------------------------")
    for k, v in m.workflow_status.items():
        print(f"{k}: {v}")
    print("=========================================")


def save_json(m: Metrics, path: Path):
    data = {
        "endpoint_count": m.endpoint_count,
        "workflow_count": m.workflow_count,
        "reduction_percent": round(m.reduction_percent, 1),
        "coverage_percent": round(m.coverage_percent, 1),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def save_csv(m: Metrics, path: Path):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["endpoint_count", m.endpoint_count])
        writer.writerow(["workflow_count", m.workflow_count])
        writer.writerow(["reduction_percent", round(m.reduction_percent, 1)])
        writer.writerow(["coverage_percent", round(m.coverage_percent, 1)])
        writer.writerow(["mapped_endpoints", m.mapped_endpoints])
        writer.writerow(
            [
                "average_endpoints_per_workflow",
                round(m.average_endpoints_per_workflow, 1),
            ]
        )
        writer.writerow(["token_savings_percent", round(m.token_savings_percent, 1)])


def main():
    parser = argparse.ArgumentParser(
        description="Dell MCP Workflow Metrics Proof Engine"
    )
    parser.add_argument(
        "--openapi",
        type=Path,
        default=Path("openapi.json"),
        help="Path to OpenAPI spec file",
    )
    parser.add_argument("--json-out", type=Path, help="Path to save metrics.json")
    parser.add_argument("--csv-out", type=Path, help="Path to save metrics.csv")
    args = parser.parse_args()

    metrics = generate_metrics(args.openapi)
    print_metrics(metrics)

    if args.json_out:
        save_json(metrics, args.json_out)
        logger.info(f"Saved JSON metrics to {args.json_out}")
    if args.csv_out:
        save_csv(metrics, args.csv_out)
        logger.info(f"Saved CSV metrics to {args.csv_out}")


if __name__ == "__main__":
    main()
