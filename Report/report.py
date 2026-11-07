"""
report.py - Logic layer for extracting `.m3u8` live-stream URLs from matoklive.tv.

Implements the flow described in report.md:

    1. GET auth-service/oauth/getToken           -> guest JWT (access_token)
    2. GET scrolliv/live/h5/home/get-live-list.json -> list of rooms (anchorId)
    3. GET zbliv/public/live/h5/get-room-info.json  -> pldm (domain) + stn (stream path)
    4. POST zbliv/h5/public/live/get-room-token     -> ptmlt + pkey (signature)
    5. m3u8 = pldm + stn + ptmlt + pkey

Bảo mật: endpoint get-room-token yêu cầu header `sign`. `sign` được tính bằng
Wasm `api_sign` (module 34896 trong d8d85f65.js) trên giá trị `h.AI(params)`.
Với get-room-token (POST JSON, không có query params) `h.AI({})` trả về chuỗi
rỗng, nên `sign = api_sign("")` là hằng số `11f569ed792da4e0cff8a393534a5bf2`
(đã kiểm thử khớp với trình duyệt và nhận HTTP 200).
"""

from __future__ import annotations

import base64
import io
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

MERCHANT_ID = "559"
AREA = "VN"
BASE_API = f"https://sw.fnccdn.com/{MERCHANT_ID}/api"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "dev-type": "H5",
    "merchantId": MERCHANT_ID,
    "area": AREA,
    "versionCode": "102",
    "locale-language": "ENU",
}

REQUEST_TIMEOUT = 25
LIVE_LIST_MAX_ATTEMPTS = 3
LIVE_LIST_RETRY_DELAY = 0.5

# getToken cần HTTP Basic của client "web-player" + area + sign; thiếu chúng
# server trả {"errorCode":"500","localizedKey":"EXCEPTION"}.
GET_TOKEN_BASIC_AUTH = "Basic d2ViLXBsYXllcjp3ZWJQbGF5ZXIyMDIyKjk2My4hQCM="

# --------------------------------------------------------------------------- #
# Device UUID — server chỉ cấp token phát khi `device` đã được xác minh
# (`nvfy` = not verified nếu không). Việc xác minh chỉ làm được một lần bằng
# tay: mở https://matoklive.tv/ trên trình duyệt, vượt captcha, rồi lấy
# localStorage["device"]. Không thể tự sinh UUID tin cậy bằng code.
# --------------------------------------------------------------------------- #

# Device đã kiểm chứng và cho ra playlist 200 (dùng khi không cấu hình gì khác).
DEFAULT_DEVICE = "2e8e5784-e34e-4e93-bdc5-6777364f2797"

# File tuỳ chọn: {"device": "<uuid>"}. Ưu tiên hơn DEFAULT_DEVICE.
DEVICE_FILE = Path(__file__).resolve().with_name("device.json")


