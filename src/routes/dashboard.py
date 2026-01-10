from starlette.websockets import WebSocket
from fastapi import (
    APIRouter,
    WebSocket,
)
from src.utils.logging import get_logger
from src.services.dashboard.animal_health_status import get_status

logger = get_logger(__name__)

router = APIRouter(tags=["Dashboard"])


@router.websocket("/ws/dashboard")
async def dashboard_data(websocket: WebSocket):
    try:
        await websocket.accept()
        await get_status(websocket)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()
