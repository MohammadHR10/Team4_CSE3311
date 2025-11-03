# ================================================================================
# AUTHORIZATION AND AUTHENTICATION UTILITIES
# ================================================================================
# This module handles user authentication and role-based authorization.
# It provides decorators and helper functions to protect routes and manage
# user sessions with role-based access control.
#
# Roles:
# - Member: Basic access, can view public information
# - Officer: Administrative access, can manage students and clubs
# - Advisor: Special access code for advisors
# ================================================================================

from functools import wraps
from flask import request, session, abort, g

# Session key for storing user information
SESSION_KEY = "user"  # session['user'] = {'email': ..., 'role': 'Officer'|'Member', 'name': ...}

# ================================================================================
# USER SESSION HELPERS
# ================================================================================

def current_user():
    """
    Return the currently logged-in user dictionary or None.
    
    Returns:
        dict or None: User information including email, role, and name
    """
    return session.get(SESSION_KEY)

def get_current_role():
    """
    Return the current user's role with fallback to 'Member' for anonymous users.
    
    Includes development override feature for testing different roles
    via URL parameter ?as=Officer or ?as=Member.
    
    Returns:
        str: User role ('Officer', 'Member', etc.)
    """
    user = current_user()
    role = (user or {}).get("role", "Member")
    
    # DEV override via ?as=Officer for quick demos only (optional)
    # This allows testing different permission levels without logging in/out
    override = request.args.get("as")
    if override in {"Officer", "Member"}:
        role = override
    return role

def inject_role():
    """
    Inject current user and role into Flask's global context.
    
    This function is called before each request to make user information
    available in templates and route handlers.
    
    Returns:
        str: Current user role
    """
    g.current_user = current_user()
    g.current_role = get_current_role()
    return g.current_role

# ================================================================================
# AUTHORIZATION DECORATORS
# ================================================================================

def require_login(view_func):
    """
    Decorator to require user login for accessing a route.
    
    Usage:
        @require_login
        def protected_route():
            return "Only logged in users can see this"
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user():
            abort(403)  # Forbidden - user not logged in
        return view_func(*args, **kwargs)
    return wrapper

def require_officer(view_func):
    """
    Decorator to require Officer role for accessing a route.
    
    Usage:
        @require_officer  
        def admin_route():
            return "Only officers can see this"
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "Officer":
            abort(403)  # Forbidden - user not an officer
        return view_func(*args, **kwargs)
    return wrapper

def login_user(email: str, role: str, name: str | None = None):
    session[SESSION_KEY] = {"email": email.strip().lower(), "role": role, "name": name or ""}

def logout_user():
    session.pop(SESSION_KEY, None)