def _valid_device(value: Any) -> Optional[str]:
    """Chỉ chấp nhận UUID dạng 8-4-4-4-12; loại bỏ timestamp/giá trị rác."""
    if not isinstance(value, str):
        return None
    text = value.strip().strip('"')
    parts = text.split("-")
    if len(parts) != 5:
        return None
    if [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return None
    if any(c not in "0123456789abcdefABCDEF" for p in parts for c in p):
        return None
    return text


def _resolve_device() -> str:
    """Thứ tự ưu tiên: MATOK_DEVICE -> Report/device.json -> DEFAULT_DEVICE."""
    env_device = _valid_device(os.environ.get("MATOK_DEVICE"))
    if env_device:
        return env_device

    try:
        if DEVICE_FILE.exists():
            data = json.loads(DEVICE_FILE.read_text(encoding="utf-8"))
            file_device = _valid_device(data.get("device") if isinstance(data, dict) else data)
            if file_device:
                return file_device
            logger.warning("%s không chứa device UUID hợp lệ; dùng DEFAULT_DEVICE", DEVICE_FILE)
    except Exception as exc:  # file hỏng không được làm chết app
        logger.warning("Không đọc được %s (%s); dùng DEFAULT_DEVICE", DEVICE_FILE, exc)

    return DEFAULT_DEVICE

# --------------------------------------------------------------------------- #
# Sign header — Wasm `api_sign` (module 34896)
# --------------------------------------------------------------------------- #

# Wasm module nhị phân trích xuất từ module 34896 của
# https://matoklive.tv/static/js/d8d85f65.js (chỉ export, không import).
WASM_PATH = Path(__file__).resolve().with_name("api_sign.wasm")

# api_sign("") đã verify khớp với giá trị `sign` trình duyệt gửi cho
# get-room-token. Dùng làm fallback nếu Wasm không load được.
SIGN_CONSTANT = "11f569ed792da4e0cff8a393534a5bf2"

_wasm_runtime_obj: Any = None
_wasm_instance: Any = None


def _wasm_runtime() -> tuple:
    """Lazy-load và trả về (Runtime, instance) đã instantiate (chỉ một lần).

    Trước đây hàm này chỉ trả về instance, khiến `_api_sign` gọi
    `rt.machine`/`rt.invocate` trên sai đối tượng, luôn ném exception và
    lặng lẽ rơi về SIGN_CONSTANT.
    """
    global _wasm_runtime_obj, _wasm_instance
    if _wasm_runtime_obj is not None and _wasm_instance is not None:
        return _wasm_runtime_obj, _wasm_instance
    from pywasm import Runtime, ModuleDesc

    rt = Runtime()
    with open(WASM_PATH, "rb") as f:
        module = ModuleDesc.from_reader(f)
    _wasm_instance = rt.instance(module)
    _wasm_runtime_obj = rt
    return _wasm_runtime_obj, _wasm_instance


def _wasm_string(fn: str, input_str: str) -> str:
    """Gọi một export Wasm nhận (ptr, len) và trả về chuỗi kết quả.

    Cùng cơ chế được site dùng cho `api_sign`, `pwd_hash`, `md5_hex`
    (module 34896: `p(e){ u.reset(); ... u[e](a, n.length) ... }`).
    """
    rt, inst = _wasm_runtime()
    exports = {e.name: e for e in inst.exps}
    mem_addr = exports["memory"].data.data
    mem = rt.machine.store.mems[mem_addr]

    def call(name: str, args: List[int]) -> Any:
        ret = rt.invocate(inst, name, args)
        if isinstance(ret, list):
            return ret[0] if ret else 0
        return ret

    call("reset", [])
    data = input_str.encode("utf-8")
    ptr = call("alloc", [len(data)])
    mem.put(ptr, bytearray(data))
    out_ptr = call(fn, [ptr, len(data)])
    olen = call("out_len", [])
    if not out_ptr or not olen:
        return ""
    return bytes(mem.get(out_ptr, olen)).decode("utf-8", errors="replace")


def _api_sign(input_str: str) -> str:
    """Gọi Wasm `api_sign(input_str)` và trả về chuỗi hex 32 ký tự.

    Nếu Wasm không khả dụng và `input_str` rỗng, trả về hằng số đã verify
    (việc này đủ cho get-room-token vì không có query params).
    """
    try:
        return _wasm_string("api_sign", input_str)
    except Exception:
        if input_str == "":
            return SIGN_CONSTANT
        raise


def _pwd_hash(password: str) -> str:
    """Băm mật khẩu bằng Wasm `pwd_hash` — server chỉ nhận dạng băm này.

    Site gọi `Yt.U(password)` (module 2248 -> 34896 `Uv` = `p("pwd_hash", e)`)
    trước khi gửi `password` lên `auth-service/oauth/token`; gửi mật khẩu thô
    sẽ bị trả `M1012 USERNAME_OR_PWD_ERROR`.
    """
    try:
        hashed = _wasm_string("pwd_hash", password)
    except Exception as exc:
        raise ReportError(f"Không băm được mật khẩu (Wasm pwd_hash): {exc}") from exc
    if not hashed:
        raise ReportError("Wasm pwd_hash trả chuỗi rỗng; không thể đăng nhập.")
    return hashed


def _sign_payload(params: Optional[Dict[str, Any]]) -> str:
    """Triết lại `h.AI` (module 47936, function z) rồi tính `api_sign`.

    `z` sắp xếp key, ghép các giá trị (mảng/đối tượng -> JSON.stringify,
    NaN/null -> chuỗi rỗng). Với get-room-token không có query params =>
    `z({})` = "" => `sign = api_sign("")`.
    """
    if not isinstance(params, dict) or not params:
        plain = ""
    else:
        parts: List[str] = []
        for key in sorted(params.keys()):
            value = params[key]
            if isinstance(value, (list, dict)):
                parts.append(json.dumps(value, ensure_ascii=False))
            elif value is None or (isinstance(value, float) and math.isnan(value)):
                parts.append("")
            else:
                parts.append(str(value))
        plain = "".join(parts)
    return _api_sign(plain)


class ReportError(Exception):
    """Raised when a step in the report flow fails."""


class DeviceNotTrustedError(ReportError):
    """Thiết bị (`device` header) chưa được server xác minh.

    Server trả `{"nvfy": true}` (`nvfy` = "now verify") thay vì token phát.
    Cờ này do server quyết định theo cặp (device, phiên đăng nhập): đăng nhập
    bằng tài khoản chưa qua cửa xác minh vẫn bị `nvfy` dù cùng device đang
    phát được bằng khách. Chỉ khắc phục được bằng một lần xác minh thủ công
    trên trình duyệt (captcha/slider), không tự động hoá được.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.device = _resolve_device()

    @property
    def hint(self) -> str:
        return (
            "Server yêu cầu xác minh (nvfy) cho thiết bị này. Mở https://matoklive.tv/ "
            "trên trình duyệt, vào một phòng live đến khi phát được (vượt captcha), "
            "rồi lấy localStorage[\"device\"] và đặt vào biến môi trường MATOK_DEVICE "
            "(hoặc Report/device.json). Nếu đang đăng nhập bằng tài khoản chưa từng "
            "qua xác minh, hãy đăng xuất để dùng phiên khách. Lưu ý: device UUID chỉ "
            "được tin cậy trong một thời gian và không nên dùng song song với tab "
            "matoklive.tv đang mở."
        )


def _normalize_json(response: requests.Response) -> Dict[str, Any]:
    """Return the payload dict, handling both bare-object and {code, data} shapes."""
    data = response.json()
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    if isinstance(data, dict):
        return data
    raise ReportError(f"Unexpected response shape: {data!r}")


class Report:
    """Encapsulates the matoklive.tv .m3u8 extraction logic."""

    def __init__(self, timeout: int = REQUEST_TIMEOUT) -> None:
        self.session = requests.Session()
        self.session.headers.update(COMMON_HEADERS)
        self.timeout = timeout
        self._guest_token: Optional[str] = None
        self._guest_token_expiry: float = 0.0
        # Phiên đăng nhập (chỉ giữ trong bộ nhớ tiến trình, không ghi ra đĩa).
        self._user_token: Optional[str] = None
        self._user_token_expiry: float = 0.0
        self._user_info: Optional[Dict[str, Any]] = None
        # Phiên tài khoản đã bị server đánh `nvfy` khi phát -> dùng khách để phát.
        self._user_play_blocked: bool = False

    # ------------------------------------------------------------------ #
    # Step 1 — guest JWT
    # ------------------------------------------------------------------ #
    def get_guest_token(self, force_refresh: bool = False) -> str:
        """Lấy guest JWT (access_token). Dùng lại token còn hạn nếu có."""
        now = time.time()
        if not force_refresh and self._guest_token and now < self._guest_token_expiry - 60:
            return self._guest_token

        url = f"{BASE_API}/auth-service/oauth/getToken"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": GET_TOKEN_BASIC_AUTH,
            "area": AREA,
            "merchantId": MERCHANT_ID,
            "dev-type": "H5",
            "versionCode": "102",
            "device": _resolve_device(),
            "sign": _sign_payload(None),
        }
        body = "loginType=11&grant_type=password"

        resp = self.session.post(url, headers=headers, data=body, timeout=self.timeout)
        try:
            resp.raise_for_status()
            payload = _normalize_json(resp)
        except Exception as exc:
            raise ReportError(f"Không lấy được guest token: {exc}") from exc

        token = payload.get("access_token")
        if not token:
            # getToken trả 200 nhưng body lỗi (vd EXCEPTION, hoặc device bị chặn).
            localized = payload.get("localizedKey") or payload.get("errorCode")
            if localized == "USER_LOGIN_OTHER_DEVICE":
                raise DeviceNotTrustedError(
                    "Device đang được dùng bởi một phiên khác (USER_LOGIN_OTHER_DEVICE)."
                )
            raise ReportError(f"getToken không trả access_token: {payload!r}")

        expires_in = int(payload.get("expires_in", 259199) or 259199)
        self._guest_token = token
        self._guest_token_expiry = now + expires_in
        return token

    # ------------------------------------------------------------------ #
    # Đăng nhập bằng tài khoản (auth-service/oauth/token)
    # ------------------------------------------------------------------ #
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Đăng nhập bằng email/tài khoản; giữ token trong bộ nhớ.

        Site dùng `loginType: validate_type3_2(username)` (3 nếu có "@" — email,
        1 nếu là username) và `password: pwd_hash(password)`. Mật khẩu chỉ được
        băm trong bộ nhớ, không bao giờ lưu lại.
        """
        account = (username or "").strip()
        if not account or not password:
            raise ReportError("Cần cả tài khoản và mật khẩu.")

        login_type = 3 if "@" in account else 1
        url = f"{BASE_API}/auth-service/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": GET_TOKEN_BASIC_AUTH,
            "area": AREA,
            "merchantId": MERCHANT_ID,
            "dev-type": "H5",
            "versionCode": "102",
            "device": _resolve_device(),
            "sign": _sign_payload(None),
        }
        body = {
            "loginType": str(login_type),
            "grant_type": "password",
            "username": account,
            "password": _pwd_hash(password),
        }

        resp = self.session.post(url, headers=headers, data=body, timeout=self.timeout)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ReportError(f"Phản hồi đăng nhập không phải JSON: {exc}") from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ReportError(f"Phản hồi đăng nhập không hợp lệ: {payload!r}")

        token = data.get("access_token")
        if not token:
            key = data.get("localizedKey") or data.get("errorCode")
            if key == "USERNAME_OR_PWD_ERROR" or data.get("errorCode") == "M1012":
                raise ReportError("Sai tài khoản hoặc mật khẩu.")
            raise ReportError(
                f"Đăng nhập bị từ chối: {data.get('errorCode') or ''} "
                f"{data.get('localizedValue') or key or ''}".strip()
            )

        expires_in = int(data.get("expires_in", 1295999) or 1295999)
        # Phiên mới có thể đã qua xác minh -> thử lại token tài khoản khi phát.
        self._user_play_blocked = False
        self._user_token = token
        self._user_token_expiry = time.time() + expires_in
        self._user_info = data.get("userData") if isinstance(data.get("userData"), dict) else {}
        self._user_info["username"] = self._user_info.get("username") or data.get("username", "")
        self._user_info["member_id"] = data.get("memberId", "")
        return self.user_status()

    def logout(self) -> None:
        """Xoá phiên đăng nhập khỏi bộ nhớ (quay lại chế độ khách)."""
        self._user_token = None
        self._user_token_expiry = 0.0
        self._user_info = None
        self._user_play_blocked = False

    def user_status(self) -> Dict[str, Any]:
        """Trạng thái đăng nhập cho UI, không lộ token."""
        logged_in = bool(self._user_token) and time.time() < self._user_token_expiry
        info = self._user_info or {}
        return {
            "logged_in": logged_in,
            "username": info.get("username", "") if logged_in else "",
            "nickname": info.get("nickname", "") if logged_in else "",
            "member_id": info.get("member_id", "") if logged_in else "",
        }

    def _auth_token(self) -> str:
        """Token Bearer đang dùng: phiên tài khoản nếu có, ngược lại là khách."""
        if self._user_token and time.time() < self._user_token_expiry - 60:
            return self._user_token
        return self.get_guest_token()

    # ------------------------------------------------------------------ #
    # Step 2 — live room list
    # ------------------------------------------------------------------ #
    def get_live_list(self, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Return the list of live rooms (each record includes anchorId)."""
        return self._live_list_payload(page, page_size).get("records") or []

    def _live_list_payload(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Gọi get-live-list và trả nguyên payload (records, total, pages)."""
        url = f"{BASE_API}/scrolliv/live/h5/home/get-live-list.json"
        params = {
            "dq": AREA,
            "mct": MERCHANT_ID,
            "lang": "ENU",
            "t": int(time.time()),
            "pn": page,
            "ps": page_size,
        }
        last_error: Optional[requests.RequestException] = None
        for attempt in range(LIVE_LIST_MAX_ATTEMPTS):
            # Refresh the timestamp so the CDN does not receive a stale signed/cache key.
            params["t"] = int(time.time())
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                payload = _normalize_json(resp)
                records = payload.get("records", [])
                if not isinstance(records, list):
                    raise ReportError(f"'records' is not a list: {records!r}")
                return payload
            except requests.Timeout as exc:
                last_error = exc
                if attempt + 1 == LIVE_LIST_MAX_ATTEMPTS:
                    raise
                time.sleep(LIVE_LIST_RETRY_DELAY * (2 ** attempt))
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else None
                if status not in (408, 429, 500, 502, 503, 504) or attempt + 1 == LIVE_LIST_MAX_ATTEMPTS:
                    raise
                time.sleep(LIVE_LIST_RETRY_DELAY * (2 ** attempt))
        if last_error:
            raise last_error
        return {}

    def get_all_live_rooms(self, page_size: int = 50, max_pages: int = 20) -> List[Dict[str, Any]]:
        """Lấy toàn bộ phòng live, không chỉ trang đầu.

        Endpoint trả `total`/`pages`; trước đây app chỉ gọi `pn=1&ps=50` nên
        danh sách bị thiếu (server hiện có 216 phòng). Duyệt theo `pages`, gộp
        và khử trùng theo `anchorId` vì danh sách thay đổi giữa các trang.
        """
        seen: set = set()
        merged: List[Dict[str, Any]] = []

        def collect(records: List[Dict[str, Any]]) -> None:
            for record in records:
                anchor_id = str(record.get("anchorId", ""))
                if not anchor_id or anchor_id in seen:
                    continue
                seen.add(anchor_id)
                merged.append(record)

        first = self._live_list_payload(page=1, page_size=page_size)
        collect(first.get("records") or [])
        # Số trang thật do server báo (vd 216 phòng -> pages 5 với ps=50).
        try:
            total_pages = int(first.get("pages") or 1)
        except (TypeError, ValueError):
            total_pages = 1

        total_pages = min(max(total_pages, 1), max_pages)
        for page in range(2, total_pages + 1):
            try:
                collect(self.get_live_list(page=page, page_size=page_size))
            except Exception:
                # Một trang lỗi không nên làm mất toàn bộ danh sách đã có.
                break
        return merged

    def get_active_rooms(self) -> List[Dict[str, str]]:
        """Return a simplified list of rooms: anchor id, name, cover, viewers."""
        rooms: List[Dict[str, str]] = []
        for record in self.get_all_live_rooms():
            rooms.append(
                {
                    "anchor_id": str(record.get("anchorId", "")),
                    "name": record.get("liveName") or record.get("anchorNickname", ""),
                    "cover": record.get("coverUrl", ""),
                    "viewers": str(record.get("onlineCount", 0)),
                    "game": record.get("gameName", ""),
                }
            )
        return rooms

    # ------------------------------------------------------------------ #
    # Step 3 — room info (pldm + stn)
    # ------------------------------------------------------------------ #
    def get_room_info(self, anchor_id: str) -> Dict[str, Any]:
        """Return the room-info payload: pldm, stn, lid, etc."""
        url = f"{BASE_API}/zbliv/public/live/h5/get-room-info.json"
        params = {
            "aid": anchor_id,
            "mctId": MERCHANT_ID,
            "lang": "ENU",
            "spH5": 0,
            "area": AREA,
            "t": int(time.time()),
        }
        headers = {"dev-type": "H5", "versionCode": "102"}
        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return _normalize_json(resp)

    # ------------------------------------------------------------------ #
    # Step 4 — room token (ptmlt + pkey)
    # ------------------------------------------------------------------ #
    def get_room_token(self, anchor_id: str) -> Dict[str, Any]:
        """Return the token payload: unlDefPa.{ptmlt, pkey}, plus buy/pexpt."""
        url = f"{BASE_API}/zbliv/h5/public/live/get-room-token"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._auth_token()}",
            "sign": _sign_payload(None),
            "merchantId": MERCHANT_ID,
            "area": AREA,
            "locale-language": "VIT",
            "device": _resolve_device(),
            "dev-type": "H5",
            "system-version": "1.5.1",
            "time-zone": "GMT+07:00",
            "versionCode": "102",
            # Header trình duyệt mà server yêu cầu để trả dữ liệu token (không chỉ mã 200 rỗng).
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "origin": "https://matoklive.tv",
            "referer": "https://matoklive.tv/",
            "accept": "application/json, text/plain, */*",
            "accept-language": "vi-VN,vi;q=0.9",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "sec-ch-ua": '"Chromium";v="156", "Not.A/Brand";v="8"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        body = {"anchorId": anchor_id}
        last_data: Optional[Dict[str, Any]] = None
        # Phiên tài khoản trên device này bị server đánh `nvfy` (chưa xác minh)
        # nên không cấp được token phát; khi đó lùi về token khách cho riêng
        # việc phát, còn phiên đăng nhập vẫn giữ nguyên cho UI. Ghi nhớ để
        # không thử lại token tài khoản ở mọi phòng (50 phòng = 50 request thừa).
        guest_fallback = self._user_play_blocked
        if guest_fallback:
            headers["Authorization"] = f"Bearer {self.get_guest_token()}"
            headers["sign"] = _sign_payload(None)
        for attempt in range(3):
            resp = self.session.post(url, headers=headers, json=body, timeout=self.timeout)
            if resp.status_code == 401:
                # Token có thể vừa hết hạn; phiên tài khoản hết hạn thì quay về khách.
                if self._user_token and not guest_fallback:
                    self.logout()
                guest_fallback = True
                headers["Authorization"] = f"Bearer {self.get_guest_token(force_refresh=True)}"
                headers["sign"] = _sign_payload(None)
                continue
            resp.raise_for_status()
            data = _normalize_json(resp)
            unl_def_pa = data.get("unlDefPa", {}) or {}
            if unl_def_pa.get("ptmlt") and unl_def_pa.get("pkey"):
                return data

            # `nvfy` (not verified) là quyết định của server dựa trên device,
            # không phải lỗi tạm thời. Có phiên tài khoản thì thử bằng token
            # khách một lần rồi mới bỏ cuộc.
            if data.get("nvfy"):
                if self._user_token and not guest_fallback:
                    guest_fallback = True
                    self._user_play_blocked = True
                    headers["Authorization"] = f"Bearer {self.get_guest_token(force_refresh=True)}"
                    headers["sign"] = _sign_payload(None)
                    continue
                raise DeviceNotTrustedError(
                    "Server từ chối cấp token phát vì thiết bị chưa được xác minh "
                    "(nvfy)."
                )

            error_code = data.get("errorCode")
            if error_code == "USER_LOGIN_OTHER_DEVICE":
                # Cùng device UUID đang bị một phiên khác (vd tab matoklive.tv) giữ.
                # Token mới sẽ đẩy phiên cũ ra, nên làm mới token rồi thử lại
                # thay vì bỏ cuộc ngay.
                if attempt < 2:
                    time.sleep(0.8 * (2 ** attempt))
                    guest_fallback = True
                    headers["Authorization"] = f"Bearer {self.get_guest_token(force_refresh=True)}"
                    headers["sign"] = _sign_payload(None)
                    continue
                raise DeviceNotTrustedError(
                    "Device đang được dùng bởi một phiên khác (USER_LOGIN_OTHER_DEVICE)."
                )
            if error_code:
                # G10003 = phiên tài khoản đã bị đẩy ra bởi thiết bị khác (vd vừa
                # đăng nhập ở tab matoklive.tv). Không phải lỗi vĩnh viễn của
                # device: lùi về token khách để vẫn phát được, giữ phiên cho UI.
                if error_code in ("G10003", "USER_LOGIN_OTHER_DEVICE"):
                    if self._user_token and not guest_fallback:
                        guest_fallback = True
                        self._user_play_blocked = True
                        headers["Authorization"] = f"Bearer {self.get_guest_token(force_refresh=True)}"
                        headers["sign"] = _sign_payload(None)
                        continue
                    if attempt < 2:
                        time.sleep(0.8 * (2 ** attempt))
                        headers["Authorization"] = (
                            f"Bearer {self.get_guest_token(force_refresh=True)}"
                        )
                        continue
                # Lỗi nghiệp vụ có mã rõ ràng (vd thiếu VIP) -> không thử lại.
                raise ReportError(
                    f"get-room-token từ chối: {error_code} "
                    f"({data.get('localizedValue') or data.get('localizedKey') or ''})"
                )

            # HTTP 200 nhưng dữ liệu suy giảm không rõ nguyên nhân -> thử lại.
            last_data = data
            time.sleep(0.8 * (2 ** attempt))
            guest_fallback = True
            headers["Authorization"] = f"Bearer {self.get_guest_token(force_refresh=True)}"
        raise ReportError(
            f"get-room-token trả dữ liệu không đầy đủ (ptmlt/pkey thiếu): {last_data!r}"
        )

    # ------------------------------------------------------------------ #
    # Step 5 — assemble the .m3u8 URL
    # ------------------------------------------------------------------ #
    @staticmethod
    def assemble_m3u8(pldm: str, stn: str, ptmlt: str, pkey: str) -> str:
        """Concatenate pldm + stn + ptmlt + pkey into the final .m3u8 URL."""
        return f"{pldm}{stn}{ptmlt}{pkey}"

    def verify_playlist(self, url: str) -> Dict[str, Any]:
        """Kiểm tra playlist thực sự phát được (HTTP 200 + bắt đầu bằng #EXTM3U).

        Trả về thông tin kiểm chứng; ném ReportError nếu URL chết để UI báo lỗi
        thật thay vì đưa một URL không dùng được cho player.
        """
        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                stream=True,
                headers={"Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*"},
            )
        except requests.RequestException as exc:
            raise ReportError(f"Không tải được playlist: {exc}") from exc

        try:
            if resp.status_code != 200:
                raise ReportError(f"Playlist trả HTTP {resp.status_code}")
            head = next(resp.iter_content(512, decode_unicode=False), b"") or b""
            text = head.decode("utf-8", errors="replace").lstrip("\ufeff").lstrip()
            if not text.startswith("#EXTM3U"):
                raise ReportError("Nội dung trả về không phải playlist HLS (#EXTM3U)")
            return {
                "playlist_ok": True,
                "content_type": resp.headers.get("Content-Type", ""),
            }
        finally:
            resp.close()

    def get_m3u8(self, anchor_id: str) -> Dict[str, Any]:
        """
        Full flow for a single room: info -> token -> assembled URL.
        Returns a dict with the URL plus metadata (expiry, buy flag, raw parts).
        """
        info = self.get_room_info(anchor_id)
        token = self.get_room_token(anchor_id)

        unl_def_pa = token.get("unlDefPa", {}) or {}
        pldm = info.get("pldm", "")
        stn = info.get("stn", "")
        ptmlt = unl_def_pa.get("ptmlt", "")
        pkey = unl_def_pa.get("pkey", "")

        if not (pldm and stn and ptmlt and pkey):
            missing = [
                k for k, v in (("pldm", pldm), ("stn", stn), ("ptmlt", ptmlt), ("pkey", pkey))
                if not v
            ]
            raise ReportError(f"Missing parts for m3u8 assembly: {missing}")

        m3u8 = self.assemble_m3u8(pldm, stn, ptmlt, pkey)
        check = self.verify_playlist(m3u8)

        return {
            "anchor_id": anchor_id,
            "m3u8": m3u8,
            "pldm": pldm,
            "stn": stn,
            "ptmlt": ptmlt,
            "pkey": pkey,
            "buy": token.get("buy", False),
            "pexpt": token.get("pexpt"),
            "lid": info.get("lid"),
            "room_title": info.get("ln", ""),
            **check,
        }
