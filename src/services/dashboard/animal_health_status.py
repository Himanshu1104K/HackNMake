import asyncio
from starlette.websockets import WebSocket
from pydantic import BaseModel
from typing import List, Optional
from src.services.dashboard.data_fetcher import fetch_active_animals_data
from src.domain.data_parser import parse_health_data
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AnimalHealthStatus(BaseModel):
    id: str
    animal_id: str
    accelerometer: Optional[str]
    gyroscrope: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    blood_pressure: Optional[dict]
    body_temp: Optional[float]
    heart_rate: Optional[int]
    overall_health_percentage: Optional[float] = None
    health_status: Optional[str] = None  # critical, warning, normal


class AnimalHealthStatusResponse(BaseModel):
    data: List[AnimalHealthStatus]
    total: int
    total_critical: int
    total_active: int
    total_device: int


async def get_status(websocket: WebSocket):
    """
    Send animal health status data to websocket every 5 seconds.

    Initially sends data with overall_health_percentage and health_status as None,
    then uses data_parser to calculate and send updated health status.
    """
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted for animal health status")

        # Send initial data with health_status and overall_health_percentage as None
        initial_sent = False

        while True:
            try:
                # Fetch active animals data
                animals_data = fetch_active_animals_data()

                # Process data and build response
                health_status_list = []
                total_critical = 0
                total_active = 0
                total_device = 0

                for animal_id, data_records in animals_data.items():
                    if not data_records:
                        continue

                    # Get the latest data record
                    latest_record = data_records[0]

                    # Parse health data
                    if initial_sent:
                        # After initial send, calculate health status
                        health_metrics = parse_health_data(data_records, device_id=animal_id)
                        overall_health_percentage = health_metrics.get(
                            "overall_health_percentage"
                        )
                        health_status = health_metrics.get("health_status")

                        # Count critical status
                        if health_status == "critical":
                            total_critical += 1
                    else:
                        # Initial send: set to None
                        overall_health_percentage = None
                        health_status = None

                    # Build health status object
                    health_status_obj = AnimalHealthStatus(
                        id=latest_record.get("id", ""),
                        animal_id=animal_id,
                        accelerometer=latest_record.get("accelerometer"),
                        gyroscrope=latest_record.get("gyroscrope"),
                        longitude=latest_record.get("longitude"),
                        latitude=latest_record.get("latitude"),
                        blood_pressure=latest_record.get("blood_pressure"),
                        body_temp=latest_record.get("body_temp"),
                        heart_rate=latest_record.get("heart_rate"),
                        overall_health_percentage=overall_health_percentage,
                        health_status=health_status,
                    )

                    health_status_list.append(health_status_obj)
                    total_active += 1
                    total_device += 1

                # Build response
                response = AnimalHealthStatusResponse(
                    data=health_status_list,
                    total=len(health_status_list),
                    total_critical=total_critical,
                    total_active=total_active,
                    total_device=total_device,
                )

                # Send to websocket
                await websocket.send_json(response.model_dump())

                if not initial_sent:
                    initial_sent = True
                    logger.info("Sent initial health status data")
                else:
                    logger.debug(
                        f"Sent health status update: {total_active} active animals, {total_critical} critical"
                    )

                # Wait 5 seconds before next send
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error sending health status data: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
                await asyncio.sleep(5)  # Wait before retrying

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        await websocket.close()
        logger.info("WebSocket connection closed")
