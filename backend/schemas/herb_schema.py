from pydantic import BaseModel
from typing import Optional

class HerbResponse(BaseModel):
    common_name: str
    scientific_name: str
    uses: str
    processing_time: Optional[float] = None  # Time in seconds
