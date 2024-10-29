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
    firmware_version: AwesomeVersion | None = None
    imeter: bool | None = None
    web_tokens: bool | None = None

    @classmethod
    def from_response(cls, response: httpx.Response) -> Info:
        """Instantiate the instance from a response."""
        xml = etree.fromstring(response.content)

        if (fw := xml.find("device/software")) is not None:
            firmware_version = AwesomeVersion(fw.text[1:])
        else:
            firmware_version = None

        if (imeter := xml.findtext("device/imeter")) is not None:
            imeter = bool(imeter)

        if (web_tokens := xml.findtext("web-tokens")) is not None:
            web_tokens = bool(web_tokens)

        return cls(
            serial_number=xml.findtext("device/sn"),
            part_number=xml.findtext("device/pn"),
            firmware_version=firmware_version,
            imeter=imeter,
            web_tokens=web_tokens,
        )
