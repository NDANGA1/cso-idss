# base.py — declarative base for SQLAlchemy models
# all my models inherit from Base

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass