"""Enphase(R) Gateway data descriptor module."""

import re
import logging
from textwrap import dedent
from types import GenericAlias

from jsonpath_ng.ext import parse, filter # noqa

from .endpoint import GatewayEndpoint


_LOGGER = logging.getLogger(__name__)


_NOT_FOUND = object()


class BaseDescriptor:
    """Base descriptor."""

    def __init__(self, required_endpoint: str, cache: int = 0) -> None:
        """Initialize BaseDescriptor."""
        self._required_endpoint = required_endpoint
        self._cache = cache

    def __set_name__(self, owner, name) -> None:
        """Set name and owner of the descriptor."""
        self._name = name
        if owner and name and self._required_endpoint:
            _endpoint = GatewayEndpoint(self._required_endpoint, self._cache)
            uid = f"{owner.__name__.lower()}_gateway_properties"
            if properties := getattr(owner, uid, None):
                properties[name] = _endpoint
            else:
                setattr(owner, uid, {name: _endpoint})


class PropertyDescriptor(BaseDescriptor):
    """Property descriptor.

    A pure python implementation of property that registers the
    required endpoint and the caching interval.
    """

    def __init__(
            self,
            fget=None,
            doc=None,
            required_endpoint: str | None = None,
            cache: int = 0,
    ) -> None:
        """Initialize instance of PropertyDescriptor."""
        super().__init__(required_endpoint, cache)
        self.fget = fget
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc
        self._name = ""

    def __get__(self, obj, objtype=None):
        """Magic method. Return the response of the fget function."""
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError(f"property '{self._name}' has no getter")
        return self.fget(obj)


class CachedPropertyDescriptor:
    def __init__(self, func):
        self.func = func
        self.attrname = None
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__

    def __set_name__(self, owner, name):
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it.")
        try:
            cache = instance.__dict__
        except AttributeError:  # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        val = cache.get(self.attrname, _NOT_FOUND)
        if val is _NOT_FOUND:
            val = self.func(instance)
            try:
                cache[self.attrname] = val
            except TypeError:
                msg = (
                    f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                    f"does not support item assignment for caching {self.attrname!r} property."
                )
                raise TypeError(msg) from None
        return val

    __class_getitem__ = classmethod(GenericAlias)



class ResponseDescriptor(BaseDescriptor):
    """Descriptor returning the raw response."""

    def __get__(self, obj, objtype):
        """Magic method. Return the response data."""
        data = obj.data.get(self._required_endpoint, {})
        return data


class JsonDescriptor(BaseDescriptor):
    """JasonPath gateway property descriptor."""

    def __init__(
            self,
            jsonpath_expr: str,
            required_endpoint: str | None = None,
            cache: int = 0,
    ) -> None:
        super().__init__(required_endpoint, cache)
        self.jsonpath_expr = jsonpath_expr

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the jasonpath expression."""
        if self._required_endpoint:
            data = obj.data.get(self._required_endpoint, {})
        else:
            data = obj.data or {}
        return self.resolve(self.jsonpath_expr, data)

    # @classmethod
    # def resolve_old(cls, path: str, data: dict, default: str | int | float = None):
    #     """Classmethod to resolve a given JsonPath."""
    #     _LOGGER.debug(f"Resolving jsonpath: {path} using data: {data}")
    #     if path == "":
    #         return data
    #     result = jsonpath(data, dedent(path))
    #     if result is False:
    #         _LOGGER.debug(
    #             f"The configured jsonpath: {path}, did not return anything!"
    #         )
    #         return default

    #     if isinstance(result, list) and len(result) == 1:
    #         result = result[0]

    #     _LOGGER.debug(f"The configured jsonpath: {path}, did return {result}")
    #     return result

    @classmethod
    def resolve(cls, path: str, data: dict, default: str | int | float = None):
        """Classmethod to resolve a given jsonpath using jsonpath-ng."""
        if path == "" or data is None:
            return data

        jsonpath_expr = parse(dedent(path))
        result = [match.value for match in jsonpath_expr.find(data)]

        if result == []:
            _LOGGER.debug(
                f"The configured jsonpath: {path}, did not return anything!"
            )
            return default

        if isinstance(result, list) and len(result) == 1:
            result = result[0]

        return result


class ModelDescriptor(BaseDescriptor):

    def __init__(
            self,
            model_cls,
            jsonpath_expr: str,
            required_endpoint: str | None = None,
            cache: int = 0,
    ) -> None:
        super().__init__(required_endpoint, cache)
        self.model_cls = model_cls
        self.jsonpath_expr = jsonpath_expr

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the jasonpath expression."""
        if self._required_endpoint:
            data = obj.data.get(self._required_endpoint, {})
        else:
            data = obj.data or {}

        return self.resolve(self.jsonpath_expr, data)

    def resolve(cls, jsonpath_expr, model_cls, data):

        result = JsonDescriptor.resolve(jsonpath_expr, data)
        if result is not None:
            return model_cls.from_result(result)



class RegexDescriptor(BaseDescriptor):
    """Regex gateway property descriptor."""

    def __init__(self, regex, required_endpoint, cache: int = 0):
        super().__init__(required_endpoint, cache)
        self._regex = regex

    def __get__(self, obj, objtype=None):
        """Magic method. Resolve the regex expression."""
        data = obj.data.get(self._required_endpoint, "")
        return self.resolve(self._regex, data)

    @classmethod
    def resolve(cls, regex: str, data: str):
        """Classmethod to resolve a given REGEX."""
        text = data
        _LOGGER.debug(
            f"The text: {text}"
        )
        match = re.search(regex, text, re.MULTILINE)
        if match:
            if match.group(2) in {"kW", "kWh"}:
                result = float(match.group(1)) * 1000
            elif match.group(2) in {"mW", "MWh"}:
                result = float(match.group(1)) * 1000000
            else:
                result = float(match.group(1))
        else:
            _LOGGER.debug(
                f"The configured REGEX: {regex}, did not return anything!"
            )
            return None

        f"The configured REGEX: {regex}, did return {result}"
        return result
