import json
import uuid
from starlette.websockets import WebSocket
from sqlalchemy.orm import Session, joinedload
from src.models.schema.animal import Animal as AnimalModel
from src.models.schema.data import Data as DataModel
from src.core.db import SessionLocal
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def get_device_data(id: str):
    """
    Get device data by joining Animal with Animals table.

    Args:
        id: The device/animal ID (Animal.id)

    Returns:
        dict: Dictionary with id, name, status, is_critical, and created_at
              Returns None if device not found
    """
    db: Session = SessionLocal()
    try:
        # Query Animal and eagerly load the related Animals table using joinedload
        data = (
            db.query(AnimalModel)
            .options(joinedload(AnimalModel.animal_type))
            .filter(AnimalModel.id == id)
            .first()
        )

        if not data:
            logger.warning(f"Device with id {id} not found")
            return None

        # Get name from the related Animals table
        name = data.animal_type.name if data.animal_type else None

        return {
            "id": data.id,
            "name": name,
            "status": data.status,
            "is_critical": data.is_critical,
            "created_at": data.created_at.isoformat() if data.created_at else None,
        }
    except Exception as e:
        logger.error(f"Error getting device data: {e}")
        return None
    finally:
        db.close()


async def manage_data(device_id: str, data: dict) -> None:
    """
    Process and store device data in the database.

    Args:
        device_id: The device/animal ID (maps to animal_id in Data table)
        data: Dictionary containing device sensor data
    """
    db: Session = SessionLocal()
    try:
        # Generate unique ID for the data record
        data_id = str(uuid.uuid4())

        # Extract data fields with safe defaults
        accelerometer = data.get("accelerometer")
        gyroscrope = data.get("gyroscrope") or data.get(
            "gyroscope"
        )  # Handle typo variant
        longitude = data.get("longitude")
        latitude = data.get("latitude")

        new_data = DataModel(
            id=data_id,
            animal_id=device_id,
            accelerometer=accelerometer,
            gyroscrope=gyroscrope,
            longitude=float(longitude) if longitude is not None else None,
            latitude=float(latitude) if latitude is not None else None,
        )

        db.add(new_data)
        db.commit()

        logger.info(f"Stored data record {data_id} for device {device_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to manage data for device {device_id}: {e}")
        raise
    finally:
        db.close()


async def handle_device_data(websocket: WebSocket, device_data: dict):
    """Handle websocket data reception every 5 seconds"""
    device_id = device_data.get("id") or device_data.get("device_id")

    if not device_id:
        await websocket.send_json({"type": "error", "message": "Device ID not found"})
        return

    try:
        while True:
            try:
                data = await websocket.receive_json()
                await manage_data(device_id, data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await websocket.send_json(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            except Exception as e:
                logger.error(f"Error processing data: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        await websocket.close()
