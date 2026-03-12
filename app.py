"""
Vercel entrypoint for ARK Usage Dashboard.
This file is self-contained for Vercel deployment.
"""

import json
import logging
import hashlib
import hmac
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ============ ARK Client (simplified for Vercel) ============

SERVICE = "ark"
VERSION = "2024-01-01"
REGION = "cn-north-1"
HOST = "open.volcengineapi.com"
CONTENT_TYPE = "application/json"

AK = os.environ.get("ARK_AK", "")
SK = os.environ.get("ARK_SK", "")

if not AK or not SK:
    logger.warning("ARK_AK or ARK_SK not set! API calls will fail.")


# Use /tmp on Vercel (ephemeral), fallback to home dir locally
def get_data_dir() -> Path:
    if os.environ.get("VERCEL", ""):
        data_dir = Path("/tmp/.ark_usage_data")
    else:
        data_dir = Path.home() / ".ark_usage_data"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data directory: {data_dir}")
    except OSError as e:
        logger.warning(f"Cannot create data directory {data_dir}: {e}")
        data_dir = None

    return data_dir


class ArkUsageClient:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or get_data_dir()
        self.data_file = None
        self.can_write = False

        if self.data_dir:
            self.data_file = self.data_dir / "usage_data.json"
            try:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                test_file = self.data_dir / ".test"
                test_file.touch()
                test_file.unlink()
                self.can_write = True
                logger.info(f"Data file writable: {self.data_file}")
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot write to data directory: {e}")
                self.data_file = None

    def _load_local_data(self) -> Dict[str, Any]:
        if not self.data_file or not self.can_write:
            logger.info("Storage unavailable, returning empty data")
            return {"days": {}, "last_updated": None, "metadata": {}}

        if not self.data_file.exists():
            return {"days": {}, "last_updated": None, "metadata": {}}

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                if "days" not in data:
                    data = {"days": {}, "last_updated": None, "metadata": {}}
                logger.info(
                    f"Loaded {len(data.get('days', {}))} days from local storage"
                )
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading local data: {e}")
            return {"days": {}, "last_updated": None, "metadata": {}}

    def _save_local_data(self, data: Dict[str, Any]):
        if not self.data_file or not self.can_write:
            logger.info("Storage unavailable, skipping save")
            return

        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        temp_file = self.data_dir / ".tmp"
        try:
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            temp_file.replace(self.data_file)
            logger.info(f"Saved {len(data.get('days', {}))} days to local storage")
        except IOError as e:
            logger.warning(f"Error saving local data: {e}")
            pass

    def _merge_data(self, local_data: Dict, new_data: Dict) -> Dict:
        merged = {
            "days": dict(local_data.get("days", {})),
            "last_updated": local_data.get("last_updated"),
            "metadata": {
                **local_data.get("metadata", {}),
                **new_data.get("metadata", {}),
            },
        }
        for date, day_data in new_data.get("days", {}).items():
            merged["days"][date] = day_data
        return merged

    def _norm_query(self, params: Dict) -> str:
        query = ""
        for key in sorted(params.keys()):
            if isinstance(params[key], list):
                for k in params[key]:
                    query += quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
            else:
                query += (
                    quote(key, safe="-_.~")
                    + "="
                    + quote(params[key], safe="-_.~")
                    + "&"
                )
        query = query[:-1]
        return query.replace("+", "%20")

    def _hmac_sha256(self, key: bytes, content: str) -> bytes:
        return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

    def _hash_sha256(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _make_request(
        self,
        method: str,
        date: datetime,
        query: Dict,
        header: Dict,
        action: str,
        body: str,
    ) -> Dict:
        logger.info(f"Making API request: {action}")
        logger.info(f"AK loaded: {AK[:10] if AK else 'EMPTY'}... (length: {len(AK)})")
        logger.info(f"SK loaded: {SK[:10] if SK else 'EMPTY'}... (length: {len(SK)})")

        if not AK or not SK:
            logger.error("AK or SK is empty! Cannot make API request.")
            raise Exception("ARK_AK or ARK_SK environment variable is not set")

        credential = {
            "access_key_id": AK,
            "secret_access_key": SK,
            "service": SERVICE,
            "region": REGION,
        }

        request_param = {
            "body": body if body else "",
            "host": HOST,
            "path": "/",
            "method": method,
            "content_type": CONTENT_TYPE,
            "date": date,
            "query": {"Action": action, "Version": VERSION, **query},
        }

        x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
        short_x_date = x_date[:8]
        x_content_sha256 = self._hash_sha256(request_param["body"])

        sign_result = {
            "Host": request_param["host"],
            "X-Content-Sha256": x_content_sha256,
            "X-Date": x_date,
            "Content-Type": request_param["content_type"],
        }

        signed_headers_str = ";".join(
            ["content-type", "host", "x-content-sha256", "x-date"]
        )

        canonical_request_str = "\n".join(
            [
                request_param["method"].upper(),
                request_param["path"],
                self._norm_query(request_param["query"]),
                "\n".join(
                    [
                        "content-type:" + request_param["content_type"],
                        "host:" + request_param["host"],
                        "x-content-sha256:" + x_content_sha256,
                        "x-date:" + x_date,
                    ]
                ),
                "",
                signed_headers_str,
                x_content_sha256,
            ]
        )

        hashed_canonical_request = self._hash_sha256(canonical_request_str)
        credential_scope = "/".join(
            [short_x_date, credential["region"], credential["service"], "request"]
        )
        string_to_sign = "\n".join(
            ["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request]
        )

        k_date = self._hmac_sha256(
            credential["secret_access_key"].encode("utf-8"), short_x_date
        )
        k_region = self._hmac_sha256(k_date, credential["region"])
        k_service = self._hmac_sha256(k_region, credential["service"])
        k_signing = self._hmac_sha256(k_service, "request")
        signature = self._hmac_sha256(k_signing, string_to_sign).hex()

        sign_result["Authorization"] = (
            "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
                credential["access_key_id"] + "/" + credential_scope,
                signed_headers_str,
                signature,
            )
        )

        header = {**header, **sign_result}

        r = requests.request(
            method=method,
            url="https://{}{}".format(request_param["host"], request_param["path"]),
            headers=header,
            params=request_param["query"],
            data=request_param["body"],
        )
        logger.info(f"API response status: {r.status_code}")
        logger.info(f"API response body: {r.text[:500]}")
        return r.json()

    def fetch_usage(
        self,
        start_date: str,
        end_date: str,
        billing_status: str = "free_for_coding_plan",
    ) -> Dict:
        now = datetime.now(timezone.utc)

        body = json.dumps(
            {
                "QueryInterval": "Day",
                "StartTime": start_date,
                "EndTime": end_date,
                "Filters": [{"Key": "BillingStatus", "Values": [billing_status]}],
            }
        )

        headers = {"ServiceName": "ark"}
        return self._make_request("POST", now, {}, headers, "GetInferenceUsage", body)

    def fetch_and_merge(
        self,
        start_date: str,
        end_date: str,
        billing_status: str = "free_for_coding_plan",
    ) -> Dict:
        logger.info(f"fetch_and_merge: {start_date} to {end_date}")
        local_data = self._load_local_data()
        logger.info(f"Loaded {len(local_data.get('days', {}))} days from local storage")

        api_response = self.fetch_usage(start_date, end_date, billing_status)

        if (
            "ResponseMetadata" in api_response
            and "Error" in api_response["ResponseMetadata"]
        ):
            error = api_response["ResponseMetadata"]["Error"]
            logger.error(f"API Error: {error}")
            raise Exception(
                f"API Error: {error.get('Code', 'Unknown')} - {error.get('Message', 'Unknown')}"
            )

        new_data = self._parse_api_response(api_response, start_date, end_date)
        logger.info(f"Parsed {len(new_data.get('days', {}))} days from API response")

        merged_data = self._merge_data(local_data, new_data)
        logger.info(f"Merged {len(merged_data.get('days', {}))} days total")

        self._save_local_data(merged_data)
        return merged_data

    def _parse_api_response(
        self, response: Dict, start_date: str, end_date: str
    ) -> Dict:
        result = {
            "days": {},
            "metadata": {
                "start_date": start_date,
                "end_date": end_date,
                "parsed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        if "Result" not in response or "Data" not in response["Result"]:
            return result

        data = response["Result"]["Data"]
        if not isinstance(data, list):
            return result

        for item in data:
            if not isinstance(item, list) or len(item) < 9:
                continue
            try:
                date = item[2]
                result["days"][date] = {
                    "date": date,
                    "account_id": item[0],
                    "billing_status": item[1],
                    "input_tokens": int(item[3]) if item[3] else 0,
                    "cache_tokens": int(item[4]) if item[4] else 0,
                    "output_tokens": int(item[5]) if item[5] else 0,
                    "image_count": int(item[6]) if item[6] else 0,
                    "total_tokens": int(item[7]) if item[7] else 0,
                    "requests": int(item[8]) if item[8] else 0,
                    "_source": "api",
                }
            except (ValueError, TypeError, IndexError):
                continue
        return result

    def get_usage_summary(self, days: int = 7) -> Dict:
        data = self._load_local_data()
        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=days)

        total_tokens = total_requests = total_input = total_output = 0
        daily_data = []

        current = start_date
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            day_data = data.get("days", {}).get(date_str)

            if day_data:
                total_tokens += day_data.get("total_tokens", 0)
                total_requests += day_data.get("requests", 0)
                total_input += day_data.get("input_tokens", 0)
                total_output += day_data.get("output_tokens", 0)
                daily_data.append(
                    {
                        "date": date_str,
                        "tokens": day_data.get("total_tokens", 0),
                        "requests": day_data.get("requests", 0),
                    }
                )
            else:
                daily_data.append({"date": date_str, "tokens": 0, "requests": 0})

            current += timedelta(days=1)

        return {
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "daily_breakdown": daily_data,
            "days_analyzed": len(daily_data),
        }


def get_client(data_dir: Optional[Path] = None) -> ArkUsageClient:
    return ArkUsageClient(data_dir=data_dir)


# ============ FastAPI App ============


# Pydantic Models
class UsageSummary(BaseModel):
    total_tokens: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    daily_breakdown: list
    days_analyzed: int


class UsageResponse(BaseModel):
    success: bool
    summary: UsageSummary
    start_date: str
    end_date: str
    days_requested: int
    days_analyzed: int
    fetched_from_api: bool = False


# Create FastAPI app
app = FastAPI(
    title="ARK Usage Dashboard",
    description="Track and visualize ARK API usage",
    version="1.0.0",
)

logger.info("=" * 50)
logger.info("ARK Usage Dashboard Starting")
logger.info(f"VERCEL env: {os.environ.get('VERCEL', 'not set')}")
logger.info(f"ARK_AK set: {bool(AK)} (length: {len(AK)})")
logger.info(f"ARK_SK set: {bool(SK)} (length: {len(SK)})")
logger.info("=" * 50)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

_client: Optional[ArkUsageClient] = None


def get_ark_client() -> ArkUsageClient:
    global _client
    if _client is None:
        _client = get_client()
    return _client


@app.get("/", response_class=HTMLResponse)
async def root():
    static_dir = Path(__file__).parent / "static"
    return FileResponse(str(static_dir / "index.html"))


MAX_API_DAYS = 30


@app.get("/usage", response_model=UsageResponse)
async def get_usage(days: int = Query(default=7, ge=1, le=365)):
    logger.info(f"Usage request: days={days}")
    client = get_ark_client()
    fetched_from_api = False

    try:
        if days <= MAX_API_DAYS:
            logger.info(f"Fetching {days} days from API")
            end_date = datetime.now().date() - timedelta(days=1)
            start_date = end_date - timedelta(days=days - 1)
            client.fetch_and_merge(
                start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            )
            fetched_from_api = True

        summary = client.get_usage_summary(days=days)
        full_data = client._load_local_data()

        stored_days = full_data.get("days", {})
        if stored_days:
            dates = sorted(stored_days.keys())
            data_start = min(dates) if dates else "None"
            data_end = max(dates) if dates else "None"
        else:
            data_start = data_end = "None"

        logger.info(
            f"Returning usage: {summary['total_tokens']} tokens, {summary['days_analyzed']} days"
        )
        return UsageResponse(
            success=True,
            summary=summary,
            start_date=data_start,
            end_date=data_end,
            days_requested=days,
            days_analyzed=summary.get("days_analyzed", 0),
            fetched_from_api=fetched_from_api,
        )
    except Exception as e:
        logger.error(f"Error in /usage: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/export")
async def export_data():
    logger.info("Export requested")
    client = get_ark_client()
    try:
        data = client._load_local_data()
        return JSONResponse({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error in /export: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "framework": "fastapi",
        "env": {
            "ark_ak_set": bool(AK),
            "ark_sk_set": bool(SK),
            "vercel": bool(os.environ.get("VERCEL", "")),
        },
    }
