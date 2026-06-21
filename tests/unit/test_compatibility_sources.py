import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.core.compatibility.models import DeviceFacts
from src.core.compatibility.sources import (
    StaticFactsProvider,
    CachedFactsProvider,
    RedfishFactsProvider,
    OMSDKFactsProvider,
    increment_cache_hits,
    increment_cache_misses,
    get_cache_metrics,
)


def test_cache_metrics():
    # Verify instrumentation helper functions
    h1, m1 = get_cache_metrics()
    increment_cache_hits()
    increment_cache_misses()
    h2, m2 = get_cache_metrics()
    assert h2 == h1 + 1
    assert m2 == m1 + 1


@pytest.mark.asyncio
async def test_static_facts_provider():
    provider = StaticFactsProvider()
    facts = await provider.get_device_facts("192.168.0.125")
    assert facts.target_ip == "192.168.0.125"
    assert facts.is_live is False
    assert facts.device_model == "PowerEdge R750"

    custom_facts = DeviceFacts(
        target_ip="1.1.1.1",
        device_model="PowerEdge R650",
        bios_version="1.0.0",
        is_live=True,
    )
    provider_custom = StaticFactsProvider(custom_facts)
    facts_custom = await provider_custom.get_device_facts("192.168.0.126")
    assert facts_custom.target_ip == "192.168.0.126"
    assert facts_custom.device_model == "PowerEdge R650"
    assert facts_custom.is_live is False  # statically overridden to False


@pytest.mark.asyncio
async def test_omsdk_facts_provider():
    provider = OMSDKFactsProvider()
    facts = await provider.get_device_facts("192.168.0.127")
    assert facts.target_ip == "192.168.0.127"
    assert facts.device_model == "PowerEdge R760"
    assert facts.is_live is True


@pytest.mark.asyncio
async def test_cached_facts_provider_success(monkeypatch):
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr(
        "src.core.compatibility.sources.async_session", mock_session_factory
    )

    mock_device = MagicMock()
    mock_device.target_ip = "192.168.0.120"
    mock_device.device_model = "PowerEdge R750"
    mock_device.bios_version = "2.12.0"
    mock_device.lifecycle_controller_version = "5.10.00.00"
    mock_device.firmware_inventory = '{"iDRAC9": "5.10.00.00"}'
    mock_device.last_scanned = "2026-06-20T23:23:55"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_device
    mock_session.execute.return_value = mock_result

    provider = CachedFactsProvider()
    facts = await provider.get_device_facts("192.168.0.120")
    assert facts.target_ip == "192.168.0.120"
    assert facts.device_model == "PowerEdge R750"
    assert facts.firmware_inventory == {"iDRAC9": "5.10.00.00"}
    assert facts.is_live is False
    assert facts.last_scanned.year == 2026


