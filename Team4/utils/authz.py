# utils/authz.py
from functools import wraps
from flask import request, session, abort, g

SESSION_KEY = "user"  # session['user'] = {'email': ..., 'role': 'Officer'|'Member', 'name': ...}

# ---------- helpers ----------
def current_user():
    """Return the logged-in user dict or None."""
    return session.get(SESSION_KEY)

def get_current_role():
    """Return role from session; default Member for anonymous viewers."""
    user = current_user()
    role = (user or {}).get("role", "Member")
    # DEV override via ?as=Officer for quick demos only (optional)
    override = request.args.get("as")
    if override in {"Officer", "Member"}:
        role = override
    return role

def inject_role():
    g.current_user = current_user()
    g.current_role = get_current_role()
    return g.current_role

def require_login(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user():
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper

def require_officer(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "Officer":
            abort(403)
        return view_func(*args, **kwargs)
    return wrapper

def login_user(email: str, role: str, name: str | None = None):
    session[SESSION_KEY] = {"email": email.strip().lower(), "role": role, "name": name or ""}

def logout_user():
    session.pop(SESSION_KEY, None)
