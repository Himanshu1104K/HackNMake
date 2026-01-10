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
    
    Note: websocket.accept() should be called by the route handler before calling this function.
    """
    try:
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

                    # Take last 5 records for averaging (data format: {id: [data(object), data(object), ...]})
                    last_5_records = (
                        data_records[:5] if len(data_records) >= 5 else data_records
                    )

                    # Get the latest data record for other fields (location, accelerometer, etc.)
                    latest_record = data_records[0]

                    # Parse health data from last 5 records (averaged)
                    health_metrics = None
                    if initial_sent:
                        # After initial send, calculate health status from averaged last 5 records
                        health_metrics = parse_health_data(
                            last_5_records, device_id=animal_id
                        )
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

                    # Build health status object (one entity per animal with averaged health metrics)
                    health_status_obj = AnimalHealthStatus(
                        id=animal_id,  # Use animal_id as the id
                        animal_id=animal_id,
                        accelerometer=latest_record.get("accelerometer"),
                        gyroscrope=latest_record.get("gyroscrope"),
                        longitude=latest_record.get("longitude"),
                        latitude=latest_record.get("latitude"),
                        # Use averaged values from parse_health_data if available, otherwise use latest record
                        blood_pressure=(
                            health_metrics.get("blood_pressure")
                            if health_metrics and initial_sent
                            else latest_record.get("blood_pressure")
                        ),
                        body_temp=(
                            health_metrics.get("body_temp")
                            if health_metrics and initial_sent
                            else latest_record.get("body_temp")
                        ),
                        heart_rate=(
                            health_metrics.get("heart_rate")
                            if health_metrics and initial_sent
                            else latest_record.get("heart_rate")
                        ),
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
                try:
                    await websocket.send_json(response.model_dump())
                except Exception as e:
                    # WebSocket may be closed - break the loop
                    logger.warning(f"Failed to send data to WebSocket: {e}")
                    break

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
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    await asyncio.sleep(5)  # Wait before retrying
                except Exception:
                    # WebSocket is closed - break the loop
                    logger.warning("WebSocket closed, stopping health status updates")
                    break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        # Don't close here - let the route handler manage the connection lifecycle
