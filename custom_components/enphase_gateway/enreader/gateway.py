"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import logging
import functools
from typing import Callable

import xmltodict
from httpx import Response

from .const import AVAILABLE_PROPERTIES
from .endpoint import GatewayEndpoint, EndpointCollection
from .descriptors import (
    PropertyDescriptor,
    # ResponseDescriptor,
    JsonDescriptor,
    RegexDescriptor,
)

from .models import (
    ACBatteryStorage,
    EnsemblePowerDevices,
    EnsembleInventory,
)


_LOGGER = logging.getLogger(__name__)


def gateway_property(
        _func: Callable | None = None,
        **kwargs: dict,
) -> PropertyDescriptor:
    """Decorate the given method as gateway property.

    Works identical to the python property decorator.
    Additionally registers the method to the '_gateway_properties' dict
    of the methods parent class.

    Parameters
    ----------
    _func : Callable, optional
        Method to decorate. The default is None.
    **kwargs : dict
        Optional keyword arguments.

    Returns
    -------
    PropertyDescriptor
        Property descriptor calling the method on attribute access.

    """
    required_endpoint = kwargs.pop("required_endpoint", None)
    cache = kwargs.pop("cache", 0)

    def decorator(func):
        return PropertyDescriptor(
            fget=func,
            doc=None,
            required_endpoint=required_endpoint,
            cache=cache,
        )

    return decorator if _func is None else decorator(_func)


def gateway_probe(
        _func: Callable | None = None,
        *,
        endpoint: str | None = None,
) -> Callable:
    """Decorate the function as a gateway probe.

    The decorator injects the following attributes to the function:
        - `._is_gateway_probe`
        - `._required_endpoint`

    These attributes can be used to identify a gateway probe
    and it's required endpoint during object creation.

    Parameters
    ----------
    _func : Callable, optional
        Function to decorate. This function is only passed in directly
        if the decorator is called without arguments.
    endpoint : str, optional
        The endpoint required for this probe. The dafault is None.

    Returns
    -------
    property
        Property of the decorated method.

    """
    # required_endpoint = kwargs.pop("required_endpoint", None)
    # cache = kwargs.pop("cache", 0)

    def decorator(func):

        if endpoint:
            required_endpoint = GatewayEndpoint(endpoint)
        else:
            required_endpoint = None
        #func.gateway_probe = endpoint

        func._is_gateway_probe = True
        func._required_endpoint = required_endpoint

        return func

    if _func is None:
        return decorator
    else:
        decorator(_func)


class EnphaseGateway:
    """A class to represent an (R)Enphase Gateway.

    Provides properties to access data fetched from the required endpoint.

    Attributes
    ----------
    data : dict
        Response data from the endpoints.
    initial_update_finished : bool
        Return True if the initial update has finished. Return False otherwise.

    """

    VERBOSE_NAME = "Generic Enphase Gateway"

    def __new__(cls, *args, **kwargs) -> EnphaseGateway:
        """Create a new instance.

        The class uses descriptors and the `gateway_property` decorator
        to define the data that is available on the (R)Enphase Gateway.

        Descriptors can be used to define easily accessible data.
        Be aware that descriptors have no access to the instance of the class.
        The following descriptors are currently available:
            - RegexDesriptor
            - JsonDescriptor

        The `gateway_property` decorator works similar to the python
        `property` decorator but allows additional keyword arguments.


        Catch methods having the 'gateway_property' attribute and add them
        to the classes '_gateway_properties' attribute.
        Set the method as a property of the class.

        """
        instance = super().__new__(cls)

        gateway_properties = {}
        gateway_probes = {}

        for obj in [instance.__class__] + instance.__class__.mro():
            #
            # Iterate over the method resolution order to get
            # all `gateway_properties` and `gateway_probes`.
            # This allows us to use inheritance.
            #
            owner_uid = f"{obj.__name__.lower()}"
            for attr_name, attr_val in obj.__dict__.items():
                #
                # Iterate over all attributes of the objet.
                #
                if attr_name == f"{owner_uid}_gateway_properties":
                    #
                    # If the object has a `_gateway_properties`
                    # attribute it's a gateway class.
                    # The `_gateway_properties` attribute contains
                    # all the endpoints of the object.
                    #
                    for key, val in attr_val.items():
                        #
                        # Add all gateway properties that have been added
                        # to the object's `_gateway_properties` dictionary
                        # to the gateway_properties dictionary.
                        #
                        gateway_properties.setdefault(key, val)

                if getattr(attr_val, "_is_gateway_probe", False):
                    #
                    # Add the gateway probes endpoint to the
                    # gateway_probes dictionary if the attribute
                    # hat a `gateway_probe` attribute itself.
                    #
                    endpoint = getattr(attr_val, "_required_endpoint")
                    gateway_probes.setdefault(attr_name, endpoint)

        instance._gateway_properties = gateway_properties
        instance._gateway_probes = gateway_probes

        return instance

    def __init__(self, gateway_info=None) -> None:
        """Initialize instance of BaseGateway."""
        self.data = {}
        self.initial_update_finished = False
        self._required_endpoints = None

    @property
    def properties(self) -> list[str]:
        """Return the properties of the gateway."""
        return self._gateway_properties.keys()

    @property
    def all_values(self) -> dict:
        """Return a dict containing all attributes and their value."""
        result = {}
        for attr in self.properties:
            result[attr] = getattr(self, attr)

        return result

    @property
    def _required_endpoints(self) -> list[GatewayEndpoint]:
        """Return all required endpoints for this gateway.

        Returns
        -------
        endpoints : list[GatewayEndpoint]
            List containing all required endpoints.

        """
        if self._required_endpoints is not None:
            return self._required_endpoints

        endpoints = {}

        for property_name, endpoint in self._gateway_properties.items():
            if isinstance(endpoint, GatewayEndpoint):
                if self.initial_update_finished:
                    #
                    # When the gateway property that requires this endpoint
                    # does not return any valid data after the inital update,
                    # then the endpoint is useless and we drop the endpoint.
                    #
                    value = getattr(self, property_name)
                    if value in (None, "", [], {}):
                        continue

                if existing := endpoints[endpoint.path]:
                    # Set the caching interval to the lowest value.
                    if endpoint.cache_for < existing.cache_for:
                        existing.cache_for = endpoint.cache_for
                else:
                    endpoints[endpoint.path] = endpoint

        if self.initial_update_finished:
            # Save list in memory, as we should not evaluate this list again.
            # If the list needs re-evaluation, then reload the plugin.
            self._required_endpoints = list(endpoints.values())

        return list(endpoints.values())

    @property
    def _required_probing_endpoints(self) -> list[GatewayEndpoint]:
        """Return all required probing endpoints for this gateway.

        Returns
        -------
        endpoints : list[GatewayEndpoint]
            List containing all required endpoints.

        """
        endpoints = {}
        for probe_name, endpoint in self._gateway_probes.items():
            if isinstance(endpoint, GatewayEndpoint):
                if endpoint.path not in endpoints:
                    endpoints[endpoint.path] = endpoint

        return list(endpoints.values())

    def update(self, _request) -> None:
        """Update the gateway's data."""
        force = True if not self.initial_update_finished else False

        for endpoint in self._required_endpoints:
            endpoint.update(_request, force=force)

        if not self.gateway.initial_update_finished:
            self.gateway.initial_update_finished = True

    def probe(self, _request) -> None:
        """Probe the gateway."""
        data = {}
        for endpoint in self._required_probing_endpoints:
            data[endpoint.path] = endpoint.fetch(_request)

        for probe_name, endpoint in self._gateway_probes.items():
            probe_func = getattr(self, probe_name)
            probe_data = data.get(endpoint.path, None)

            probe_func(probe_data)

        self._clean_probes()

        return self._get_subclass()

    def _clean_probes(self):
        """Clean the data from the probes."""
        pass

    def _get_subclass(self):
        """Return the matching subclass."""
        return None

    def __getattribute__(self, name):
        """Return None if gateway does not support this property."""
        try:
            value = object.__getattribute__(self, name)
        except AttributeError as err:
            if name in AVAILABLE_PROPERTIES:
                return None
            else:
                raise err
        else:
            return value

    def get(self, attr: str, default=None):
        """Get the given attribute.

        Parameters
        ----------
        attr : str
            Attribute to get.
        default : TYPE, optional
            Default return value. The default is None.

        Returns
        -------
        TYPE
            Value of the attribute.

        """
        data = getattr(self, attr)
        if data is None:
            return default
        elif isinstance(data, str) and data == "not_supported":
            return default
        return data









