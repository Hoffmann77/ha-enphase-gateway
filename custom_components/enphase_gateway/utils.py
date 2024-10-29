"""Utilities."""

# from __future__ import annotations

# from collections.abc import Iterable
# from typing import Any, cast, overload


# def redact_sensitive_data[_T](
#         data: _T,
#         to_redact: Iterable[str],
#         placeholder: str = "<redacted>"
# ) -> _T:
#     """Redact sensitive strings in a dict."""
#     if not isinstance(data, dict):
#         return data

#     if isinstance(data, list):
#         return cast(_T, [async_redact_data(val, to_redact) for val in data])

#     redacted = data

#     for key, value in redacted:
#         if value is None:
#             continue
#         if isinstance(value, str):
#             # check if sensitive data is in value and replace
#             continue
#         if isinstance(value, dict):
#             redacted[key] = redact_sensitive_data(value, to_redact)

#     return redacted
