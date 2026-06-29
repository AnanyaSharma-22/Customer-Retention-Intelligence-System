from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    dataset_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    recency: Mapped[int] = mapped_column(Integer)

    frequency: Mapped[int] = mapped_column(Integer)

    monetary: Mapped[float] = mapped_column(Float)

    churn_probability: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    churn_prediction: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    segment: Mapped[str] = mapped_column(
        String(50),
        default="Unknown",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    dataset = relationship(
        "Dataset",
        back_populates="customers",
    )
    predictions = relationship(
    "Prediction",
    back_populates="customer",
    cascade="all, delete-orphan",
)