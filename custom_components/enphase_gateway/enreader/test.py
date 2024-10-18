"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import json
import time
import logging
from jsonpath import jsonpath
from typing import Callable

from jsonpath_ng import jsonpath as jsonpath_ng
from jsonpath_ng.ext import parse, filter

from textwrap import dedent

#from const import AVAILABLE_PROPERTIES
#from endpoint import GatewayEndpoint
#from descriptors import ResponseDescriptor, JsonDescriptor, RegexDescriptor, PropertyDescriptor


from .enreader import Enreader


enreader = Enreader("hostname")


