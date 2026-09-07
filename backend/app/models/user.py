# user.py — User model
# I keep role-based access here: STUDENT, LECTURER, IFMSO, TIMETABLER, ADMIN

from sqlalchemy import Column, Integer, String, Enum as SQLEnum
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                    # "Dr. Mushi", "IFMSO Office", etc.
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    role = Column(
        SQLEnum('STUDENT', 'LECTURER', 'IFMSO', 'TIMETABLER', 'ADMIN', name="user_role"),
        nullable=False,
        default='STUDENT'
    )

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"