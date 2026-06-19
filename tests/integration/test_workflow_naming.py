import pytest
from src.ai_clustering.workflow_naming import generate_system_name

def test_generate_system_name_from_tags():
    endpoints = [
        {"tags": ["UpdateService", "Firmware"], "url": "/redfish/v1/UpdateService", "method": "GET"},
        {"tags": ["UpdateService"], "url": "/redfish/v1/UpdateService/FirmwareInventory", "method": "GET"}
    ]
    name = generate_system_name(endpoints)
    assert name == "firmware_update_operations"

def test_generate_system_name_from_path():
    endpoints = [
        {"url": "/redfish/v1/AccountService/Accounts", "method": "GET"},
        {"url": "/redfish/v1/AccountService/Roles", "method": "GET"}
    ]
    name = generate_system_name(endpoints)
    assert name == "account_management"
    
def test_generate_system_name_operations():
    endpoints = [
        {"url": "/redfish/v1/Systems/1", "method": "GET"},
        {"url": "/redfish/v1/Systems/1", "method": "PATCH"}
    ]
    name = generate_system_name(endpoints)
    assert name == "systems_management"

def test_generate_system_name_fallback():
    endpoints = [
        {"url": "/redfish/v1/Chassis/1", "method": "POST"}
    ]
    name = generate_system_name(endpoints)
    assert name == "chassis_operations"

def test_deterministic_behavior():
    # Same endpoints in different order should yield the same name based on counts
    endpoints1 = [
        {"url": "/redfish/v1/Chassis/1", "method": "GET"},
        {"url": "/redfish/v1/Chassis/1", "method": "POST"}
    ]
    endpoints2 = [
        {"url": "/redfish/v1/Chassis/1", "method": "POST"},
        {"url": "/redfish/v1/Chassis/1", "method": "GET"}
    ]
    assert generate_system_name(endpoints1) == generate_system_name(endpoints2)
