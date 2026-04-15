import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import (
    GenerateCopyRequest,
    GenerateCopyResponse,
    GenerateLicenseRequest,
    GenerateLicenseResponse,
    GenerateScriptRequest,
    GenerateScriptResponse,
    RetrieveLicenseRequest,
    RetrieveLicenseResponse,
    VerifyLicenseRequest,
    VerifyLicenseResponse,
)
from app.services import generate_copy_variations, generate_video_script

UPGRADE_URL = "https://fuioherm.gumroad.com/l/copysnap"
DEFAULT_USAGE_STORE_PATH = Path("~/hermes-copy-kit/data/usage_limits.json").expanduser()
DEFAULT_LICENSE_STORE_PATH = Path("~/hermes-copy-kit/data/licenses.json").expanduser()
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



def _license_store_path() -> Path:
    return Path(os.getenv("LICENSE_STORE_PATH", str(DEFAULT_LICENSE_STORE_PATH))).expanduser()



def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()



def _load_json_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)



def _save_json_store(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file)



def _load_usage_store() -> dict[str, dict[str, Any]]:
    return _load_json_store(_usage_store_path())



def _save_usage_store(data: dict[str, dict[str, Any]]) -> None:
    _save_json_store(_usage_store_path(), data)



def _load_license_store() -> dict[str, dict[str, Any]]:
    return _load_json_store(_license_store_path())



def _save_license_store(data: dict[str, dict[str, Any]]) -> None:
    _save_json_store(_license_store_path(), data)



def _normalize_license_key(license_key: str) -> str:
    return license_key.strip().upper()



def _generate_license_value(email: str, source: str, order_id: str) -> str:
    seed = f"{email.lower()}|{source.lower()}|{order_id}|{secrets.token_hex(8)}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    return "COPYSNAP-" + "-".join([digest[0:4], digest[4:8], digest[8:12], digest[12:16]])



def _create_license(email: str, source: str, order_id: str) -> str:
    licenses = _load_license_store()
    email = email.strip().lower()
    source = source.strip()
    order_id = order_id.strip()

    for key, record in licenses.items():
        if record.get("email") == email and record.get("order_id") == order_id:
            return key

    license_key = _normalize_license_key(_generate_license_value(email, source, order_id))
    licenses[license_key] = {
        "email": email,
        "source": source,
        "order_id": order_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_license_store(licenses)
    return license_key



def _verify_license_key(license_key: str) -> bool:
    licenses = _load_license_store()
    return _normalize_license_key(license_key) in licenses



def _retrieve_license(email: str, order_id: Optional[str] = None) -> Optional[str]:
    licenses = _load_license_store()
    email = email.strip().lower()
    order_id = order_id.strip() if order_id else None

    for key, record in licenses.items():
        if record.get("email") != email:
            continue
        if order_id and record.get("order_id") != order_id:
            continue
        return key
    return None



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



def _extract_gumroad_payload(raw_body: bytes) -> dict[str, str]:
    parsed = parse_qs(raw_body.decode("utf-8", errors="ignore"), keep_blank_values=True)
    flat = {key: values[0] for key, values in parsed.items() if values}
    if not flat and raw_body:
        try:
            flat = json.loads(raw_body.decode("utf-8"))
        except Exception:
            flat = {}
    return flat



def _gumroad_email(payload: dict[str, Any]) -> Optional[str]:
    for key in ["email", "purchase_email", "buyer_email"]:
        value = payload.get(key)
        if value:
            return str(value).strip().lower()
    return None



def _gumroad_order_id(payload: dict[str, Any]) -> Optional[str]:
    for key in ["sale_id", "order_id", "purchase_id"]:
        value = payload.get(key)
        if value:
            return str(value).strip()
    return None


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "copysnap"}


@app.post("/generate-license", response_model=GenerateLicenseResponse)
def generate_license(payload: GenerateLicenseRequest) -> GenerateLicenseResponse:
    license_key = _create_license(
        email=payload.email,
        source=payload.source,
        order_id=payload.order_id,
    )
    return GenerateLicenseResponse(license_key=license_key)


@app.post("/retrieve-license", response_model=RetrieveLicenseResponse)
def retrieve_license(payload: RetrieveLicenseRequest) -> RetrieveLicenseResponse:
    license_key = _retrieve_license(payload.email, payload.order_id)
    return RetrieveLicenseResponse(found=bool(license_key), license_key=license_key)


@app.post("/gumroad/webhook", response_model=GenerateLicenseResponse)
async def gumroad_webhook(request: Request) -> GenerateLicenseResponse:
    payload = _extract_gumroad_payload(await request.body())
    email = _gumroad_email(payload)
    order_id = _gumroad_order_id(payload)

    if not email or not order_id:
        raise HTTPException(status_code=400, detail="Missing Gumroad email or sale_id/order_id")

    license_key = _create_license(email=email, source="gumroad", order_id=order_id)
    return GenerateLicenseResponse(license_key=license_key)


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
