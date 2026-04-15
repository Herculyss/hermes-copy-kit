from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    GenerateCopyRequest,
    GenerateCopyResponse,
    GenerateScriptRequest,
    GenerateScriptResponse,
)
from app.services import generate_copy_variations, generate_video_script

app = FastAPI(title="CopySnap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "copysnap"}


@app.post("/generate-copy", response_model=GenerateCopyResponse)
def generate_copy(payload: GenerateCopyRequest) -> GenerateCopyResponse:
    try:
        variations = generate_copy_variations(
            product_name=payload.product_name,
            description=payload.description,
            audience=payload.audience,
        )
        return GenerateCopyResponse(
            product_name=payload.product_name,
            variations=variations,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/generate-script", response_model=GenerateScriptResponse)
def generate_script(payload: GenerateScriptRequest) -> GenerateScriptResponse:
    try:
        script = generate_video_script(
            product_name=payload.product_name,
            description=payload.description,
            style=payload.style,
        )
        return GenerateScriptResponse(
            product_name=payload.product_name,
            style=payload.style,
            duration_seconds=30,
            script=script,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
