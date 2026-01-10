from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.db import Base


class Animals(Base):
    __tablename__ = "animals"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), nullable=False, onupdate=func.now()
    )

    # Relationships
    animal_instances = relationship(
        "Animal", back_populates="animal_type", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (Index("idx_animals_created_at", "created_at"),)
