import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Executive(Base):
    __tablename__ = "executives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=True)
    cik: Mapped[str | None] = mapped_column(String(20), nullable=True)  # SEC CIK number
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    profile: Mapped["PSIProfile | None"] = relationship(back_populates="executive", uselist=False)
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="executive")


class PSIProfile(Base):
    __tablename__ = "psi_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    executive_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executives.id"), unique=True)
    version: Mapped[int] = mapped_column(default=1)

    # PSI core dimensions (Kuhl's framework)
    action_orientation: Mapped[float] = mapped_column(Float, nullable=True)
    state_orientation: Mapped[float] = mapped_column(Float, nullable=True)
    self_regulation: Mapped[float] = mapped_column(Float, nullable=True)
    self_control: Mapped[float] = mapped_column(Float, nullable=True)
    positive_affect: Mapped[float] = mapped_column(Float, nullable=True)
    negative_affect: Mapped[float] = mapped_column(Float, nullable=True)
    volatility: Mapped[float] = mapped_column(Float, nullable=True)
    openness_to_risk: Mapped[float] = mapped_column(Float, nullable=True)

    # Full profile as structured text (for LLM prompt injection)
    profile_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Embedding for similarity search
    embedding = mapped_column(Vector(1536), nullable=True)

    source_documents: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list of source refs
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    executive: Mapped["Executive"] = relationship(back_populates="profile")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    executive_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executives.id"))
    simulation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    actual_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    executive: Mapped["Executive"] = relationship(back_populates="predictions")
