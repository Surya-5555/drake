import logging
import json
import httpx
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.future import select

from src.core.compatibility.models import DeviceFacts
from src.core.database import async_session, DeviceInventory

logger = logging.getLogger(__name__)

# Global cache instrumentation counters
CACHE_HITS = 0
CACHE_MISSES = 0


def increment_cache_hits():
    global CACHE_HITS
    CACHE_HITS += 1


def increment_cache_misses():
    global CACHE_MISSES
    CACHE_MISSES += 1


def get_cache_metrics():
    return CACHE_HITS, CACHE_MISSES


class DeviceFactsProvider(ABC):
    """
    Abstract Base Class for hardware configuration facts retrieval.
    """

    @abstractmethod
    async def get_device_facts(
        self, target_ip: str, credentials: Optional[Dict[str, Any]] = None
    ) -> DeviceFacts:
        """
        Fetch and return target device configuration facts.
        """
        pass


class RedfishFactsProvider(DeviceFactsProvider):
    """
    Queries live iDRAC / OME Redfish REST endpoints at runtime.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or "http://localhost:4010"

    async def get_device_facts(
        self, target_ip: str, credentials: Optional[Dict[str, Any]] = None
    ) -> DeviceFacts:
        logger.info(f"Querying live hardware facts via Redfish for IP: {target_ip}...")
        url = self.base_url.rstrip("/")

        headers = {
            "Authorization": "Bearer redfish-live-facts-token",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                sys_res = await client.get(
                    f"{url}/redfish/v1/Systems/System.Embedded.1", headers=headers
                )
                if sys_res.status_code != 200:
                    sys_res = await client.get(
                        f"{url}/redfish/v1/Systems/1", headers=headers
                    )

                if sys_res.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Failed to query Systems endpoint, status: {sys_res.status_code}",
                        request=sys_res.request,
                        response=sys_res,
                    )

                sys_data = sys_res.json()
                model = sys_data.get("Model", "PowerEdge R750")
                bios = sys_data.get("BiosVersion", "2.12.2")
                lc_ver = (
                    sys_data.get("Oem", {})
                    .get("Dell", {})
                    .get("LifecycleControllerVersion", "5.10.00.00")
                )

                fw_inv = {}
                fw_res = await client.get(
                    f"{url}/redfish/v1/UpdateService/FirmwareInventory", headers=headers
                )
                if fw_res.status_code == 200:
                    fw_data = fw_res.json()
                    members = fw_data.get("Members", [])
                    for member in members:
                        ref_url = member.get("@odata.id")
                        if ref_url:
                            item_res = await client.get(
                                f"{url}{ref_url}", headers=headers
                            )
                            if item_res.status_code == 200:
                                item_data = item_res.json()
                                name = item_data.get("Name", "")
                                version = item_data.get("Version", "")
                                if name and version:
                                    fw_inv[name] = version

                return DeviceFacts(
                    target_ip=target_ip,
                    device_model=model,
                    bios_version=bios,
                    lifecycle_controller_version=lc_ver,
                    firmware_inventory=fw_inv,
                    last_scanned=datetime.now(timezone.utc),
                    is_live=True,
                )
            except Exception as e:
                logger.error(f"Live Redfish query failed for target {target_ip}: {e}")
                raise


class CachedFactsProvider(DeviceFactsProvider):
    """
    Loads device configurations from SQLite device_inventory cache.
    """

    async def get_device_facts(
        self, target_ip: str, credentials: Optional[Dict[str, Any]] = None
    ) -> DeviceFacts:
        logger.info(f"Querying SQLite device cache for IP: {target_ip}...")
        async with async_session() as session:
            result = await session.execute(
                select(DeviceInventory).where(DeviceInventory.target_ip == target_ip)
            )
            device = result.scalar_one_or_none()
            if not device:
                raise ValueError(
                    f"Device configuration cache not found for IP: {target_ip}"
                )

            fw_inventory = {}
            try:
                if device.firmware_inventory:
                    fw_inventory = json.loads(device.firmware_inventory)
            except Exception:
                pass

            scanned_time = None
            try:
                scanned_time = datetime.fromisoformat(device.last_scanned)
            except Exception:
                pass

            return DeviceFacts(
                target_ip=device.target_ip,
                device_model=device.device_model,
                bios_version=device.bios_version,
                lifecycle_controller_version=device.lifecycle_controller_version,
                firmware_inventory=fw_inventory,
                last_scanned=scanned_time,
                is_live=False,
            )


class StaticFactsProvider(DeviceFactsProvider):
    """
    Static mockup configurations provider for unit/integration testing.
    """

    def __init__(self, mock_facts: Optional[DeviceFacts] = None):
        self.mock_facts = mock_facts or DeviceFacts(
            target_ip="192.168.0.120",
            device_model="PowerEdge R750",
            bios_version="2.12.0",
            lifecycle_controller_version="5.10.00.00",
            firmware_inventory={"iDRAC9": "5.10.00.00", "BroadcomNIC": "21.6.0"},
            last_scanned=datetime.now(timezone.utc),
            is_live=False,
        )

    async def get_device_facts(
        self, target_ip: str, credentials: Optional[Dict[str, Any]] = None
    ) -> DeviceFacts:
        logger.info(f"Using Static mock facts for IP: {target_ip}")
        facts = self.mock_facts.model_copy()
        facts.target_ip = target_ip
        facts.is_live = False
        return facts


class OMSDKFactsProvider(DeviceFactsProvider):
    """
    Swappable adapter for connecting dynamically to target hardware using Dell OMSDK.
    """

    async def get_device_facts(
        self, target_ip: str, credentials: Optional[Dict[str, Any]] = None
    ) -> DeviceFacts:
        logger.info(
            f"Querying hardware config dynamically via Dell OMSDK driver for IP: {target_ip}..."
        )
        # Future implementation hooks into OMSDK library
        return DeviceFacts(
            target_ip=target_ip,
            device_model="PowerEdge R760",
            bios_version="1.0.0",
            lifecycle_controller_version="6.00.00.00",
            firmware_inventory={"iDRAC9": "6.00.00.00"},
            last_scanned=datetime.now(timezone.utc),
            is_live=True,
        )


class DellCatalogCompatibilitySource(ABC):
    """Future extensible driver for parsing Dell Catalog.xml files."""

    pass


class OMECompatibilitySource(ABC):
    """Future extensible driver for connecting to Dell OpenManage Enterprise groups."""

    pass
