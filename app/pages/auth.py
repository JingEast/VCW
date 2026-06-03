"""Authentication page routes (login/register/logout)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required

from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.models import User

bp = Blueprint("pages_auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page — session-based authentication."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("请输入用户名和密码", "warning")
            return render_template("login.html")
        session = get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if not user.is_active:
                    flash("账户已禁用，请联系管理员", "danger")
                    return render_template("login.html")
                login_user(user, remember=True)
                flash(f"欢迎回来，{user.username}！", "success")
                next_page = request.args.get("next")
                return redirect(next_page or url_for("index"))
            flash("用户名或密码错误", "danger")
        finally:
            session.close()
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Registration page — create a new user account."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        if not username or not email or not password:
            flash("请填写所有必填字段", "warning")
            return render_template("register.html")
        if password != password_confirm:
            flash("两次输入的密码不一致", "warning")
            return render_template("register.html")
        if len(password) < 6:
            flash("密码长度至少为 6 位", "warning")
            return render_template("register.html")
        session = get_session()
        try:
            if session.query(User).filter_by(username=username).first():
                flash("用户名已存在", "warning")
                return render_template("register.html")
            if session.query(User).filter_by(email=email).first():
                flash("邮箱已被注册", "warning")
                return render_template("register.html")
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role="viewer",
                is_active=True,
            )
            session.add(user)
            session.commit()
            flash("注册成功，请登录", "success")
            return redirect(url_for("login"))
        finally:
            session.close()
    return render_template("register.html")


@bp.route("/logout")
@login_required
def logout():
    """Logout — clear session."""
    logout_user()
    flash("已成功退出登录", "info")
    return redirect(url_for("index"))
