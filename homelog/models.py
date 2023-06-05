from datetime import datetime

from pydantic import BaseModel


class Measurement(BaseModel):
    value: float
    measurement: str
    created_at: datetime
