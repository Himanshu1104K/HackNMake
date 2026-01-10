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
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            # WebSocket may already be closed
            pass
    finally:
        # Only close if the WebSocket is still open
        try:
            await websocket.close()
        except RuntimeError:
            # WebSocket is already closed - ignore the error
            pass
        except Exception:
            # Any other error closing the WebSocket - ignore
            pass