@pytest.mark.asyncio
async def test_cached_facts_provider_miss(monkeypatch):
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr(
        "src.core.compatibility.sources.async_session", mock_session_factory
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    provider = CachedFactsProvider()
    with pytest.raises(ValueError, match="Device configuration cache not found"):
        await provider.get_device_facts("192.168.0.120")


@pytest.mark.asyncio
async def test_cached_facts_provider_malformed_json_and_date(monkeypatch):
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr(
        "src.core.compatibility.sources.async_session", mock_session_factory
    )

    mock_device = MagicMock()
    mock_device.target_ip = "192.168.0.120"
    mock_device.device_model = "PowerEdge R750"
    mock_device.bios_version = "2.12.0"
    mock_device.lifecycle_controller_version = "5.10.00.00"
    mock_device.firmware_inventory = "{invalid-json}"
    mock_device.last_scanned = "invalid-date"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_device
    mock_session.execute.return_value = mock_result

    provider = CachedFactsProvider()
    facts = await provider.get_device_facts("192.168.0.120")
    assert facts.firmware_inventory == {}
    assert facts.last_scanned is None


@pytest.mark.asyncio
async def test_redfish_facts_provider_success(monkeypatch):
    # Mock responses
    mock_sys_res = MagicMock()
    mock_sys_res.status_code = 200
    mock_sys_res.json.return_value = {
        "Model": "PowerEdge R750",
        "BiosVersion": "2.12.2",
        "Oem": {"Dell": {"LifecycleControllerVersion": "5.10.00.00"}},
    }

    mock_fw_res = MagicMock()
    mock_fw_res.status_code = 200
    mock_fw_res.json.return_value = {
        "Members": [{"@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/iDRAC"}]
    }

    mock_item_res = MagicMock()
    mock_item_res.status_code = 200
    mock_item_res.json.return_value = {"Name": "iDRAC9", "Version": "5.10.00.00"}

    # Mock Client methods
    mock_client = AsyncMock()

    async def mock_get(url, **kwargs):
        if "/redfish/v1/Systems/System.Embedded.1" in url:
            return mock_sys_res
        elif "/redfish/v1/UpdateService/FirmwareInventory/iDRAC" in url:
            return mock_item_res
        elif "/redfish/v1/UpdateService/FirmwareInventory" in url:
            return mock_fw_res
        else:
            raise ValueError(f"Unexpected url request: {url}")

    mock_client.get.side_effect = mock_get

    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    monkeypatch.setattr(
        httpx, "AsyncClient", MagicMock(return_value=mock_client_instance)
    )

    provider = RedfishFactsProvider()
    facts = await provider.get_device_facts("192.168.0.120")
    assert facts.target_ip == "192.168.0.120"
    assert facts.device_model == "PowerEdge R750"
    assert facts.bios_version == "2.12.2"
    assert facts.lifecycle_controller_version == "5.10.00.00"
    assert facts.firmware_inventory == {"iDRAC9": "5.10.00.00"}
    assert facts.is_live is True


@pytest.mark.asyncio
async def test_redfish_facts_provider_fallback_and_failure(monkeypatch):
    # Mock responses: Embedded.1 returns 404, fallback to /v1/Systems/1 returns 200
    mock_sys_res_1 = MagicMock()
    mock_sys_res_1.status_code = 404

    mock_sys_res_2 = MagicMock()
    mock_sys_res_2.status_code = 200
    mock_sys_res_2.json.return_value = {
        "Model": "PowerEdge R650",
        "BiosVersion": "1.4.0",
    }

    mock_fw_res = MagicMock()
    mock_fw_res.status_code = 404  # Firmware inventory missing

    mock_client = AsyncMock()

    async def mock_get(url, **kwargs):
        if "/redfish/v1/Systems/System.Embedded.1" in url:
            return mock_sys_res_1
        elif "/redfish/v1/Systems/1" in url:
            return mock_sys_res_2
        elif "/redfish/v1/UpdateService/FirmwareInventory" in url:
            return mock_fw_res
        else:
            raise ValueError(f"Unexpected url request: {url}")

    mock_client.get.side_effect = mock_get

    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    monkeypatch.setattr(
        httpx, "AsyncClient", MagicMock(return_value=mock_client_instance)
    )

    provider = RedfishFactsProvider()
    facts = await provider.get_device_facts("192.168.0.120")
    assert facts.device_model == "PowerEdge R650"
    assert facts.bios_version == "1.4.0"
    assert facts.firmware_inventory == {}


@pytest.mark.asyncio
async def test_redfish_facts_provider_http_error(monkeypatch):
    mock_sys_res_1 = MagicMock()
    mock_sys_res_1.status_code = 500
    mock_sys_res_1.request = httpx.Request(
        "GET", "/redfish/v1/Systems/System.Embedded.1"
    )

    mock_sys_res_2 = MagicMock()
    mock_sys_res_2.status_code = 500
    mock_sys_res_2.request = httpx.Request("GET", "/redfish/v1/Systems/1")

    mock_client = AsyncMock()

    async def mock_get(url, **kwargs):
        if "/redfish/v1/Systems/System.Embedded.1" in url:
            return mock_sys_res_1
        elif "/redfish/v1/Systems/1" in url:
            return mock_sys_res_2
        raise ValueError(f"Unexpected url request: {url}")

    mock_client.get.side_effect = mock_get

    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    monkeypatch.setattr(
        httpx, "AsyncClient", MagicMock(return_value=mock_client_instance)
    )

    provider = RedfishFactsProvider()
    with pytest.raises(httpx.HTTPStatusError):
        await provider.get_device_facts("192.168.0.120")
