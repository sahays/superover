from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .inspector import inspect_media, MediaInspectionError

app = FastAPI()

class InspectRequest(BaseModel):
    file_path: str

@app.post("/inspect")
async def inspect_file(request: InspectRequest):
    """
    Inspects a media file and returns its metadata.
    """
    try:
        metadata = inspect_media(request.file_path)
        return metadata
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MediaInspectionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
