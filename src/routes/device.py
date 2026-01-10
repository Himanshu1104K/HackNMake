from starlette.websockets import WebSocket
from src.core.configs import settings
from fastapi import (
    APIRouter,
    WebSocket,
    UploadFile,
    File,
    HTTPException,
)
from pydantic import BaseModel
from typing import Optional
from src.utils.logging import get_logger
from src.models.animal import Animal
from src.services.device.device_data import get_device_data, handle_device_data
from src.services.device.animals import (
    get_animals,
    create_animal,
    get_animal_by_slug,
    import_animals_from_csv,
)

logger = get_logger(__name__)

router = APIRouter(tags=["Device Data"])


class AnimalData(BaseModel):
    id: str
    name: str


class AnimalDataResponse(BaseModel):
    data: list[AnimalData]
    total: int
    page: Optional[int]
    page_size: Optional[int]


class ImportAnimalsResponse(BaseModel):
    status: str
    created: int
    skipped: int
    errors: int
    error_details: list[str] = []
    message: str | None = None


@router.websocket("/ws")
async def device_data(websocket: WebSocket):
    device_data = None
    try:
        await websocket.accept()

        id = websocket.query_params.get("id")
        try:
            device_data = await get_device_data(id)
            if device_data is not None:
                await handle_device_data(websocket, device_data)
            else:
                try:
                    await websocket.send_json(
                        {"type": "error", "message": "device doesn't exist"}
                    )
                    await websocket.close(code=1008, reason="device doesn't exist")
                except Exception:
                    # WebSocket may already be closed
                    pass

        except Exception as e:
            try:
                await websocket.send_json(
                    {"type": "error", "message": f"device doesn't exist: {e}"}
                )
                await websocket.close(code=1008, reason=f"device doesn't exist: {e}")
            except Exception:
                # WebSocket may already be closed
                pass
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        try:
            await websocket.close(code=1008, reason=f"Unexpected error: {e}")
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


@router.get("/animals", response_model=AnimalDataResponse)
async def get_animals_route(
    page_number: int = 1,
    page_size: int = 10,
):
    result = await get_animals(page_number, page_size)
    return AnimalDataResponse(
        data=result["data"],
        total=result["total"],
        page=page_number,
        page_size=page_size,
    )


@router.get("/animal/{slug}", response_model=AnimalDataResponse)
async def get_animal_route(slug: str):
    result = await get_animal_by_slug(slug)
    if result["total"] == 0:
        raise HTTPException(
            status_code=404, detail=f"Animal with slug '{slug}' not found"
        )
    return AnimalDataResponse(
        data=result["data"],
        total=result["total"],
        page=None,
        page_size=None,
    )


@router.post("/animal")
async def create_animal_data(animal: Animal):
    return await create_animal(
        animal_id=animal.animal_id,
        device_id=animal.device_id,
    )


@router.get("/animal/{id}/id")
async def get_animal_data_route(id: str):
    result = await get_device_data(id)
    return result


@router.post("/animals/import", response_model=ImportAnimalsResponse)
async def import_animals_from_csv_route(file: UploadFile = File(...)):
    """
    Import animals from a CSV file.

    The CSV file must contain a 'name' column with animal names.
    Each row will create a new animal record in the database.
    """
    try:
        # Validate file type
        if not file.filename.endswith(".csv"):
            return ImportAnimalsResponse(
                status="error",
                message="File must be a CSV file",
                created=0,
                skipped=0,
                errors=0,
            )

        # Import animals from CSV
        result = await import_animals_from_csv(file.file)

        return ImportAnimalsResponse(
            status=result.get("status", "error"),
            created=result.get("created", 0),
            skipped=result.get("skipped", 0),
            errors=result.get("errors", 0),
            error_details=result.get("error_details", []),
            message=result.get("message"),
        )
    except Exception as e:
        logger.error(f"Error importing animals from CSV: {e}")
        return ImportAnimalsResponse(
            status="error",
            message=str(e),
            created=0,
            skipped=0,
            errors=1,
        )
