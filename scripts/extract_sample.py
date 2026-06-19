import yaml
import json
from pathlib import Path


def extract_sample():
    root_dir = Path(__file__).resolve().parent.parent
    input_file = root_dir / "data" / "raw_specs" / "openapi-7.xx.yaml"
    output_dir = root_dir / "data"
    output_file = output_dir / "openapi_sample.json"

    print(f"Loading {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    target_domains = [
        "/redfish/v1/AccountService",
        "/redfish/v1/SessionService",
        "/redfish/v1/Systems",
        "/redfish/v1/Chassis",
        "/redfish/v1/Managers",
        "/redfish/v1/UpdateService",
    ]

    new_paths = {}
    endpoint_count = 0
    max_endpoints = 100

    for path, path_item in spec.get("paths", {}).items():
        if endpoint_count >= max_endpoints:
            break

        for domain in target_domains:
            if path.startswith(domain):
                new_paths[path] = path_item
                endpoint_count += len(
                    [
                        m
                        for m in path_item.keys()
                        if m.lower() in ["get", "post", "put", "patch", "delete"]
                    ]
                )
                break

    sample_spec = {
        "openapi": spec.get("openapi", "3.0.0"),
        "info": spec.get("info", {}),
        "paths": new_paths,
        "components": spec.get("components", {}),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sample_spec, f, indent=2)

    print(
        f"Extracted {endpoint_count} endpoints across {len(new_paths)} paths to {output_file}"
    )


if __name__ == "__main__":
    extract_sample()
