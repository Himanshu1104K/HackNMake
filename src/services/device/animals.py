import uuid
from typing import Union
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models.schema.animal import Animal as AnimalModel
from src.models.schema.animals import Animals as AnimalsModel
from src.core.db import SessionLocal
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def get_animals(page_number: int, page_size: int):
    """
    Get a paginated list of animals from the animals table.

    Args:
        page_number: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        dict: Dictionary with 'data' (list of AnimalData) and 'total' (total count)
    """
    db: Session = SessionLocal()
    try:
        # Calculate offset
        offset = (page_number - 1) * page_size

        # Get total count
        total = db.query(func.count(AnimalsModel.id)).scalar()

        # Query animals with pagination
        animals = (
            db.query(AnimalsModel)
            .order_by(AnimalsModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        # Convert to AnimalData format
        data = [{"id": animal.id, "name": animal.name} for animal in animals]

        logger.info(
            f"Retrieved {len(data)} animals for page {page_number} (total: {total})"
        )

        return {"data": data, "total": total}
    except Exception as e:
        logger.error(f"Error retrieving animals: {e}")
        return {"data": [], "total": 0}
    finally:
        db.close()


async def get_animal_by_slug(slug: str):
    """
    Get animals whose names start with the slug from the database.

    Args:
        slug: The slug/prefix to match animal names

    Returns:
        dict: Dictionary with 'data' (list of AnimalData) and 'total' (total count)
    """
    db: Session = SessionLocal()
    try:
        # Query animals whose names start with the slug (case-insensitive)
        animals_query = db.query(AnimalsModel).filter(
            AnimalsModel.name.ilike(f"%{slug}%")
        )

        # Get total count
        total = animals_query.count()

        # Get all matching animals
        animals = animals_query.order_by(AnimalsModel.created_at.desc()).all()

        # Convert to AnimalData format (same format as get_animals)
        data = [{"id": animal.id, "name": animal.name} for animal in animals]

        logger.info(
            f"Retrieved {len(data)} animals starting with slug '{slug}' (total: {total})"
        )

        return {"data": data, "total": total}
    except Exception as e:
        logger.error(f"Error retrieving animals by slug: {e}")
        return {"data": [], "total": 0}
    finally:
        db.close()


async def import_animals_from_csv(csv_file: Union[str, object]) -> dict:
    """
    Import animals from a CSV file with a 'name' column using pandas.

    Args:
        csv_file: Path to CSV file (str) or file-like object

    Returns:
        dict: Statistics about the import (created, skipped, errors)
    """
    db: Session = SessionLocal()
    created_count = 0
    skipped_count = 0
    error_count = 0
    errors = []

    try:
        # Reset file position if it's a file-like object
        if hasattr(csv_file, "seek"):
            csv_file.seek(0)

        # Read CSV file using pandas
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            if hasattr(csv_file, "seek"):
                csv_file.seek(0)
            df = pd.read_csv(csv_file, encoding="latin-1")

        # Validate that 'Animal' column exists (case-insensitive check)
        column_names_lower = [col.lower() for col in df.columns]
        if "animal" not in column_names_lower:
            raise ValueError("CSV file must contain an 'Animal' column")

        # Find the actual column name (preserve case)
        animal_column = None
        for col in df.columns:
            if col.lower() == "animal":
                animal_column = col
                break

        # Get existing animal names for duplicate checking
        existing_animals = {
            animal.name.lower().strip(): animal.id
            for animal in db.query(AnimalsModel).all()
        }

        animals_to_create = []

        # Process each row in the dataframe
        for index, row in df.iterrows():
            row_num = index + 2  # +2 because index is 0-based and header is row 1
            try:
                # Get name value, handle NaN values
                name = (
                    str(row[animal_column]).strip()
                    if pd.notna(row[animal_column])
                    else ""
                )

                if not name or name == "nan":
                    skipped_count += 1
                    errors.append(f"Row {row_num}: Empty animal field, skipped")
                    continue

                # Check for duplicates (case-insensitive)
                name_lower = name.lower()
                if name_lower in existing_animals:
                    skipped_count += 1
                    logger.debug(f"Skipping duplicate animal: {name}")
                    continue

                # Generate unique ID
                animal_id = str(uuid.uuid4())

                # Create animal instance
                new_animal = AnimalsModel(id=animal_id, name=name)

                animals_to_create.append(new_animal)
                existing_animals[name_lower] = (
                    animal_id  # Track to avoid duplicates in same batch
                )

            except Exception as e:
                error_count += 1
                error_msg = f"Row {row_num}: Error processing - {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        # Bulk insert animals
        if animals_to_create:
            db.add_all(animals_to_create)
            db.commit()
            created_count = len(animals_to_create)
            logger.info(
                f"Successfully imported {created_count} animals from CSV using pandas"
            )

        return {
            "status": "success",
            "created": created_count,
            "skipped": skipped_count,
            "errors": error_count,
            "error_details": errors[:10] if errors else [],  # Limit error details
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error importing animals from CSV: {e}")
        return {
            "status": "error",
            "message": str(e),
            "created": created_count,
            "skipped": skipped_count,
            "errors": error_count,
        }
    finally:
        db.close()


async def create_animal(animal_id: str, device_id: str):
    """
    Create a new animal record in the database.

    Args:
        animal_id: The animal type ID (foreign key to animals.id)
        device_id: The device ID (primary key for animal.id)

    Returns:
        dict: Status and created animal data
    """
    db: Session = SessionLocal()
    try:
        # Check if animal with this device_id already exists
        existing_animal = (
            db.query(AnimalModel).filter(AnimalModel.id == device_id).first()
        )
        if existing_animal:
            logger.warning(f"Animal with device_id {device_id} already exists")
            return {
                "status": "error",
                "message": "Animal with this device_id already exists",
            }

        # Create new animal record
        new_animal = AnimalModel(
            id=device_id, animal_id=animal_id, status=None, is_critical=None
        )

        db.add(new_animal)
        db.commit()
        db.refresh(new_animal)

        logger.info(
            f"Created animal with device_id: {device_id}, animal_id: {animal_id}"
        )

        return {
            "status": "success",
            "data": {
                "id": new_animal.id,
                "animal_id": new_animal.animal_id,
                "status": new_animal.status,
                "is_critical": new_animal.is_critical,
                "created_at": (
                    new_animal.created_at.isoformat() if new_animal.created_at else None
                ),
                "updated_at": (
                    new_animal.updated_at.isoformat() if new_animal.updated_at else None
                ),
            },
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating animal: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
