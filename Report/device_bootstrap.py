"""Tự lấy một `device` hợp lệ bằng cách để chính matoklive.tv xác minh.

Server chặn token phát bằng cờ `nvfy` ("not verified") gắn với giá trị
`device` nằm trong localStorage của matoklive.tv. Cờ này chỉ được cấp khi
chính trang matoklive.tv chạy Cloudflare Turnstile (invisible):

* sitekey bị khoá theo hostname, nên mint token từ origin khác trả ``ERR:110200``;
* gọi thẳng ``submit-room-verify`` trả ``{"code":200,"data":true}`` nhưng
  không cấp cờ `nvfy` cho device.

Vì vậy cách duy nhất tự động hoá được là mở Chrome headless vào matoklive.tv,
để chính site sinh ``device`` trong localStorage (chỉ tự đặt UUID khi site chưa
sinh), mở trang phòng live cho site tự gửi Turnstile, rồi hỏi lại API bằng đúng
UUID đó. Dùng UUID do site sinh là bắt buộc: chèn một UUID khác thì luồng xác
minh của site không gửi kèm nó và server vẫn trả `nvfy`. UUID tin cậy được lưu
vào ``Report/device.json`` nên các lần chạy sau không phải bootstrap lại.

Module này không cần Playwright/Selenium: chỉ dùng Chrome có sẵn trên máy và
giao thức DevTools (CDP) qua WebSocket tối giản ở dưới.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import time
import urllib.request
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Chrome/Chromium/Edge có sẵn trên máy người dùng (không tải thêm gì).
CHROME_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)


def find_chrome() -> Optional[str]:
    """Trả đường dẫn Chrome/Chromium đầu tiên tìm thấy, hoặc ``None``."""
    override = os.environ.get("MATOK_CHROME")
    if override:
        return override if os.path.exists(override) else None
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    return None


class _WS:
    """WebSocket client tối giản, đủ để nói chuyện CDP (không cần thư viện ngoài)."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        parsed = urlparse(url)
        raw = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout)
        if parsed.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        raw.sendall(request.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = raw.recv(4096)
            if not chunk:
                raise ConnectionError("CDP đóng kết nối khi bắt tay WebSocket")
            buf += chunk
        if b"101" not in buf.split(b"\r\n")[0]:
            raise ConnectionError(f"Bắt tay WebSocket thất bại: {buf[:120]!r}")
        self._sock = raw

    def send(self, text: str) -> None:
        payload = text.encode()
        length = len(payload)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask = os.urandom(4)
        header += mask
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self._sock.sendall(bytes(header) + data)

    def _read(self, size: int) -> bytes:
        out = b""
        while len(out) < size:
            chunk = self._sock.recv(size - len(out))
            if not chunk:
                raise ConnectionError("CDP đóng kết nối")
            out += chunk
        return out

    def recv(self) -> str:
        frames = []
        while True:
            first, second = self._read(2)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            frames.append(self._read(length) if length else b"")
            if first & 0x80:
                return b"".join(frames).decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


class _Chrome:
    """Một Chrome headless tạm thời + một tab điều khiển qua CDP."""

    def __init__(self, chrome: str, timeout: float = 30.0) -> None:
        self.profile = tempfile.mkdtemp(prefix="matok-device-")
        self.port = 0
        self.proc = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--mute-audio",
                "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.ws: Optional[_WS] = None
        self._msg_id = 0
        try:
            self.port = self._wait_port(timeout)
            self.ws = _WS(self._new_tab(), timeout=timeout)
            self.cmd("Page.enable")
            self.cmd("Runtime.enable")
        except Exception:
            self.close()
            raise

    def _wait_port(self, timeout: float) -> int:
        """Chrome ghi cổng debug thật vào ``DevToolsActivePort`` trong profile."""
        marker = os.path.join(self.profile, "DevToolsActivePort")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("Chrome thoát ngay khi khởi động")
            try:
                with open(marker, encoding="utf-8") as handle:
                    port = int(handle.readline().strip())
                if port:
                    return port
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        raise TimeoutError("Chrome không mở cổng DevTools")

    def _new_tab(self) -> str:
        url = f"http://127.0.0.1:{self.port}/json/new?about:blank"
        deadline = time.time() + 20
        while True:
            try:
                request = urllib.request.Request(url, method="PUT")
                with urllib.request.urlopen(request, timeout=10) as resp:
                    info = json.load(resp)
                return info["webSocketDebuggerUrl"]
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(0.3)

    def cmd(self, method: str, timeout: float = 45.0, **params: Any) -> Dict[str, Any]:
        assert self.ws is not None
        self._msg_id += 1
        self.ws.send(json.dumps({"id": self._msg_id, "method": method, "params": params}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.ws._sock.settimeout(max(0.5, deadline - time.time()))
            message = json.loads(self.ws.recv())
            if message.get("id") == self._msg_id:
                return message
        raise TimeoutError(f"CDP không trả lời {method}")

    def js(self, expression: str, timeout: float = 45.0) -> Any:
        """Chạy JS trong tab và trả giá trị (``None`` nếu JS ném lỗi)."""
        result = self.cmd(
            "Runtime.evaluate",
            timeout=timeout,
            expression=expression,
            awaitPromise=True,
            returnByValue=True,
        ).get("result", {})
        if "exceptionDetails" in result:
            return None
        return result.get("result", {}).get("value")

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
            self.ws = None
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


# Bấm nút chặn 18+ nếu trang hiện (matoklive.tv chặn nội dung người lớn).
_CLICK_AGREE = """(()=>{
  const hit=[...document.querySelectorAll('button,a,div,span')].filter(e=>
    e.children.length===0 && /(over 18|18 tu\u1ed5i|t\u00f4i \u0111\u00e3 tr\u00ean 18)/i.test(e.textContent||''));
  if(!hit.length) return 'none';
  hit[0].click();
  return 'clicked';
})()"""


class DeviceBootstrapError(RuntimeError):
    """Không tự lấy được device tin cậy (thiếu Chrome, mạng lỗi, bị chặn...)."""


def bootstrap_device(
    anchor_id: str,
    verify: Callable[[str], bool],
    timeout: float = 120.0,
    chrome: Optional[str] = None,
) -> str:
    """Xin một ``device`` mới được matoklive.tv xác minh và trả UUID đó.

    ``verify(device)`` phải kiểm tra thật: gọi API token và trả ``True`` chỉ
    khi server đã cấp ``unlDefPa`` (tức device đã qua xác minh).

    Cách làm: mở Chrome headless vào matoklive.tv để chính site tự sinh
    ``device``, vào một phòng live cho site chạy Turnstile invisible, rồi hỏi
    lại API bằng UUID đó. Gọi API chen ngang lúc trang còn đang xác minh có
    thể làm server huỷ lượt xác minh, nên chỉ kiểm tra sau khi đóng Chrome.
    """
    path = chrome or find_chrome()
    if not path:
        raise DeviceBootstrapError(
            "Không tìm thấy Chrome/Chromium trên máy. Cài Google Chrome hoặc đặt "
            "MATOK_CHROME=/đường/dẫn/tới/chrome."
        )

    candidate = str(uuid.uuid4())
    browser: Optional[_Chrome] = None
    try:
        browser = _Chrome(path, timeout=min(45.0, timeout))
        # Mở origin để site tự sinh device. Dùng đúng giá trị site sinh (không
        # tự chèn UUID khác): đó là device mà luồng xác minh của site gửi kèm
        # Turnstile, nên mới được server đánh dấu đã xác minh.
        browser.cmd("Page.navigate", url="https://matoklive.tv/")
        time.sleep(5)
        current = browser.js("localStorage.getItem('device')")
        if isinstance(current, str) and len(current) >= 32:
            candidate = current
        else:
            browser.js(f"localStorage.setItem('device', {json.dumps(candidate)})")
        # Trang phòng live mới chạy luồng xác minh của site (Turnstile invisible).
        browser.cmd("Page.navigate", url=f"https://matoklive.tv/room/{anchor_id}")
        # Trang cần ~20s để tải player và gửi xác minh; bấm hộ cửa chặn 18+.
        wait_seconds = max(20.0, min(40.0, timeout))
        waited = 0.0
        while waited < wait_seconds:
            time.sleep(5)
            waited += 5
            browser.js(_CLICK_AGREE)
        current = browser.js("localStorage.getItem('device')")
        if isinstance(current, str) and len(current) >= 32:
            candidate = current
    finally:
        if browser is not None:
            browser.close()

    # Chỉ kiểm tra sau khi đã đóng Chrome để không chen ngang lượt xác minh.
    try:
        if verify(candidate):
            logger.info("Device %s đã được xác minh", candidate)
            return candidate
    except Exception as exc:
        logger.debug("Device %s chưa qua: %s", candidate, exc)

    raise DeviceBootstrapError(
        "Đã thử xác minh qua trình duyệt nhưng server vẫn trả nvfy. Kiểm tra mạng, "
        "thử lại, hoặc xác minh thủ công trên https://matoklive.tv/ rồi đặt "
        "MATOK_DEVICE."
    )
