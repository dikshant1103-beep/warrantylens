"""Application exceptions + RFC 7807 problem+json handlers."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base application error mapped to a problem+json response."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    title: str = "Bad Request"

    def __init__(self, detail: str | None = None, *, title: str | None = None):
        self.detail = detail or self.title
        if title:
            self.title = title
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not Found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Authentication Failed"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Permission Denied"


def _problem(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _problem(exc.status_code, exc.title, exc.detail, str(request.url.path))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _problem(
            exc.status_code,
            exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            str(exc.detail),
            str(request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            media_type="application/problem+json",
            content={
                "type": "about:blank",
                "title": "Validation Error",
                "status": 422,
                "detail": "Request validation failed",
                "instance": str(request.url.path),
                "errors": jsonable_encoder(exc.errors()),
            },
        )
