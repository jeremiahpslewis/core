"""Test ViCare binary sensors."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "entity_id",
    [
        "burner",
        "circulation_pump",
        "frost_protection",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the ViCare binary sensor."""
    assert hass.states.get(f"binary_sensor.model0_{entity_id}") == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:radiator"}, "vicare/ZigbeeTRV.json"),
        Fixture({"type:repeater"}, "vicare/ZigbeeRepeater.json"),
        # FHT main and channel are the same physical zigbee node, so they share
        # a gateway; this lets the channel link to the main via via_device.
        Fixture({"type:fhtMain"}, "vicare/FHTMain.json", gateway_id="fht_gateway"),
        Fixture(
            {"type:fhtChannel"}, "vicare/FHTChannel.json", gateway_id="fht_gateway"
        ),
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        pytest.param("limited", STATE_ON, id="limited"),
        pytest.param("unlimitedAutonomous", STATE_OFF, id="unlimited"),
    ],
)
async def test_power_limited(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status: str,
    expected_state: str,
) -> None:
    """Test the power limited binary sensor follows the limitation status."""
    fixtures: list[Fixture] = [
        Fixture(
            {"type:heatpump"},
            "vicare/Vitocal250A.json",
            properties={
                "device.power.statusReport.consumption": {
                    "limit": {"type": "number", "unit": "watt", "value": 4200},
                    "status": {"type": "string", "value": status},
                }
            },
        ),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = "binary_sensor.model0_power_consumption_limited"
    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
