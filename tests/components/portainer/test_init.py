"""Test the Portainer initial specific behavior."""

from importlib.metadata import distribution
from unittest.mock import AsyncMock

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (PortainerAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (PortainerConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (PortainerTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_portainer_client.get_endpoints.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


async def test_migrations(hass: HomeAssistant) -> None:
    """Test migration from v1 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "http://test_host",
            CONF_API_KEY: "test_key",
        },
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    assert entry.version == 1
    assert CONF_VERIFY_SSL not in entry.data
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert CONF_HOST not in entry.data
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_URL] == "http://test_host"
    assert entry.data[CONF_API_TOKEN] == "test_key"
    assert entry.data[CONF_VERIFY_SSL] is True


def test_pyportainer_no_forbidden_dependencies() -> None:
    """Test that pyportainer does not have mkdocs or sphinx as dependencies.

    This test verifies the fix from PR #155783, which bumped pyportainer
    to version 1.0.13 to remove mkdocs and sphinx dependencies that were
    inadvertently included in version 1.0.12.

    This is a regression test to ensure future versions don't reintroduce
    documentation build dependencies as runtime dependencies.

    See: https://github.com/home-assistant/core/pull/155781
    See: https://github.com/home-assistant/core/pull/155783
    """
    # Get pyportainer's metadata using importlib.metadata
    try:
        dist = distribution("pyportainer")
    except Exception as err:  # noqa: BLE001
        pytest.fail(f"Failed to get pyportainer distribution info: {err}")

    # Get direct dependencies from metadata
    # The requires property returns a list like ['aiohttp (>=3.0.0)', 'yarl (>=1.0)']
    requires = dist.requires or []

    # Extract package names without version specifiers or extras
    # Package names are before the first space, parenthesis, bracket, or version operator
    dependencies = set()
    for req in requires:
        # Split on whitespace, operators, and markers - take the first part
        # This handles formats like: 'package', 'package (>=1.0)', 'package[extra]', etc.
        package_name = req.split()[0].split("(")[0].split("[")[0].strip()
        dependencies.add(package_name)

    # Assert that forbidden documentation packages are not in direct dependencies
    # mkdocs and sphinx were added to FORBIDDEN_PACKAGES in PR #155781
    assert "mkdocs" not in dependencies, (
        "pyportainer should not depend on mkdocs (documentation tool)"
    )
    assert "sphinx" not in dependencies, (
        "pyportainer should not depend on sphinx (documentation tool)"
    )
