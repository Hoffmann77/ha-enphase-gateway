"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import json
import time
import logging

import httpx
from lxml import etree

#from const import AVAILABLE_PROPERTIES
#from endpoint import GatewayEndpoint
#from descriptors import ResponseDescriptor, JsonDescriptor, RegexDescriptor, PropertyDescriptor


def test():
    
    response = httpx.get("http://envoy.local/info.xml")
    
    xml = etree.fromstring(response.content)

    
    find = xml.findtext("web-tokens1")
    
    
    print(bool(find))

    #if (device_tag := xml.find("device")) is not None:




test()


