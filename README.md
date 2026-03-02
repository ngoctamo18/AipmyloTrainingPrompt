# Tournament Login Web Server

Web server đăng nhập với phân quyền:
- **Administrator**: quản lý các tài khoản đăng ký, tạo trận đấu, tổ chức trận đấu.
- **Người dùng**: tham gia trận đấu.

## Chạy local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Mở trình duyệt tại `http://localhost:5000`.

## Tài khoản mặc định

- Username: `admin`
- Password: `admin123`

Bạn có thể đổi bằng biến môi trường:

```bash
export ADMIN_USERNAME=superadmin
export ADMIN_PASSWORD='yourStrongPassword'
export SECRET_KEY='your-random-secret'
```

## Deploy free lên Render

Repo đã có sẵn file `render.yaml` để deploy nhanh.

### Cách 1: Blueprint Deploy (khuyên dùng)
1. Push code lên GitHub repo của bạn.
2. Đăng nhập Render: `https://render.com`.
3. Chọn **New +** → **Blueprint**.
4. Kết nối GitHub repo.
5. Render tự đọc `render.yaml` và tạo web service.
6. Set biến môi trường `ADMIN_PASSWORD` trong dashboard Render.
7. Đợi build xong, mở URL Render để test.

### Cách 2: Tạo Web Service thủ công
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Runtime: Python
- Plan: Free

## Chức năng chính

1. Đăng ký tài khoản người dùng (cần admin phê duyệt).
2. Đăng nhập theo role.
3. Admin duyệt tài khoản chờ duyệt.
4. Admin tạo trận đấu và cập nhật trạng thái (`DRAFT`, `OPEN`, `ONGOING`, `FINISHED`).
5. Người dùng tham gia các trận có trạng thái `OPEN` hoặc `ONGOING`.
6. Health check endpoint: `GET /health`.

> Lưu ý: Free plan thường dùng filesystem tạm thời. SQLite có thể bị reset khi service restart.
