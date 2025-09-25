from fastapi import FastAPI, HTTPException
from .models import VideoProcessingRequest, VideoProcessingResult
from .processor import process_video, VideoProcessingError

app = FastAPI()

@app.post("/process", response_model=VideoProcessingResult)
async def process_video_endpoint(request: VideoProcessingRequest):
    """
    Processes a video by splitting, chunking, and/or compressing it.
    """
    try:
        result = process_video(
            video_file_path=request.video_file_path,
            output_directory=request.output_directory,
            split_timestamps=request.split_timestamps,
            chunk_duration=request.chunk_duration,
            compress_resolution=request.compress_resolution,
            compress_first=request.compress_first
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except VideoProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
