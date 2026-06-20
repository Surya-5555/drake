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


# Cache of loaded external specs to avoid re-reading files
external_specs_cache: Dict[str, Any] = {}

def resolve_refs(obj: Any, spec: Dict[str, Any], seen: set = None, root_dir: Path = None) -> Any:
    """Recursively resolves $ref (both internal and external) in OpenAPI schema."""
    # AUDIT1.MD Fix: Implement a robust $ref resolver for Redfish OpenAPI specs (recursive, following internal & external references)
    if seen is None:
        seen = set()
    
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref in seen:
                # Prevent infinite recursion in circular schemas
                return {"type": "object", "description": f"Circular reference to {ref}"}
            seen.add(ref)
            
            # Split into file path and internal pointer path
            if "#" in ref:
                file_part, pointer_part = ref.split("#", 1)
            else:
                file_part, pointer_part = ref, ""
                
            pointer_parts = [p for p in pointer_part.split("/") if p]
            
            if file_part:
                # External reference
                if root_dir is not None:
                    ext_file_path = root_dir / file_part
                else:
                    ext_file_path = Path(file_part)
                
                # Normalize path to use as cache key
                cache_key = str(ext_file_path.resolve())
                if cache_key in external_specs_cache:
                    ext_spec = external_specs_cache[cache_key]
                else:
                    ext_spec = {}
                    if ext_file_path.exists():
                        try:
                            with open(ext_file_path, "r", encoding="utf-8") as f:
                                if ext_file_path.suffix.lower() in [".yaml", ".yml"]:
                                    ext_spec = yaml.safe_load(f)
                                elif ext_file_path.suffix.lower() == ".json":
                                    ext_spec = json.load(f)
                        except Exception as e:
                            logger.warning(f"Failed to load external ref file {ext_file_path}: {e}")
                    external_specs_cache[cache_key] = ext_spec
                
                # Find the referenced part in the external spec
                cur = ext_spec
                for p in pointer_parts:
                    if isinstance(cur, dict):
                        cur = cur.get(p, {})
                    else:
                        cur = {}
                
                # Resolve recursively on the resolved target
                res = resolve_refs(cur, ext_spec, seen, ext_file_path.parent)
                seen.remove(ref)
                return res
            else:
                # Internal reference
                cur = spec
                for p in pointer_parts:
                    if isinstance(cur, dict):
                        cur = cur.get(p, {})
                    else:
                        cur = {}
                res = resolve_refs(cur, spec, seen, root_dir)
                seen.remove(ref)
                return res
                
        return {k: resolve_refs(v, spec, set(seen), root_dir) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_refs(i, spec, set(seen), root_dir) for i in obj]
    return obj


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

    def _resolve_refs(self, schema: Any, root_spec: Dict[str, Any], depth: int = 0) -> Any:
        """Recursively resolves OpenAPI $ref pointers and merges allOf/oneOf/anyOf schemas."""
        # AUDIT1.MD Fix: Implement a robust $ref resolver for nested and multi-step Redfish schemas (both internal and external pointer types)
        if depth > 8:
            return schema  # Prevent infinite recursive cycles
            
        root_dir = self.file_path.parent
        resolved = resolve_refs(schema, root_spec, root_dir=root_dir)
        
        if isinstance(resolved, dict):
            resolved_dict = {}
            for k, v in resolved.items():
                if k in ["allOf", "oneOf", "anyOf"] and isinstance(v, list):
                    # Combine sub-schemas into the current dictionary
                    combined_props = {}
                    for sub in v:
                        resolved_sub = self._resolve_refs(sub, root_spec, depth + 1)
                        if isinstance(resolved_sub, dict):
                            # Simplistic merge of properties
                            props = resolved_sub.get("properties", {})
                            combined_props.update(props)
                    if combined_props:
                        if "properties" not in resolved_dict:
                            resolved_dict["properties"] = {}
                        resolved_dict["properties"].update(combined_props)
                else:
                    resolved_dict[k] = self._resolve_refs(v, root_spec, depth)
            return resolved_dict
            
        elif isinstance(resolved, list):
            return [self._resolve_refs(item, root_spec, depth) for item in resolved]
        return resolved

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

            # Resolve references in path item (e.g. parameter refs, both internal and external)
            path_item = resolve_refs(path_item, spec, root_dir=self.file_path.parent)
            path_parameters = path_item.get("parameters", [])

            for method, operation in path_item.items():
                if method.lower() not in [
                    "get", "post", "put", "patch", "delete", "options", "head", "trace"
                ]:
                    continue

                if not isinstance(operation, dict):
                    continue
                
                # Resolve entire operation to ensure parameters and requestBody are resolved
                operation = resolve_refs(operation, spec, root_dir=self.file_path.parent)

                operation_params = operation.get("parameters", [])

                # Combine path and operation parameters
                all_parameters = path_parameters + operation_params

                required_params = []
                for p in all_parameters:
                    # We capture all params (required or not) for full orchestration capabilities
                    param_name = p.get("name", "")
                    param_loc = p.get("in", "query")
                    if param_loc not in ["path", "query", "header", "cookie"]:
                        param_loc = "query"
                        
                    # Extract type from schema or directly
                    p_schema = p.get("schema", {})
                    param_type = p_schema.get("type", p.get("type", "string"))
                    
                    required_params.append(
                        RequiredParameter(
                            name=param_name,
                            location=param_loc,
                            param_type=param_type,
                            required=p.get("required", param_loc == "path")
                        )
                    )

                # Extract request schema
                request_schema = None
                req_body = operation.get("requestBody", {})
                if req_body:
                    content = req_body.get("content", {})
                    for content_type, media in content.items():
                        if "json" in content_type:
                            request_schema = media.get("schema")
                            break
                    
                    if request_schema:
                        required_params.append(
                            RequiredParameter(
                                name="body", 
                                location="body", 
                                param_type="object",
                                required=req_body.get("required", False)
                            )
                        )
                        request_schema = self._resolve_refs(request_schema, spec)

                # Extract response schema
                response_schema = None
                responses = operation.get("responses", {})
                for status_code, response in responses.items():
                    if str(status_code).startswith("2"):
                        content = response.get("content", {})
                        for content_type, media in content.items():
                            if "json" in content_type:
                                response_schema = media.get("schema")
                                break
                        if response_schema:
                            response_schema = self._resolve_refs(response_schema, spec)
                            break

                endpoint = EndpointContract(
                    operation_id=operation.get("operationId", f"{method.upper()}_{path}"),
                    method=method.upper(),
                    url=path,
                    required_params=required_params,
                    tags=(
                        operation.get("tags", [])
                        if isinstance(operation.get("tags"), list)
                        else ([operation.get("tags")] if operation.get("tags") is not None else [])
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

    def export_contract_a(self, output_file: str | Path = "contract_a_endpoints.json") -> None:
        """Exports the flattened endpoints to a JSON file."""
        try:
            contract_a = self.parse_and_flatten()
            output_path = Path(output_file)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(contract_a.model_dump_json(indent=2))
            logger.info(f"Successfully exported {contract_a.total_endpoints} endpoints to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export Contract A: {str(e)}")
            raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parse OpenAPI spec and generate Contract A")
    parser.add_argument("input_file", help="Path to the OpenAPI JSON or YAML file")
    parser.add_argument("--output", default="contract_a_endpoints.json", help="Output file path")
    args = parser.parse_args()
    try:
        parser_obj = OpenAPIParser(args.input_file)
        parser_obj.export_contract_a(args.output)
    except Exception as e:
        logger.error(f"Execution failed: {str(e)}")
        exit(1)
