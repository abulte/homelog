from datetime import datetime, timezone

from pydantic import BaseModel, validator

from homelog import database


class Measurement(BaseModel):
    value: float
    measurement: str
    created_at: datetime

    @validator("created_at")
    def ensure_tz(cls, v):
        """We arbitrarly attach an UTC timezone to naive `created_at`"""
        if not v.tzinfo:
            v = v.replace(tzinfo=timezone.utc)
        return v

    @classmethod
    def query(cls, model, **kwargs):
        db = database.get()
        records = db[model].find(**kwargs)
        return [cls(**r) for r in records]
