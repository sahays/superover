from fastapi import FastAPI, HTTPException
from .models import AudioExtractionRequest, AudioExtractionResult
from .extractor import extract_audio, AudioExtractionError

app = FastAPI()

@app.post("/extract", response_model=AudioExtractionResult)
async def extract_audio_endpoint(request: AudioExtractionRequest):
    """
    Extracts all audio tracks from a video file.
    """
    try:
        result = extract_audio(request.video_file_path, request.output_directory)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AudioExtractionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
