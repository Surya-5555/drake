import json
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.core.models import ContractA, EndpointContract, RequiredParameter

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OpenAPIParser:
    """
    Parses and flattens large Enterprise OpenAPI specification files into a structured
    Contract A format.
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def load_spec(self) -> Dict[str, Any]:
        """Loads the OpenAPI specification from a JSON or YAML file."""
        if not self.file_path.exists():
            logger.error(f"File not found: {self.file_path}")
            raise FileNotFoundError(f"OpenAPI spec file not found at {self.file_path}")

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                if self.file_path.suffix.lower() in [".yaml", ".yml"]:
                    return yaml.safe_load(f)
                elif self.file_path.suffix.lower() == ".json":
                    return json.load(f)
                else:
                    raise ValueError("Unsupported file format. Must be .json or .yaml")
        except Exception as e:
            logger.error(f"Failed to parse OpenAPI spec: {str(e)}")
            raise

    def parse_and_flatten(self) -> ContractA:
        """
        Flattens the OpenAPI paths into a ContractA object.
        Extracts: operation_id, path, method, summary, description, tags, required parameters, and schemas.
        """
        spec = self.load_spec()
        paths = spec.get("paths", {})

        endpoints: List[EndpointContract] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Common parameters for all methods in this path
            path_parameters = path_item.get("parameters", [])

            for method, operation in path_item.items():
                # Filter out standard non-HTTP method keys like parameters, servers, etc.
                if method.lower() not in [
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                    "trace",
                ]:
                    continue

                if not isinstance(operation, dict):
                    continue

                operation_params = operation.get("parameters", [])

                # Combine path and operation parameters
                all_parameters = path_parameters + operation_params

                required_params = []
                for p in all_parameters:
                    # Note: we only capture explicit 'required' or path params.
                    if p.get("required") or p.get("in") == "path":
                        param_name = p.get("name", "")
                        param_loc = p.get("in", "query")
                        # Validate location literal
                        if param_loc not in [
                            "path",
                            "query",
                            "header",
                            "cookie",
                            "body",
                        ]:
                            param_loc = "query"  # fallback
                        required_params.append(
                            RequiredParameter(
                                name=param_name,
                                location=param_loc,
                                param_type=p.get("schema", {}).get("type", "string"),
                            )
                        )

                # Synthesize body parameter if required
                if operation.get("requestBody", {}).get("required"):
                    required_params.append(
                        RequiredParameter(
                            name="body", location="body", param_type="object"
                        )
                    )

                request_schema = (
                    operation.get("requestBody", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                response_schema = (
                    operation.get("responses", {})
                    .get("200", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )

                endpoint = EndpointContract(
                    operation_id=operation.get(
                        "operationId", f"{method.upper()}_{path}"
                    ),
                    method=method.upper(),
                    url=path,
                    required_params=required_params,
                    tags=(
                        operation.get("tags", [])
                        if isinstance(operation.get("tags"), list)
                        else (
                            [operation.get("tags")]
                            if operation.get("tags") is not None
                            else []
                        )
                    ),
                    summary=operation.get("summary", ""),
                    description=operation.get("description", ""),
                    request_schema=request_schema,
                    response_schema=response_schema,
                )
                endpoints.append(endpoint)

        contract_a = ContractA(
            spec_title=spec.get("info", {}).get("title", "Unknown Spec"),
            spec_version=spec.get("info", {}).get("version", "1.0.0"),
            openapi_version=spec.get("openapi", "3.0.0"),
            source_file=self.file_path.name,
            total_endpoints=len(endpoints),
            endpoints=endpoints,
        )
        return contract_a

    def export_contract_a(
        self, output_file: str | Path = "contract_a_endpoints.json"
    ) -> None:
        """Exports the flattened endpoints to a JSON file."""
        try:
            contract_a = self.parse_and_flatten()
            output_path = Path(output_file)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(contract_a.model_dump_json(indent=2))
            logger.info(
                f"Successfully exported {contract_a.total_endpoints} endpoints to {output_path}"
            )
        except Exception as e:
            logger.error(f"Failed to export Contract A: {str(e)}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse OpenAPI spec and generate Contract A"
    )
    parser.add_argument("input_file", help="Path to the OpenAPI JSON or YAML file")
    parser.add_argument(
        "--output", default="contract_a_endpoints.json", help="Output file path"
    )

    args = parser.parse_args()

    try:
        parser_obj = OpenAPIParser(args.input_file)
        parser_obj.export_contract_a(args.output)
    except Exception as e:
        logger.error(f"Execution failed: {str(e)}")
        exit(1)
