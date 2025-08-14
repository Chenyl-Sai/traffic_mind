from fastapi import FastAPI, Request
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from contextvars import ContextVar
from app.schemas.user.user import UserOut

current_user_context: ContextVar[UserOut | None] = ContextVar("current_user", default=None)
current_user_scope_context: ContextVar[list[str] | None] = ContextVar("current_user_scope", default=None)
