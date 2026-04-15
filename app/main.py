import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import (
    GenerateCopyRequest,
    GenerateCopyResponse,
    GenerateScriptRequest,
    GenerateScriptResponse,
    VerifyLicenseRequest,
    VerifyLicenseResponse,
)
from app.services import generate_copy_variations, generate_video_script

UPGRADE_URL = "https://fuioherm.gumroad.com/l/copysnap"
DEFAULT_USAGE_STORE_PATH = Path("~/hermes-copy-kit/data/usage_limits.json").expanduser()
FREE_DAILY_LIMIT = 1

app = FastAPI(title="CopySnap API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _usage_store_path() -> Path:
    return Path(os.getenv("USAGE_STORE_PATH", str(DEFAULT_USAGE_STORE_PATH))).expanduser()


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_usage_store() -> dict[str, dict[str, Any]]:
    path = _usage_store_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _save_usage_store(data: dict[str, dict[str, Any]]) -> None:
    path = _usage_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file)


def _verify_license_key(license_key: str) -> bool:
    return False


def _request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _extract_license_key(request: Request) -> Optional[str]:
    license_key = request.headers.get("x-license-key", "").strip()
    return license_key or None


def _enforce_free_limit(request: Request) -> Optional[JSONResponse]:
    license_key = _extract_license_key(request)
    if license_key and _verify_license_key(license_key):
        return None

    ip_address = _request_ip(request)
    today = _utc_today()
    usage_data = _load_usage_store()
    record = usage_data.get(ip_address, {"count": 0, "last_reset_date": today})

    if record.get("last_reset_date") != today:
        record = {"count": 0, "last_reset_date": today}

    if int(record.get("count", 0)) >= FREE_DAILY_LIMIT:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Free limit reached. Get unlimited access.",
                "upgrade_url": UPGRADE_URL,
            },
        )

    record["count"] = int(record.get("count", 0)) + 1
    record["last_reset_date"] = today
    usage_data[ip_address] = record
    _save_usage_store(usage_data)
    return None


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "copysnap"}


@app.post("/generate-copy", response_model=GenerateCopyResponse)
def generate_copy(payload: GenerateCopyRequest, request: Request) -> Union[GenerateCopyResponse, JSONResponse]:
    rate_limit_response = _enforce_free_limit(request)
    if rate_limit_response is not None:
        return rate_limit_response

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
def generate_script(payload: GenerateScriptRequest, request: Request) -> Union[GenerateScriptResponse, JSONResponse]:
    rate_limit_response = _enforce_free_limit(request)
    if rate_limit_response is not None:
        return rate_limit_response

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


@app.post("/verify-license", response_model=VerifyLicenseResponse)
def verify_license(payload: VerifyLicenseRequest) -> VerifyLicenseResponse:
    return VerifyLicenseResponse(valid=_verify_license_key(payload.license_key))