class EnvoyLegacy(EnphaseGateway):
    """Enphase(R) Envoy-R Gateway using FW < R3.9."""

    VERBOSE_NAME = "Envoy-R"

    production = RegexDescriptor(
        r"<td>Currentl.*</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(W|kW|MW)</td>",
        "production",
    )

    daily_production = RegexDescriptor(
        r"<td>Today</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>",
        "production",
    )

    seven_days_production = RegexDescriptor(
        r"<td>Past Week</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>",
        "production",
    )

    lifetime_production = RegexDescriptor(
        r"<td>Since Installation</td>\s+<td>\s*(\d+|\d+\.\d+)\s*(Wh|kWh|MWh)</td>", # noqa
        "production",
    )


class Envoy(EnphaseGateway):
    """Enphase(R) Envoy-R Gateway using FW >= R3.9."""

    VERBOSE_NAME = "Envoy-R"

    production = JsonDescriptor("wattsNow", "api/v1/production")

    daily_production = JsonDescriptor("wattHoursToday", "api/v1/production")

    seven_days_production = JsonDescriptor(
        "wattHoursSevenDays", "api/v1/production"
    )

    lifetime_production = JsonDescriptor(
        "wattHoursLifetime", "api/v1/production"
    )

    @gateway_property(required_endpoint="api/v1/production/inverters")
    def inverters(self):
        """Single inverter production data."""
        inverters = self.data.get("api/v1/production/inverters")
        if inverters:
            return {inv["serialNumber"]: inv for inv in inverters}

        return None


class EnvoyS(Envoy):
    """Enphase(R) Envoy-S Standard Gateway."""

    VERBOSE_NAME = "Envoy-S Standard"

    ensemble_secctrl = JsonDescriptor("", "ivp/ensemble/secctrl")

    @gateway_property(required_endpoint="ivp/ensemble/inventory")
    def ensemble_inventory(self) -> EnsembleInventory | None:
        """Ensemble Encharge storages."""
        result = JsonDescriptor.resolve(
            "$[?(@.type=='ENCHARGE')].devices",
            self.data.get("ivp/ensemble/inventory", {}),
        )
        if result and isinstance(result, list):
            return {
                device["serial_num"]: EnsembleInventory.from_result(device)
                for device in result
            }

        return None

    @gateway_property(required_endpoint="ivp/ensemble/power")
    def ensemble_power(self) -> EnsemblePowerDevices | None:
        """Ensemble power data."""
        result = JsonDescriptor.resolve(
            "'devices:'", self.data.get("ivp/ensemble/power", {})
        )
        if result and isinstance(result, list):
            return EnsemblePowerDevices.from_result(result)

        return None

    @gateway_property(required_endpoint="production.json")
    def ac_battery(self) -> ACBatteryStorage | None:
        """Return AC battery storage data."""
        # AC-Battery is installed when the 'percentFull' key exists.
        data = JsonDescriptor.resolve(
            "storage[?(@.percentFull)]",
            self.data.get("production.json", {})
        )
        if data is not None:
            return ACBatteryStorage.from_result(data)

        return None


