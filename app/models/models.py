from sqlalchemy import Boolean, Column, DateTime, Integer, Interval, String, ForeignKey, Enum, UniqueConstraint, JSON
from enum import Enum as PythonEnum
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.database import Base


class UserRole(str, PythonEnum):
    super_admin = "super_admin"
    admin =  "admin"
    user = "user"


class PrivateMessage(Base):
    __tablename__ = 'private_messages'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'), nullable=False)
    sender_id = Column(UUID, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(UUID, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    message = Column(String)
    fileUrl = Column(String)
    voiceUrl = Column(String)
    videoUrl = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    is_read = Column(Boolean, nullable=False, server_default='false')
    edited = Column(Boolean, server_default='false')
    id_return = Column(Integer)
    deleted = Column(Boolean, server_default='false')
    room_id = Column(UUID, nullable=True)
    is_sent = Column(Boolean, default=False)
    
    
class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('uuid_generate_v4()'), nullable=False)
    email = Column(String, nullable=False, unique=True)
    user_name = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    avatar = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    verified = Column(Boolean, nullable=False, server_default='false')
    token_verify = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.user)
    blocked = Column(Boolean, nullable=False, server_default='false')
    password_changed = Column(TIMESTAMP(timezone=True), nullable=True)
    company_id = Column(UUID, ForeignKey('companies.id', ondelete="CASCADE"), nullable=True)
    active = Column(Boolean, nullable=False, server_default='True')
    description = Column(String)

    # company = relationship("Company", back_populates="users")
    # bans = relationship("Ban", back_populates="users")
    # Relationships
    # reports = relationship("Report", back_populates="reported_by_user")
    # notifications = relationship("Notification", back_populates="moderator")

    __table_args__ = (
        UniqueConstraint('email', name='uq_user_email'),
        UniqueConstraint('user_name', name='uq_user_name'),
    )
    

class PrivateMessageVote(Base):
    __tablename__ = 'private_message_votes'

    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    message_id = Column(UUID, ForeignKey("private_messages.id", ondelete="CASCADE"), primary_key=True)
    dir = Column(Integer)



class FCMTokenManager(Base):
    __tablename__ = 'fcm_token_manager'

    id = Column(Integer, primary_key=True, nullable=False)
    user_id = Column(UUID, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    fcm_token = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))