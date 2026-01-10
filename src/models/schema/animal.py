from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.db import Base


class Animal(Base):
    __tablename__ = "animal"

    id = Column(String, primary_key=True)
    animal_id = Column(String, ForeignKey("animals.id"), nullable=False)
    status = Column(String, nullable=True)
    is_critical = Column(Boolean, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), nullable=False, onupdate=func.now()
    )

    # Relationships
    animal_type = relationship("Animals", back_populates="animal_instances")
    data_records = relationship(
        "Data", back_populates="animal", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_animal_animal_id", "animal_id"),
        Index("idx_animal_status", "status"),
        Index("idx_animal_is_critical", "is_critical"),
    )
