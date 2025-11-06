from pydantic import BaseModel

class HerbResponse(BaseModel):
    common_name: str
    scientific_name: str
    uses: str
