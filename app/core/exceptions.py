from __future__ import annotations


class AppError(Exception):
    """Base application exception."""


class DataAccessError(AppError):
    """Raised when database persistence fails."""


class AuthenticationError(AppError):
    """Raised when admin authentication fails."""


class ProductNotFoundError(AppError):
    """Raised when the requested product cannot be found."""


class ValidationError(AppError):
    """Raised when input data is invalid."""
