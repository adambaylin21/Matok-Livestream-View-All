"""
app.py - Flask web UI for the matoklive.tv .m3u8 report.

Interface: folder UI/  (Flask template_folder = "UI")
Logic:     file Report/report.py
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from Report.report import DeviceNotTrustedError, Report, ReportError

app = Flask(__name__, template_folder="UI", static_folder="UI")
report = Report()


@app.route("/")
def index():
    """Render only real rooms returned by matoklive.tv; never substitute demo data."""
    try:
        rooms = report.get_active_rooms()
    except Exception as exc:
        rooms = []
        app.logger.warning("Không tải được danh sách phòng live (%s)", exc)

    # Chỉ lấy danh sách phòng; URL phát được lấy-on-demand khi user chọn phòng
    # (gọi /api/m3u8/<anchor_id>) để tránh gọi lến 50 phòng cùng lúc và bị rate-limit.
    for room in rooms:
        room["m3u8"] = None
        room["m3u8_error"] = None
        room["pexpt"] = None
    return render_template("code.html", rooms=rooms)


@app.route("/api/m3u8/<anchor_id>")
def api_m3u8(anchor_id: str):
    """On-demand .m3u8 for a single room (used by the player/refresh)."""
    try:
        data = report.get_m3u8(anchor_id)
        return jsonify({"ok": True, **data})
    except DeviceNotTrustedError as exc:
        # Thiết bị chưa xác minh: cần can thiệp thủ công, không phải lỗi tạm thời.
        app.logger.warning("Thiết bị chưa xác minh khi lấy m3u8 phòng %s: %s", anchor_id, exc)
        return jsonify(
            {
                "ok": False,
                "code": "device_untrusted",
                "error": str(exc),
                "hint": exc.hint,
            }
        ), 409
    except ReportError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    except Exception as exc:
        app.logger.warning("Lỗi lấy m3u8 phòng %s: %s", anchor_id, exc)
        return jsonify({"ok": False, "error": f"Lỗi dịch vụ: {exc}"}), 502


@app.route("/api/login", methods=["POST"])
def api_login():
    """Đăng nhập tài khoản matoklive.tv; token giữ trong bộ nhớ tiến trình."""
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Cần nhập tài khoản và mật khẩu."}), 400
    try:
        status = report.login(username, password)
        return jsonify({"ok": True, **status})
    except ReportError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401
    except Exception as exc:
        app.logger.warning("Lỗi đăng nhập: %s", exc)
        return jsonify({"ok": False, "error": f"Lỗi dịch vụ: {exc}"}), 502


@app.route("/api/logout", methods=["POST"])
def api_logout():
    """Quay lại chế độ khách (xoá token tài khoản khỏi bộ nhớ)."""
    report.logout()
    return jsonify({"ok": True, **report.user_status()})


@app.route("/api/session")
def api_session():
    """Trạng thái đăng nhập hiện tại để UI dựng lại nút trên header."""
    return jsonify({"ok": True, **report.user_status()})


@app.route("/favicon.ico")
def favicon():
    """Trả về No Content để tránh log 404 khi trình duyệt yêu cầu favicon."""
    return "", 204


@app.route("/api/rooms")
def api_rooms():
    """JSON list of active rooms; return an error instead of fake demo rooms."""
    try:
        rooms = report.get_active_rooms()
        return jsonify({"ok": True, "rooms": rooms})
    except Exception as exc:
        app.logger.warning("Không tải được danh sách phòng live (%s)", exc)
        return jsonify({"ok": False, "rooms": [], "error": f"Lỗi dịch vụ: {exc}"}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
