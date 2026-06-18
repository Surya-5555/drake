import json
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
            with open(self.file_path, 'r', encoding='utf-8') as f:
                if self.file_path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f)
                elif self.file_path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    raise ValueError("Unsupported file format. Must be .json or .yaml")
        except Exception as e:
            logger.error(f"Failed to parse OpenAPI spec: {str(e)}")
            raise

    def parse_and_flatten(self) -> List[Dict[str, Any]]:
        """
        Flattens the OpenAPI paths into a list of endpoint dictionaries (Contract A).
        Extracts: path, method, summary, description, tags, parameters.
        """
        spec = self.load_spec()
        paths = spec.get("paths", {})
        
        contract_a: List[Dict[str, Any]] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
                
            # Common parameters for all methods in this path
            path_parameters = path_item.get("parameters", [])

            for method, operation in path_item.items():
                # Filter out standard non-HTTP method keys like parameters, servers, etc.
                if method.lower() not in ["get", "post", "put", "patch", "delete", "options", "head", "trace"]:
                    continue
                
                if not isinstance(operation, dict):
                    continue

                operation_params = operation.get("parameters", [])
                
                # Combine path and operation parameters
                all_parameters = path_parameters + operation_params

                endpoint_data = {
                    "path": path,
                    "method": method.upper(),
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": operation.get("tags", []),
                    "parameters": all_parameters
                }
                contract_a.append(endpoint_data)
                
        return contract_a

    def export_contract_a(self, output_file: str | Path = "contract_a_endpoints.json") -> None:
        """Exports the flattened endpoints to a JSON file."""
        try:
            endpoints = self.parse_and_flatten()
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(endpoints, f, indent=2)
            logger.info(f"Successfully exported {len(endpoints)} endpoints to {output_path}")
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
