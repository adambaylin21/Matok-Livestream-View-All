# Matok Livestream View All

Ứng dụng web Flask để xem và giám sát **nhiều phòng live của matoklive.tv cùng lúc** trên một màn hình: danh sách phòng bên trái (có tìm kiếm, tick chọn), lưới video HLS bên phải (1–6 cột), phóng to từng phòng, tắt/bật âm thanh hàng loạt.

Backend lấy danh sách phòng và URL phát `.m3u8` từ API của matoklive.tv; frontend phát trực tiếp bằng `hls.js`. Không có dữ liệu demo — nếu không lấy được phòng thật, app hiện danh sách rỗng kèm cảnh báo trong log.

## Tính năng

- **Danh sách đầy đủ:** duyệt hết các trang của endpoint live-list (server hiện có ~200–250 phòng), khử trùng theo `anchorId`; trước đây chỉ lấy trang đầu nên bị thiếu.
- **Tìm kiếm thông minh:** gõ không dấu vẫn khớp có dấu (`boi` → "BốiBối🦜"), không phân biệt hoa/thường, bỏ khoảng trắng thừa, tìm được cả emoji. Lọc đồng thời danh sách bên trái **và** lưới video; `Escape` xoá nhanh từ khoá.
- **Chọn nhiều phòng:** tick trong sidebar để đưa phòng vào lưới; bỏ tick để gỡ (trình phát được giải phóng, không còn tải stream).
- **Layout linh hoạt:** 1/2/3/4/6 cột, nút tự động dàn layout, thu gọn sidebar, chế độ tiêu điểm (phóng to một phòng).
- **Âm thanh:** bật/tắt tiếng cho từng phòng hoặc toàn bộ.
- **Đăng nhập tài khoản (tuỳ chọn):** dùng token matoklive.tv để xem phòng yêu cầu đăng nhập; token chỉ giữ trong bộ nhớ tiến trình, không ghi ra đĩa. Có nút đăng xuất về chế độ khách.

## Yêu cầu

- Python 3.10+ (đã kiểm thử với 3.15)
- Kết nối Internet tới `sw.fnccdn.com` và CDN phát video

## Cài đặt

```bash
python -m venv .venv

# Windows (Git Bash / PowerShell)
.venv/Scripts/python.exe -m pip install -r requirements.txt

# macOS / Linux
# .venv/bin/python -m pip install -r requirements.txt
```

Nếu venv không có sẵn `pip` (tạo bằng `--without-pip` hoặc bằng `uv`), dùng:

```bash
uv venv .venv && uv pip install --python .venv/Scripts/python.exe -r requirements.txt
# hoặc: python -m ensurepip --upgrade
```

## Chạy

```bash
# Cách 1: chạy trực tiếp (mặc định http://127.0.0.1:5000, debug=True)
.venv/Scripts/python.exe app.py

# Cách 2: qua Flask CLI, đổi cổng tuỳ ý
.venv/Scripts/python.exe -m flask --app app run --port 5055

# Chạy nền, ghi log (dùng khi thử nghiệm lâu)
nohup .venv/Scripts/python.exe -m flask --app app run --port 5055 > .server.log 2>&1 &
```

Mở `http://127.0.0.1:5000` (hoặc cổng bạn chọn). App chỉ lắng nghe trên localhost nên không lộ ra mạng ngoài.

> Khi sửa `UI/code.html` hay `Report/report.py`, cần **khởi động lại server** nếu chạy bằng Flask CLI không có `--reload` (template được render từ đĩa mỗi request, nhưng module Python thì đã nạp).

## Cấu hình thiết bị (`device`)

Server matoklive.tv chỉ cấp token phát cho `device` UUID đã được xác minh. Thứ tự ưu tiên:

1. Biến môi trường `MATOK_DEVICE` — UUID dạng `8-4-4-4-12`
2. File `Report/device.json` — nội dung `{"device": "<uuid>"}` (đã nằm trong `.gitignore`)
3. Hằng số `DEFAULT_DEVICE` trong `Report/report.py`

Lấy UUID của riêng bạn: mở https://matoklive.tv/ trên trình duyệt, vào một phòng live đến khi phát được (vượt captcha), rồi chạy trong Console:

```js
localStorage.getItem("device")
```