class EnvoySMetered(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway.

    This is the default gateway for metered Envoy-s gateways.
    It provides probes to detect abnormal configurations.

    """

    VERBOSE_NAME = "Envoy-S Metered"

    _CONS = "consumption[?(@.measurementType == '{}' & @.activeCount > 0)]"

    _PRODUCTION_JSON = "production[?(@.type=='eim' & @.activeCount > 0)].{}"

    _TOTAL_CONSUMPTION_JSON = _CONS.format("total-consumption")

    _NET_CONSUMPTION_JSON = _CONS.format("net-consumption")

    def __init__(self, *args, **kwargs):
        """Initialize instance of EnvoySMetered."""
        super().__init__(*args, **kwargs)
        self.production_meter = None
        self.net_consumption_meter = None
        self.total_consumption_meter = None

    def _get_subclass(self):
        """Return the subclass for abnormal gateway installations."""
        if self._probes_finished:
            consumption_meter = (
                self.net_consumption_meter or self.total_consumption_meter
            )
            if not self.production_meter or not consumption_meter:
                return EnvoySMeteredCtDisabled(
                    self.production_meter,
                    self.net_consumption_meter,
                    self.total_consumption_meter,
                )

        return None

    @gateway_probe(required_endpoint="ivp/meters")
    def ivp_meters_probe(self, data):
        """Probe the meter configuration."""
        base_expr = "$[?(@.state=='enabled' & @.measurementType=='{}')].eid"
        self.production_meter = JsonDescriptor.resolve(
            base_expr.format("production"),
            self.data.get("ivp/meters", {}),
        )
        self.net_consumption_meter = JsonDescriptor.resolve(
            base_expr.format("net-consumption"),
            self.data.get("ivp/meters", {}),
        )
        self.total_consumption_meter = JsonDescriptor.resolve(
            base_expr.format("total-consumption"),
            self.data.get("ivp/meters", {}),
        )
        _LOGGER.debug("Probe: 'ivp_meters_probe' finished")

    @gateway_property(required_endpoint="ivp/meters/readings")
    def grid_power(self):
        """Return grid power."""
        if eid := self.net_consumption_meter:
            return JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )

        return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def grid_import(self):
        """Return grid import."""
        if eid := self.net_consumption_meter:
            power = JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )
            if isinstance(power, (int, float)):
                return power if power > 0 else 0

        return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_grid_net_import(self):
        """Return lifetime grid import."""
        if eid := self.net_consumption_meter:
            return JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].actEnergyDlvd",
                self.data.get("ivp/meters/readings", {})
            )

        return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def grid_export(self):
        """Return grid export."""
        if eid := self.net_consumption_meter:
            power = JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )
            if isinstance(power, (int, float)):
                return (power * -1) if power < 0 else 0

        return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_grid_net_export(self):
        """Return lifetime grid export."""
        if eid := self.net_consumption_meter:
            return JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].actEnergyRcvd",
                self.data.get("ivp/meters/readings", {})
            )

        return None

    @gateway_property(required_endpoint="ivp/meters/readings")
    def production(self):
        """Return the measured active power."""
        return JsonDescriptor.resolve(
            f"$[?(@.eid=={self.production_meter})].activePower",
            self.data.get("ivp/meters/readings", {})
        )

    @gateway_property(required_endpoint="production.json", cache=0)
    def daily_production(self):
        """Return the daily energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION_JSON.format("whToday"),
            self.data.get("production.json", {})
        )

    @gateway_property(required_endpoint="production.json", cache=0)
    def seven_days_production(self):
        """Return the daily energy production."""
        # HINT: Currently disabled due to inaccurate values.
        return None
        return JsonDescriptor.resolve(
            self._PRODUCTION_JSON.format("whLastSevenDays"),
            self.data.get("production.json", {}),
        )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_production(self):
        """Return the lifetime energy production."""
        return JsonDescriptor.resolve(
            f"$[?(@.eid=={self.production_meter})].actEnergyDlvd",
            self.data.get("ivp/meters/readings", {})
        )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def consumption(self):
        """Return the measured active power."""
        if eid := self.net_consumption_meter:
            prod = self.production
            cons = JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )
            if prod and cons:
                return prod + cons
        elif eid := self.total_consumption_meter:
            return JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].activePower",
                self.data.get("ivp/meters/readings", {})
            )

        return None

    @gateway_property(required_endpoint="production.json", cache=0)
    def daily_consumption(self):
        """Return the daily energy production."""
        return JsonDescriptor.resolve(
            self._TOTAL_CONSUMPTION_JSON + ".whToday",
            self.data.get("production.json", {})
        )

    @gateway_property(required_endpoint="production.json", cache=0)
    def seven_days_consumption(self):
        """Return the daily energy production."""
        # HINT: Currently disabled due to inaccurate values.
        return None
        return JsonDescriptor.resolve(
            self._TOTAL_CONSUMPTION_JSON + ".whLastSevenDays",
            self.data.get("production.json", {}),
        )

    @gateway_property(required_endpoint="ivp/meters/readings")
    def lifetime_consumption(self):
        """Return the lifetime energy production."""
        if eid := self.net_consumption_meter:
            prod = self.lifetime_production
            cons = JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})]",
                self.data.get("ivp/meters/readings", {})
            )
            if prod and cons:
                return prod - (cons["actEnergyRcvd"] - cons["actEnergyDlvd"])
        elif eid := self.total_consumption_meter:
            # TODO: collect fixtures and validate
            return JsonDescriptor.resolve(
                f"$[?(@.eid=={eid})].actEnergyRcvd",
                self.data.get("ivp/meters/readings", {})
            )

        return None


