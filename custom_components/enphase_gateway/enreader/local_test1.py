"""Enphase(R) Gateway data access properties."""

from __future__ import annotations

import json
import time
import logging

import httpx
from lxml import etree

#from awesomeversion import AwesomeVersion

#from const import AVAILABLE_PROPERTIES
#from endpoint import GatewayEndpoint
#from descriptors import ResponseDescriptor, JsonDescriptor, RegexDescriptor, PropertyDescriptor





def test():
    y = False
    return 5 if y else 7

print(test())



class Reader:

    def __init__(self, host, gateway):
        self.host = host
        self.gateway = gateway

    def update(self):
        self.gateway.update(self.request)

    def request(self, url):
        v = f"{self.host}/{url}"
        print(v)
        #self.test_2.test(self.)



class Gateway:

    def __init__(self, url):
        self.url = url

    def update(self, request):
        print(request.__self__)

        request(self.url)





#gateway = Gateway("envoy.local")

#reader = Reader("host", gateway)


#reader.update()






