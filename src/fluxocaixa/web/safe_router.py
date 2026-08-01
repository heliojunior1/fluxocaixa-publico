"""Utilities for safer route registration with automatic exception handling."""

import inspect
import logging
from functools import wraps

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)


def _rollback_session():
    """Rollback the database session to recover from errors."""
    try:
        from ..models.base import db
        db.session.rollback()
    except Exception as e:
        logger.warning("Failed to rollback session: %s", e)


def _e_erro_de_negocio(exc: Exception) -> bool:
    """RegraNegocioError atravessa o wrapper: o handler global converte em
    flash + redirect (HTML) ou 400 (API) — nunca 500. Import tardio para não
    carregar o pacote services na inicialização do router."""
    from ..services.validacao import RegraNegocioError

    return isinstance(exc, RegraNegocioError)


def handle_exceptions(func):
    """Wrap endpoint functions to provide basic exception handling."""

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                if _e_erro_de_negocio(exc):
                    _rollback_session()
                    raise
                logger.exception("Unhandled exception in endpoint: %s", exc)
                # Rollback session to recover from database errors
                _rollback_session()
                raise HTTPException(status_code=500, detail="Internal server error")

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if _e_erro_de_negocio(exc):
                _rollback_session()
                raise
            logger.exception("Unhandled exception in endpoint: %s", exc)
            # Rollback session to recover from database errors
            _rollback_session()
            raise HTTPException(status_code=500, detail="Internal server error")

    return sync_wrapper


class SafeAPIRouter(APIRouter):
    """APIRouter that automatically wraps endpoints with exception handling."""

    def add_api_route(self, path: str, endpoint, **kwargs):  # type: ignore[override]
        endpoint = handle_exceptions(endpoint)
        return super().add_api_route(path, endpoint, **kwargs)
