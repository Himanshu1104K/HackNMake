from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from src.models.schema.animal import Animal as AnimalModel
from src.core.db import SessionLocal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def parse_health_data(
    data_records: List[Dict], device_id: Optional[str] = None
) -> Dict[str, Optional[float]]:
    """
    Parse health data from data records and calculate overall health percentage and status.
    Automatically updates animal status in database if health status is critical.

    Args:
        data_records: List of data record dictionaries containing health metrics
        device_id: Optional device ID (Animal.id) to update status in database if critical

    Returns:
        dict: Dictionary with 'overall_health_percentage' and 'health_status'
              Returns None for both if data is insufficient
    """
    if not data_records or len(data_records) == 0:
        return {"overall_health_percentage": None, "health_status": None}

    try:
        # Extract health metrics from the latest record
        latest_record = data_records[
            0
        ]  # Assuming records are sorted by created_at desc

        blood_pressure = latest_record.get("blood_pressure")
        body_temp = latest_record.get("body_temp")
        heart_rate = latest_record.get("heart_rate")

        # Calculate individual health scores (0-100, where 100 is best)
        scores = []

        # Blood pressure score (normal: 90-120/60-80 = 100, high/low = lower score)
        if blood_pressure and isinstance(blood_pressure, dict):
            systolic = blood_pressure.get("systolic")
            diastolic = blood_pressure.get("diastolic")
            if systolic and diastolic:
                # Normal range: 90-120 systolic, 60-80 diastolic
                if 90 <= systolic <= 120 and 60 <= diastolic <= 80:
                    bp_score = 100
                elif 120 < systolic <= 140 or 80 < diastolic <= 90:
                    bp_score = 70  # Warning
                elif systolic > 140 or diastolic > 90:
                    bp_score = 30  # Critical
                elif systolic < 90 or diastolic < 60:
                    bp_score = 50  # Low
                else:
                    bp_score = 60
                scores.append(bp_score)

        # Body temperature score (normal: 36.5-37.5°C = 100)
        if body_temp is not None:
            if 36.5 <= body_temp <= 37.5:
                temp_score = 100
            elif 37.5 < body_temp <= 38.0:
                temp_score = 70  # Warning
            elif body_temp > 38.0:
                temp_score = 30  # Critical (fever)
            elif body_temp < 36.5:
                temp_score = 50  # Low
            else:
                temp_score = 60
            scores.append(temp_score)

        # Heart rate score (normal: 60-100 bpm = 100)
        if heart_rate is not None:
            if 60 <= heart_rate <= 100:
                hr_score = 100
            elif 100 < heart_rate <= 120:
                hr_score = 70  # Warning
            elif heart_rate > 120:
                hr_score = 30  # Critical
            elif heart_rate < 60:
                hr_score = 50  # Low
            else:
                hr_score = 60
            scores.append(hr_score)

        # Calculate overall health percentage (average of all scores)
        if scores:
            overall_health_percentage = sum(scores) / len(scores)

            # Determine health status
            if overall_health_percentage >= 80:
                health_status = "normal"
            elif overall_health_percentage >= 50:
                health_status = "warning"
            else:
                health_status = "critical"

            # Update animal status in database if critical and device_id is provided
            if health_status == "critical" and device_id:
                update_animal_status_if_critical(device_id, health_status)

            return {
                "overall_health_percentage": round(overall_health_percentage, 2),
                "health_status": health_status,
            }
        else:
            return {"overall_health_percentage": None, "health_status": None}

    except Exception as e:
        logger.error(f"Error parsing health data: {e}")
        return {"overall_health_percentage": None, "health_status": None}


def update_animal_status_if_critical(
    device_id: str, health_status: Optional[str]
) -> bool:
    """
    Update animal status to 'critical' in the database if health status is critical.

    Args:
        device_id: The animal device ID (Animal.id in the database)
        health_status: The health status from parse_health_data ('normal', 'warning', or 'critical')

    Returns:
        bool: True if the status was updated, False otherwise
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

        # Update status and is_critical flag
        animal.status = "critical"
        animal.is_critical = True

        db.commit()
        db.refresh(animal)

        logger.info(f"Updated animal {device_id} status to critical")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating animal status for {device_id}: {e}")
        return False
    finally:
        db.close()