class EnvoySMeteredCtDisabled(EnvoyS):
    """Enphase(R) Envoy Model S Metered Gateway with disabled CTs."""

    VERBOSE_NAME = "Envoy-S Metered without CTs"

    _CONS = "consumption[?(@.measurementType == '{}' & @.activeCount > 0)]"

    _PRODUCTION = "production[?(@.type=='{}' & @.activeCount > 0)]"

    _PRODUCTION_INV = "production[?(@.type=='inverters')]"

    _TOTAL_CONSUMPTION = _CONS.format("total-consumption")

    _NET_CONSUMPTION = _CONS.format("net-consumption")

    consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".wNow",
        "production.json",
    )

    daily_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whToday",
        "production.json",
    )

    # HINT: Currently disabled due to inaccurate values.
    seven_days_consumption = None
    # seven_days_consumption = JsonDescriptor(
    #     _TOTAL_CONSUMPTION + ".whLastSevenDays",
    #     "production.json",
    # )

    lifetime_consumption = JsonDescriptor(
        _TOTAL_CONSUMPTION + ".whLifetime",
        "production.json",
    )

    def __init__(
            self,
            production_meter: str | None,
            net_consumption_meter: str | None,
            total_consumption_meter: str | None,
            *args,
            **kwargs
    ):
        """Initialize instance of EnvoySMeteredAbnormal."""
        super().__init__(*args, **kwargs)
        self.production_meter = production_meter
        self.net_consumption_meter = net_consumption_meter
        self.total_consumption_meter = total_consumption_meter
        self.prod_type = "eim" if production_meter else "inverters"

    @gateway_property(required_endpoint="production.json")
    def production(self):
        """Energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".wNow",
            self.data.get("production.json", {})
        )

    @gateway_property(required_endpoint="production.json")
    def daily_production(self):
        """Todays energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".whToday",
            self.data.get("production.json", {})
        )

    # HINT: Currently disabled due to inaccurate values.
    @gateway_property(required_endpoint="production.json")
    def seven_days_production(self):
        """Last seven days energy production."""
        return None
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".whLastSevenDays",
            self.data.get("production.json", {})
        )

    @gateway_property(required_endpoint="production.json")
    def lifetime_production(self):
        """Lifetime energy production."""
        return JsonDescriptor.resolve(
            self._PRODUCTION.format(self.prod_type) + ".whLifetime",
            self.data.get("production.json", {})
        )
