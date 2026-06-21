import os
import json
import yaml
from pathlib import Path

def analyze_openapi_files():
    results = []
    base_dir = Path('d:/projects/DELL_MCP')
    for ext in ('*.json', '*.yaml', '*.yml'):
        for file in base_dir.rglob(ext):
            if 'node_modules' in file.parts or '.venv' in file.parts or '.git' in file.parts:
                continue
            try:
                content = file.read_text(encoding='utf-8')
                data = None
                if file.suffix == '.json':
                    try:
                        data = json.loads(content)
                    except: pass
                else:
                    try:
                        data = yaml.safe_load(content)
                    except: pass
                
                if isinstance(data, dict) and ('openapi' in data or 'swagger' in data):
                    size = os.path.getsize(file)
                    paths = data.get('paths', {})
                    num_paths = len(paths)
                    num_ops = sum(
                        1 for p in paths.values() if isinstance(p, dict)
                        for k in p.keys() if k.lower() in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head', 'trace']
                    )
                    results.append({
                        'path': str(file.absolute()),
                        'size': size,
                        'paths': num_paths,
                        'ops': num_ops
                    })
            except Exception:
                pass
    
    for r in results:
        print(f"File: {r['path']}")
        print(f"Size: {r['size']} bytes")
        print(f"Paths: {r['paths']}")
        print(f"Operations: {r['ops']}")
        print('-'*40)

analyze_openapi_files()
