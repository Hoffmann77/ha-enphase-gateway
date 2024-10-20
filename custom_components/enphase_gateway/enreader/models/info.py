"""Model for the info.xml endpoint."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from awesomeversion import AwesomeVersion
from lxml import etree


@dataclass(slots=True)
class Info:
    """Model for the `info.xml` endpoint."""

    serial_number: str | None = None
    part_number: str | None = None
    firmware_version: AwesomeVersion | None
    imeter: bool = False
    web_tokens: bool = False

    @classmethod
    def from_response(cls, response: httpx.Response) -> Info:
        """Instantiate the Info model from the response."""
        xml = etree.fromstring(response.content)

        if (fw := xml.find("device/software") is not None):
            firmware_version = AwesomeVersion(fw.text[1:])
        else:
            firmware_version = None

        return cls(
            serial_number=xml.findtext("device/sn"),
            part_number=xml.findtext("device/pn"),
            firmware_version=firmware_version,
            imeter=bool(xml.findtext("device/imeter")),
            web_tokens=bool(xml.findtext("web-tokens")),
        )
