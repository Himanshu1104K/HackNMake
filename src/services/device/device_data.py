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
    Fetch animal by device ID and return id, name, status, is_critical, and created_at.

    Args:
        id: The device/animal ID (Animal.id)

    Returns:
        dict: Dictionary containing:
            - id: Animal device ID
            - name: Animal name from Animals table
            - status: Animal status
            - is_critical: Critical flag
            - created_at: Creation timestamp
        Returns None if device not found
    """
    db: Session = SessionLocal()
    try:
        # Fetch animal with joined Animals table to get the name
        animal = (
            db.query(AnimalModel)
            .options(joinedload(AnimalModel.animal_type))
            .filter(AnimalModel.id == id)
            .first()
        )

        if not animal:
            logger.warning(f"Animal with id {id} not found")
            return None

        # Extract name from related Animals table
        name = animal.animal_type.name if animal.animal_type else None

        return {
            "id": animal.id,
            "name": name,
            "status": animal.status,
            "is_critical": animal.is_critical,
            "created_at": animal.created_at.isoformat() if animal.created_at else None,
        }
    except Exception as e:
        logger.error(f"Error fetching animal data for id {id}: {e}")
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
        body_temp = data.get("body_temp")
        heart_rate = data.get("heart_rate")

        # Convert accelerometer and gyroscrope dicts to JSON strings if they are dicts
        if accelerometer is not None and isinstance(accelerometer, dict):
            accelerometer = json.dumps(accelerometer)
        if gyroscrope is not None and isinstance(gyroscrope, dict):
            gyroscrope = json.dumps(gyroscrope)

        new_data = DataModel(
            id=data_id,
            animal_id=device_id,
            accelerometer=accelerometer,
            gyroscrope=gyroscrope,
            longitude=float(longitude) if longitude is not None else None,
            latitude=float(latitude) if latitude is not None else None,
            body_temp=float(body_temp) if body_temp is not None else None,
            heart_rate=int(heart_rate) if heart_rate is not None else None,
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
                try:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid JSON format"}
                    )
                except Exception:
                    # WebSocket is closed - break the loop
                    logger.warning("WebSocket closed while processing data")
                    break
            except Exception as e:
                logger.error(f"Error processing data: {e}")
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except Exception:
                    # WebSocket is closed - break the loop
                    logger.warning("WebSocket closed while processing data")
                    break
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        # Don't close here - let the route handler manage the connection lifecycle
