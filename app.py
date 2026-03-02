from datetime import datetime
from functools import wraps
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tournament.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="USER")
    is_approved = db.Column(db.Boolean, default=False)

    registrations = db.relationship("MatchRegistration", back_populates="user", cascade="all, delete-orphan")


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="DRAFT")

    registrations = db.relationship("MatchRegistration", back_populates="match", cascade="all, delete-orphan")


class MatchRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="registrations")
    match = db.relationship("Match", back_populates="registrations")

    __table_args__ = (db.UniqueConstraint("user_id", "match_id", name="uq_user_match"),)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("Vui lòng đăng nhập trước.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "ADMIN":
            flash("Bạn không có quyền truy cập khu vực quản trị.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped




@app.get("/health")
def health_check():
    return {"status": "ok"}, 200


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Tên đăng nhập và mật khẩu là bắt buộc.", "danger")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Tên đăng nhập đã tồn tại.", "danger")
            return render_template("register.html")

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="USER",
            is_approved=False,
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Đăng ký thành công. Chờ quản trị viên phê duyệt tài khoản.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Thông tin đăng nhập không chính xác.", "danger")
            return render_template("login.html")

        if not user.is_approved:
            flash("Tài khoản của bạn chưa được phê duyệt.", "warning")
            return render_template("login.html")

        session["user_id"] = user.id
        session["role"] = user.role
        session["username"] = user.username
        flash("Đăng nhập thành công.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "ADMIN":
        pending_users = User.query.filter_by(role="USER", is_approved=False).all()
        matches = Match.query.order_by(Match.start_time.is_(None), Match.start_time).all()
        return render_template("admin_dashboard.html", pending_users=pending_users, matches=matches)

    matches = Match.query.filter(Match.status.in_(["OPEN", "ONGOING"]))\
        .order_by(Match.start_time.is_(None), Match.start_time).all()
    joined_match_ids = {
        registration.match_id
        for registration in MatchRegistration.query.filter_by(user_id=session["user_id"]).all()
    }
    return render_template("user_dashboard.html", matches=matches, joined_match_ids=joined_match_ids)


@app.post("/admin/users/<int:user_id>/approve")
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "ADMIN":
        flash("Không thể thay đổi tài khoản quản trị.", "warning")
    else:
        user.is_approved = True
        db.session.commit()
        flash(f"Đã phê duyệt tài khoản {user.username}.", "success")
    return redirect(url_for("dashboard"))


@app.post("/admin/matches")
@admin_required
def create_match():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    start_time_raw = request.form.get("start_time", "").strip()

    if not title:
        flash("Tên trận đấu là bắt buộc.", "danger")
        return redirect(url_for("dashboard"))

    start_time = None
    if start_time_raw:
        try:
            start_time = datetime.strptime(start_time_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Thời gian không hợp lệ.", "danger")
            return redirect(url_for("dashboard"))

    match = Match(title=title, description=description, start_time=start_time, status="OPEN")
    db.session.add(match)
    db.session.commit()
    flash("Tạo trận đấu thành công.", "success")
    return redirect(url_for("dashboard"))


@app.post("/admin/matches/<int:match_id>/status")
@admin_required
def update_match_status(match_id):
    match = Match.query.get_or_404(match_id)
    new_status = request.form.get("status", "").strip().upper()

    if new_status not in {"DRAFT", "OPEN", "ONGOING", "FINISHED"}:
        flash("Trạng thái không hợp lệ.", "danger")
        return redirect(url_for("dashboard"))

    match.status = new_status
    db.session.commit()
    flash(f"Đã cập nhật trạng thái trận '{match.title}' thành {new_status}.", "success")
    return redirect(url_for("dashboard"))


@app.post("/matches/<int:match_id>/join")
@login_required
def join_match(match_id):
    if session.get("role") != "USER":
        flash("Chỉ người dùng mới có thể tham gia trận đấu.", "warning")
        return redirect(url_for("dashboard"))

    match = Match.query.get_or_404(match_id)
    if match.status not in {"OPEN", "ONGOING"}:
        flash("Trận đấu hiện không cho phép đăng ký.", "warning")
        return redirect(url_for("dashboard"))

    existing = MatchRegistration.query.filter_by(user_id=session["user_id"], match_id=match_id).first()
    if existing:
        flash("Bạn đã tham gia trận này trước đó.", "info")
        return redirect(url_for("dashboard"))

    db.session.add(MatchRegistration(user_id=session["user_id"], match_id=match_id))
    db.session.commit()
    flash(f"Bạn đã tham gia trận '{match.title}'.", "success")
    return redirect(url_for("dashboard"))


def init_database():
    db.create_all()
    bootstrap_admin()


def bootstrap_admin():
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = User.query.filter_by(username=admin_username).first()
    if admin:
        return

    admin = User(
        username=admin_username,
        password_hash=generate_password_hash(admin_password),
        role="ADMIN",
        is_approved=True,
    )
    db.session.add(admin)
    db.session.commit()


with app.app_context():
    init_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
