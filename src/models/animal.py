from pydantic import BaseModel


class Animal(BaseModel):
    device_id: str
    animal_id: str
