"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import json
import time
import logging

import httpx
from lxml import etree

from awesomeversion import AwesomeVersion

#from const import AVAILABLE_PROPERTIES
#from endpoint import GatewayEndpoint
#from descriptors import ResponseDescriptor, JsonDescriptor, RegexDescriptor, PropertyDescriptor


def test():
    
    x = {}
    v = x.values()
    print(type(v))
    return
    
    
    response = httpx.get("http://envoy.local/info.xml")
    
    xml = etree.fromstring(response.content)

    
    find = xml.findtext("web-tokens1")
    
    if fw := xml.find("device/software"):
        firmware = AwesomeVersion(fw.text[1:])
        print(firmware)
    
    print(bool(find))

    #if (device_tag := xml.find("device")) is not None:




test()


