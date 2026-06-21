from src.ai_clustering.graph_clustering import build_relationship_graph, detect_communities

def make_endpoint(method: str, url: str, operation_id: str, tags: list[str]) -> dict:
    return {
        "operation_id": operation_id,
        "method": method,
        "url": url,
        "tags": tags,
        "required_params": [],
        "summary": f"{method} {url}",
        "description": "",
    }

def test_golden_clustering_quality():
    # Phase 8: Golden Test Suite
    # UpdateService, Systems, Accounts
    
    endpoints = [
        # UpdateService cluster
        make_endpoint("GET", "/redfish/v1/UpdateService", "GET_UpdateService", ["UpdateService"]),
        make_endpoint("GET", "/redfish/v1/UpdateService/FirmwareInventory", "GET_FirmwareInventory", ["UpdateService", "FirmwareInventory"]),
        make_endpoint("GET", "/redfish/v1/UpdateService/SoftwareInventory", "GET_SoftwareInventory", ["UpdateService", "SoftwareInventory"]),
        make_endpoint("POST", "/redfish/v1/UpdateService/Actions/Oem/DellUpdateService.Install", "POST_Install", ["UpdateService"]),
        make_endpoint("POST", "/redfish/v1/UpdateService/SoftwareInventory/{SoftwareInventoryId}/Actions/Oem/DellPluginInventory.Restart", "POST_Restart", ["SoftwareInventory"]),
        
        # Systems cluster
        make_endpoint("GET", "/redfish/v1/Systems", "GET_Systems", ["ComputerSystemCollection"]),
        make_endpoint("GET", "/redfish/v1/Systems/{ComputerSystemId}", "GET_System", ["ComputerSystem"]),
        make_endpoint("POST", "/redfish/v1/Systems/{ComputerSystemId}/Actions/ComputerSystem.Reset", "POST_Reset", ["ComputerSystem"]),
        make_endpoint("GET", "/redfish/v1/Systems/{ComputerSystemId}/Oem/Dell/DellPowerControl", "GET_PowerControl", ["ComputerSystem"]),
        
        # Accounts cluster
        make_endpoint("GET", "/redfish/v1/AccountService", "GET_AccountService", ["AccountService"]),
        make_endpoint("GET", "/redfish/v1/AccountService/Accounts", "GET_Accounts", ["ManagerAccountCollection"]),
        make_endpoint("GET", "/redfish/v1/AccountService/Roles", "GET_Roles", ["RoleCollection"]),
    ]
    
    G = build_relationship_graph(endpoints)
    communities = detect_communities(G)
    
    # We expect roughly 3 main communities: UpdateService, Systems, Accounts
    # Let's map endpoints to communities
    ep_to_comm = {}
    for i, comm in enumerate(communities):
        for ep_id in comm:
            ep_to_comm[ep_id] = i
            
    # Check UpdateService cohesion
    assert ep_to_comm["GET_UpdateService"] == ep_to_comm["GET_FirmwareInventory"]
    assert ep_to_comm["GET_UpdateService"] == ep_to_comm["GET_SoftwareInventory"]
    assert ep_to_comm["GET_UpdateService"] == ep_to_comm["POST_Install"]
    assert ep_to_comm["GET_UpdateService"] == ep_to_comm["POST_Restart"]
    
    # Check Systems cohesion
    assert ep_to_comm["GET_Systems"] == ep_to_comm["GET_System"]
    assert ep_to_comm["GET_System"] == ep_to_comm["POST_Reset"]
    assert ep_to_comm["GET_System"] == ep_to_comm["GET_PowerControl"]
    
    # Check Accounts cohesion
    assert ep_to_comm["GET_AccountService"] == ep_to_comm["GET_Accounts"]
    assert ep_to_comm["GET_AccountService"] == ep_to_comm["GET_Roles"]

    # Check separation
    assert ep_to_comm["GET_UpdateService"] != ep_to_comm["GET_Systems"]
    assert ep_to_comm["GET_Systems"] != ep_to_comm["GET_AccountService"]
    assert ep_to_comm["GET_UpdateService"] != ep_to_comm["GET_AccountService"]

if __name__ == "__main__":
    test_golden_clustering_quality()
    print("Golden tests passed!")
