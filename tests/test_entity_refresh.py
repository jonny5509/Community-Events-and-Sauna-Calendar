"""Regression tests for coordinator and scheduled entity state refreshes."""
from unittest.mock import Mock

import pytest

from custom_components.chastity_calendar.calendar import ChastityChallengeCalendar
from custom_components.chastity_calendar.sensor import ChastityCalendarSensorBase


@pytest.mark.parametrize("entity_class", [ChastityChallengeCalendar, ChastityCalendarSensorBase])
def test_coordinator_update_writes_entity_state(entity_class):
    """Coordinator callbacks must explicitly write state when discovery changes."""
    entity = entity_class.__new__(entity_class)
    entity.async_write_ha_state = Mock()

    entity._handle_coordinator_update()

    entity.async_write_ha_state.assert_called_once_with()


@pytest.mark.parametrize("entity_class", [ChastityChallengeCalendar, ChastityCalendarSensorBase])
@pytest.mark.asyncio
async def test_scheduled_refresh_uses_same_state_update_path(entity_class):
    """Time-based refreshes should share the coordinator-update behavior."""
    entity = entity_class.__new__(entity_class)
    entity.async_write_ha_state = Mock()

    await entity._scheduled_state_refresh(None)

    entity.async_write_ha_state.assert_called_once_with()
