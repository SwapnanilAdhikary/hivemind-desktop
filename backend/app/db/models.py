from __future__ import annotations

import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), nullable=False, index=True)
    sender = Column(String(256), nullable=False)
    sender_name = Column(String(256), default="")
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    read = Column(Boolean, default=False)
    replied = Column(Boolean, default=False)
    reply_content = Column(Text, default="")
    conversation_id = Column(String(256), default="")
    metadata_json = Column(JSON, default=dict)


class Trace(Base):
    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    agent_name = Column(String(128), nullable=False)
    node_name = Column(String(128), nullable=False)
    input_state = Column(JSON, default=dict)
    output_state = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    duration_ms = Column(Float, default=0.0)

    decisions = relationship("Decision", back_populates="trace", cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(Integer, ForeignKey("traces.id"), nullable=False)
    node_name = Column(String(128), nullable=False)
    reasoning = Column(Text, default="")
    chosen_action = Column(String(128), default="")
    alternatives = Column(JSON, default=list)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    trace = relationship("Trace", back_populates="decisions")


class Tool(Base):
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text, default="")
    source_code = Column(Text, nullable=False)
    parameters_schema = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    usage_count = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)


class PlatformStatus(Base):
    __tablename__ = "platform_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), unique=True, nullable=False)
    connected = Column(Boolean, default=False)
    last_checked = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text, default="")
