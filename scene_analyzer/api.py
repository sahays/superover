from fastapi import FastAPI, HTTPException
from .models import SceneAnalysisRequest, SceneAnalysisResult
from .analyzer import analyze_scenes, SceneAnalysisError

app = FastAPI()

@app.post("/analyze", response_model=SceneAnalysisResult)
async def analyze_scenes_endpoint(request: SceneAnalysisRequest):
    """
    Analyzes video scenes from a manifest file using the Gemini API.
    """
    try:
        result = analyze_scenes(request.manifest_file_path)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SceneAnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