### Khi gặp lỗi `nvfy`

`nvfy` (*not verified*) là server từ chối cấp token phát cho cặp (device, phiên đăng nhập) chưa xác minh. Biểu hiện trong app: khung phòng báo "Thiết bị chưa xác minh…" và `/api/m3u8/<id>` trả **409**.

Đây là chính sách phía server, không phải lỗi code. Cách xử lý:

- Xác minh lại thiết bị trên trình duyệt như trên rồi cập nhật `MATOK_DEVICE`;
- Hoặc đăng xuất để dùng phiên khách (nút đăng xuất trên header);
- Đôi khi cờ này xuất hiện tạm thời và tự hết sau vài phút;
- Không mở song song tab matoklive.tv trên cùng device — server coi là trùng phiên.

## API

| Method | Endpoint | Mô tả |
| --- | --- | --- |
| `GET` | `/` | Giao diện chính, render danh sách phòng live |
| `GET` | `/api/rooms` | JSON danh sách phòng: `{ok, rooms:[{anchor_id, name, cover, viewers, game}]}` |
| `GET` | `/api/m3u8/<anchor_id>` | Lấy URL phát theo yêu cầu. `200` thành công; `409` thiết bị chưa xác minh (`device_untrusted` + `hint`); `422` phòng lỗi; `502` lỗi dịch vụ |
| `POST` | `/api/login` | Body JSON `{username, password}`. `200` kèm trạng thái phiên; `400` thiếu dữ liệu; `401` sai tài khoản / server từ chối |
| `POST` | `/api/logout` | Xoá token tài khoản khỏi bộ nhớ, quay về phiên khách |
| `GET` | `/api/session` | Trạng thái đăng nhập hiện tại để UI dựng lại nút trên header |

URL phát được lấy **theo yêu cầu** cho từng phòng khi bạn tick chọn, không gọi hàng loạt lúc tải trang — tránh bị rate-limit.

## Cấu trúc dự án

```
app.py                 # Flask app + các route
requirements.txt       # flask, requests, pywasm
Report/
  report.py            # Toàn bộ logic: lấy token, danh sách phòng, m3u8, đăng nhập
  api_sign.wasm        # Wasm tính header `sign` (trích từ JS của matoklive.tv)
  device.json          # (tuỳ chọn, không commit) UUID thiết bị
UI/
  code.html            # Toàn bộ giao diện + JS (HLS, tìm kiếm, layout, đăng nhập)
  DESIGN.md            # Quy ước thiết kế: màu, typography, shape
```

## Luồng lấy link phát

1. `GET auth-service/oauth/getToken` → guest JWT (hoặc token tài khoản nếu đã đăng nhập)
2. `GET scrolliv/live/h5/home/get-live-list.json` → danh sách phòng (`anchorId`), duyệt hết các trang
3. `GET zbliv/public/live/h5/get-room-info.json` → domain (`pldm`) + đường dẫn stream (`stn`)
4. `POST zbliv/h5/public/live/get-room-token` → `ptmlt` + `pkey`
5. Ghép `m3u8 = pldm + stn + ptmlt + pkey`

Header `sign` được tính bằng Wasm `api_sign` (`Report/api_sign.wasm`, gọi qua `pywasm`); có hằng số dự phòng nếu Wasm không nạp được.

## Ghi chú & giới hạn

- **Đăng nhập có thể bị server tắt:** endpoint OAuth từng trả `M1120 Feature not yet available` cho mọi tài khoản. Khi đó app vẫn xem được bằng phiên khách; đây là thay đổi phía matoklive.tv, không phải lỗi của app.
- **Mật khẩu không lưu:** mật khẩu chỉ được băm trong bộ nhớ để gửi lên server, không ghi log/đĩa; token mất khi restart tiến trình.
- **`hls.js` và Tailwind nạp từ CDN** (`cdn.jsdelivr.net`, `cdn.tailwindcss.com`), nên giao diện cần Internet. Warning "should not be used in production" của Tailwind CDN là bình thường với app chạy local.
- **Danh sách phòng thay đổi liên tục** theo thời điểm, nên số phòng giữa hai lần tải có thể khác nhau.
- Dự án dùng cho mục đích cá nhân; tôn trọng điều khoản sử dụng của matoklive.tv.
