import json
import uuid
from starlette.websockets import WebSocket
from sqlalchemy.orm import Session, joinedload
from src.models.schema.animal import Animal as AnimalModel
from src.models.schema.data import Data as DataModel
from src.core.db import SessionLocal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def update_animal_status(device_id: str, status: str) -> bool:
    """
    Update animal status in the database.

    Args:
        device_id: The animal device ID (Animal.id in the database)
        status: The status to set (e.g., "active", "deactive")

    Returns:
        bool: True if the status was updated, False otherwise
    """
    db: Session = SessionLocal()
    try:
        # Find the animal by device ID
        animal = db.query(AnimalModel).filter(AnimalModel.id == device_id).first()

        if not animal:
            logger.warning(f"Animal with device_id {device_id} not found")
            return False

        # Update status
        animal.status = status

        db.commit()
        db.refresh(animal)

        logger.info(f"Updated animal {device_id} status to {status}")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating animal status for {device_id}: {e}")
        return False
    finally:
        db.close()


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
        logger.warning("Device ID not found in device_data")
        try:
            await websocket.send_json({"type": "error", "message": "Device ID not found"})
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
        return

    logger.info(f"Starting WebSocket data handler for device {device_id}")

    try:
        while True:
            try:
                logger.debug(f"Waiting for data from device {device_id}")
                data = await websocket.receive_json()
                logger.debug(f"Received data from device {device_id}: {list(data.keys())}")
                
                await manage_data(device_id, data)
                logger.debug(f"Successfully processed data for device {device_id}")
                
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON received from device {device_id}: {e}. "
                    f"Raw error: {str(e)}"
                )
                try:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid JSON format"}
                    )
                    logger.debug(f"Sent error response to device {device_id}")
                except Exception as send_error:
                    # WebSocket is closed - break the loop
                    logger.warning(
                        f"WebSocket closed while sending error to device {device_id}. "
                        f"Close error: {send_error}"
                    )
                    break
            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                logger.error(
                    f"Error processing data for device {device_id}: "
                    f"Type: {error_type}, Message: {error_message}, "
                    f"Exception: {repr(e)}"
                )
                try:
                    await websocket.send_json(
                        {"type": "error", "message": f"Error processing data: {error_message}"}
                    )
                    logger.debug(f"Sent error response to device {device_id}")
                except Exception as send_error:
                    # WebSocket is closed - break the loop
                    send_error_type = type(send_error).__name__
                    logger.warning(
                        f"WebSocket closed while sending error to device {device_id}. "
                        f"Send error type: {send_error_type}, "
                        f"Send error message: {str(send_error)}"
                    )
                    break
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        logger.error(
            f"WebSocket connection error for device {device_id}: "
            f"Type: {error_type}, Message: {error_message}, "
            f"Exception: {repr(e)}"
        )
        # Don't close here - let the route handler manage the connection lifecycle
    finally:
        logger.info(f"WebSocket data handler ended for device {device_id}")