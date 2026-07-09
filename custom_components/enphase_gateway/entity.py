"""Home assistant base entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityDescription

from .coordinator import GatewayUpdateCoordinator

if TYPE_CHECKING:
    from .enreader.gateway import EnphaseGateway


class GatewayCoordinatorEntity(CoordinatorEntity[GatewayUpdateCoordinator]):
    """Coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            coordinator: GatewayUpdateCoordinator,
            description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.gateway_serial_num = coordinator.gateway_reader.serial_number

    @property
    def data(self) -> EnphaseGateway:
        """Return the gateway data."""
        return self.coordinator.data
