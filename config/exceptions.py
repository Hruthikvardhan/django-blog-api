"""Custom DRF exception handler that keeps every error shaped as {"detail": "..."}."""
from typing import Any, Optional

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _first_message(data: Any) -> str:
    """Dig through nested dict/list validation errors and return the first message."""
    if isinstance(data, dict):
        for key, value in data.items():
            message = _first_message(value)
            if key in ("non_field_errors", "detail"):
                return message
            return f"{key}: {message}"
        return "Invalid input."
    if isinstance(data, (list, tuple)):
        return _first_message(data[0]) if data else "Invalid input."
    return str(data)


def custom_exception_handler(exc: Exception, context: dict) -> Optional[Response]:
    """
    Wrap DRF's default handler.

    * Validation errors -> {"detail": "<first error>", "errors": {field: [msgs]}}
      (the `errors` key lets forms show per-field messages).
    * Everything else   -> {"detail": "<message>"}
    """
    response = exception_handler(exc, context)
    if response is None:
        return None  # unhandled exception -> Django returns a 500

    data = response.data
    if isinstance(exc, ValidationError):
        response.data = {"detail": _first_message(data), "errors": data}
    elif isinstance(data, dict) and "detail" in data:
        response.data = {"detail": str(data["detail"])}
    else:
        response.data = {"detail": _first_message(data)}
    return response
