"""Test the Portainer initial specific behavior."""

import subprocess
import sys
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

    See: https://github.com/home-assistant/core/pull/155781
    See: https://github.com/home-assistant/core/pull/155783
    """
    # Get pyportainer's direct dependencies using pip show
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "pyportainer"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Extract the Requires line from pip show output
    requires_line = None
    for line in result.stdout.split("\n"):
        if line.startswith("Requires:"):
            requires_line = line
            break

    assert requires_line is not None, "Could not find Requires line in pip show output"

    # Parse direct dependencies
    # Format is "Requires: dep1, dep2, dep3" or "Requires: " if no dependencies
    requires_text = requires_line.split(":", 1)[1].strip()

    if requires_text:
        dependencies = {dep.strip() for dep in requires_text.split(",")}
    else:
        dependencies = set()

    # Assert that forbidden documentation packages are not in direct dependencies
    # This is a regression test to ensure future versions don't reintroduce these
    assert "mkdocs" not in dependencies, (
        "pyportainer should not depend on mkdocs (documentation tool)"
    )
    assert "sphinx" not in dependencies, (
        "pyportainer should not depend on sphinx (documentation tool)"
    )
