from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.db import Base


class Data(Base):
    __tablename__ = "data"

    id = Column(String, primary_key=True)
    animal_id = Column(String, ForeignKey("animal.id"), nullable=False)
    accelerometer = Column(String, nullable=True)
    gyroscrope = Column(String, nullable=True)
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    blood_pressure = Column(JSONB, nullable=True)
    body_temp = Column(Float, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), nullable=False, onupdate=func.now()
    )

    # Relationships
    animal = relationship("Animal", back_populates="data_records")

    # Indexes
    __table_args__ = (
        Index("idx_data_animal_id", "animal_id"),
        Index("idx_data_created_at", "created_at"),
        Index("idx_data_location", "latitude", "longitude"),
    )
