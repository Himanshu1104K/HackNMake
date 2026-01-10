from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.models.schema.animal import Animal as AnimalModel
from src.models.schema.data import Data as DataModel
from src.core.db import SessionLocal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def fetch_active_animals_data() -> dict:
    """
    Fetch the last 8 data records for each animal with active status.

    Returns:
        dict: Dictionary in format {animal_id: [data]} where each data entry
              is a dictionary containing the data record fields
    """
    db: Session = SessionLocal()
    result = {}

    try:
        # Query all animals with status "active"
        active_animals = (
            db.query(AnimalModel).filter(AnimalModel.status == "active").all()
        )

        logger.info(f"Found {len(active_animals)} active animals")

        # For each active animal, fetch the last 8 data records
        for animal in active_animals:
            data_records = (
                db.query(DataModel)
                .filter(DataModel.animal_id == animal.id)
                .order_by(desc(DataModel.created_at))
                .limit(8)
                .all()
            )

            # Convert data records to dictionaries
            data_list = []
            for record in data_records:
                data_dict = {
                    "id": record.id,
                    "accelerometer": record.accelerometer,
                    "gyroscrope": record.gyroscrope,
                    "longitude": record.longitude,
                    "latitude": record.latitude,
                    "blood_pressure": record.blood_pressure,
                    "body_temp": record.body_temp,
                    "heart_rate": record.heart_rate,
                    "created_at": (
                        record.created_at.isoformat() if record.created_at else None
                    ),
                }
                data_list.append(data_dict)

            # Store in result dictionary with animal id as key
            result[animal.id] = data_list

            logger.info(f"Fetched {len(data_list)} data records for animal {animal.id}")

        return result

    except Exception as e:
        logger.error(f"Error fetching active animals data: {e}")
        return {}
    finally:
        db.close()
