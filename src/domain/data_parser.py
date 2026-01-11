import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from src.models.schema.animal import Animal as AnimalModel
from src.core.db import SessionLocal
from src.core.configs import settings
from src.utils.logging import get_logger
from src.utils.prompts import DATA_PARSER_PROMPT

logger = get_logger(__name__)


async def parse_health_data(
    data_records: List[Dict], device_id: Optional[str] = None
) -> Dict[str, Optional[float]]:
    """
    Parse health data from data records and calculate overall health percentage and status using LLM.
    Automatically updates animal is_critical flag in database if health status is critical.

    Args:
        data_records: List of data record dictionaries containing health metrics
        device_id: Optional device ID (Animal.id) to update is_critical in database if critical

    Returns:
        dict: Dictionary with 'overall_health_percentage', 'health_status', 'blood_pressure',
              'body_temp', and 'heart_rate'. Returns None for both if data is insufficient
    """
    if not data_records or len(data_records) == 0:
        return {"overall_health_percentage": None, "health_status": None}

    try:
        # Take last 5 records for averaging (or all if less than 5)
        records_to_analyze = (
            data_records[:5] if len(data_records) >= 5 else data_records
        )

        # Initialize LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            streaming=False,
        )

        # Create chain with prompt and output parser
        chain = DATA_PARSER_PROMPT | llm | StrOutputParser()

        # Prepare inputs for the prompt
        inputs = {
            "data_records": json.dumps(records_to_analyze, indent=2),
        }

        # Invoke the chain
        result = await chain.ainvoke(inputs)

        # Parse the LLM response (expecting JSON format)
        try:
            parsed_result = json.loads(result)
        except json.JSONDecodeError:
            # If response is not JSON, try to extract key information
            logger.warning(f"LLM response is not valid JSON: {result}")
            # Fallback: return None values
            return {"overall_health_percentage": None, "health_status": None}

        # Extract health metrics from parsed result
        overall_health_percentage = parsed_result.get("overall_health_percentage")
        health_status = parsed_result.get("health_status")
        blood_pressure = parsed_result.get("blood_pressure")
        body_temp = parsed_result.get("body_temp")
        heart_rate = parsed_result.get("heart_rate")

        # Update animal is_critical flag in database if critical and device_id is provided
        if health_status == "critical" and device_id:
            update_animal_status_if_critical(device_id, health_status)

        return {
            "overall_health_percentage": (
                round(overall_health_percentage, 2)
                if overall_health_percentage is not None
                else None
            ),
            "health_status": health_status,
            "blood_pressure": blood_pressure,
            "body_temp": (round(body_temp, 1) if body_temp is not None else None),
            "heart_rate": heart_rate,
        }

    except Exception as e:
        logger.error(f"Error parsing health data: {e}")
        return {"overall_health_percentage": None, "health_status": None}


def update_animal_status_if_critical(
    device_id: str, health_status: Optional[str]
) -> bool:
    """
    Update animal is_critical flag in the database if health status is critical.
    Does not modify the status field (which is managed by WebSocket connection state).

    Args:
        device_id: The animal device ID (Animal.id in the database)
        health_status: The health status from parse_health_data ('normal', 'warning', or 'critical')

    Returns:
        bool: True if the is_critical flag was updated, False otherwise
    """
    if health_status != "critical":
        return False

    db: Session = SessionLocal()
    try:
        # Find the animal by device ID
        animal = db.query(AnimalModel).filter(AnimalModel.id == device_id).first()

        if not animal:
            logger.warning(f"Animal with device_id {device_id} not found")
            return False

        # Only update is_critical flag, not status
        animal.is_critical = True

        db.commit()
        db.refresh(animal)

        logger.info(f"Updated animal {device_id} is_critical to True")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating animal is_critical for {device_id}: {e}")
        return False
    finally:
        db.close()
