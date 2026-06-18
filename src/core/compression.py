import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

def compress_redfish_response(data: Any, seen: Set[int] = None) -> Any:
    """
    Recursively compresses Dell Redfish API responses by:
    1. Stripping @odata keys (e.g., @odata.id)
    2. Removing nulls, empty strings "", and empty lists []
    3. Dropping standard HATEOAS navigation links (Links, Actions) unless explicitly needed.
    
    Args:
        data: The JSON response data (dict, list, or primitive)
        seen: A set of object IDs to prevent infinite recursion
        
    Returns:
        The compressed data structure, heavily reduced for LLM token context.
    """
    if seen is None:
        seen = set()

    # Base case: Handle primitive types and prevent infinite recursion
    if not isinstance(data, (dict, list)):
        return data

    obj_id = id(data)
    if obj_id in seen:
        return None
    seen.add(obj_id)

    try:
        if isinstance(data, dict):
            compressed_dict = {}
            for key, value in data.items():
                # 1. Strip out all keys starting with @odata
                if isinstance(key, str) and key.startswith("@odata"):
                    continue

                # 3. Drop standard HATEOAS navigation links unless they contain direct operational data.
                # Redfish APIs extensively use "Links" and "Actions" to show what operations 
                # or related objects are available. Often this blows up the payload.
                if key in ("Links", "Actions"):
                    continue
                    
                compressed_value = compress_redfish_response(value, seen)

                # 2. Remove keys that have null, empty strings "", or empty lists [] as values
                if compressed_value is None:
                    continue
                if compressed_value == "":
                    continue
                if isinstance(compressed_value, list) and len(compressed_value) == 0:
                    continue
                if isinstance(compressed_value, dict) and len(compressed_value) == 0:
                    continue

                compressed_dict[key] = compressed_value
                
            return compressed_dict

        elif isinstance(data, list):
            compressed_list = []
            for item in data:
                compressed_item = compress_redfish_response(item, seen)
                
                # Exclude nulls, empty strings, empty lists, and empty dicts from arrays as well
                if compressed_item is not None and compressed_item != "" and compressed_item != []:
                    if not (isinstance(compressed_item, dict) and len(compressed_item) == 0):
                        compressed_list.append(compressed_item)
                    
            return compressed_list
    finally:
        # Cleanup the seen set when returning up the call stack
        seen.remove(obj_id)


# =====================================================================
# INTEGRATION SNIPPET
# =====================================================================
# This shows how to integrate the compression utility into the executor.
"""
from typing import Any
import httpx
from src.core.compression import compress_redfish_response

class MockHTTPXExecutor:
    
    async def execute_request(self, request_url: str) -> Any:
        try:
            # Example execution
            # async with httpx.AsyncClient(verify=False) as client:
            #     response = await client.get(request_url)
            #     response.raise_for_status()
            #     raw_data = response.json()
            
            # Simulated response for demonstration
            raw_data = {
                "@odata.id": "/redfish/v1/Systems/1",
                "@odata.context": "/redfish/v1/$metadata#ComputerSystem.ComputerSystem",
                "Id": "1",
                "Name": "System",
                "SystemType": "Physical",
                "AssetTag": "",
                "BiosVersion": "2.12.2",
                "Description": null,
                "Links": {
                    "Chassis": [{"@odata.id": "/redfish/v1/Chassis/System.Embedded.1"}]
                },
                "Actions": {
                    "#ComputerSystem.Reset": {
                        "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
                    }
                },
                "Processors": {"@odata.id": "/redfish/v1/Systems/1/Processors"},
                "Memory": {"@odata.id": "/redfish/v1/Systems/1/Memory"},
                "EmptyList": []
            }
            
            # Apply our token-saving compression immediately after extracting JSON
            compressed_data = compress_redfish_response(raw_data)
            
            # The returned payload will now be significantly smaller!
            return compressed_data
            
        except httpx.HTTPError as e:
            # Handle standard errors...
            raise
"""
