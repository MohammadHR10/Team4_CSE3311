# ================================================================================
# CLUB HOUSE MANAGEMENT SYSTEM - MAIN APPLICATION
# ================================================================================
# This Flask web application manages student club membership, officer roles,
# and club information for a university club house system.
#
# Key Features:
# - Student registration and management
# - Club creation and management  
# - Officer role assignments with access control
# - Firebase Firestore database integration
# - CSV import/export functionality
# - Role-based authentication (Member, Officer, Advisor)
# ================================================================================

import os
import csv
from io import StringIO
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash, make_response, abort, g, session
)
from dotenv import load_dotenv
from logger import get_logger
from firebase_config import FirebaseDB
from utils.validators import valid_email, normalize_email, validate_name, validate_role
from utils.authz import (
    get_current_role, require_officer, inject_role,
    login_user, logout_user, require_login
)

# Load environment variables from .env file
load_dotenv()
logger = get_logger(__name__)

# Initialize Flask application with security settings
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")  # Secret key for session encryption
app.permanent_session_lifetime = 60 * 60 * 6  # Session timeout: 6 hours
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")  # Security settings

# Initialize Firebase database connection
db = FirebaseDB()

# ---- BEFORE REQUEST HANDLERS ----
# These functions run before each request to set up user context

@app.before_request
def _set_role():
    """Set the current user's role in the global context for each request"""
    from utils.authz import current_user
    g.current_user = current_user()
    g.current_role = inject_role()

@app.context_processor
def inject_template_vars():
    """Inject user role and info into all templates automatically"""
    return {
        "current_role": getattr(g, "current_role", "Member"),
        "current_user": getattr(g, "current_user", None),
    }

@app.template_filter('avatar_color')
def avatar_color_filter(name):
    """Generate a gradient color pair based on name"""
    colors = [
        ('667eea', '764ba2'),
        ('f093fb', 'f5576c'),
        ('4facfe', '00f2fe'),
        ('43e97b', '38f9d7'),
        ('fa709a', 'fee140'),
        ('30cfd0', '330867'),
        ('a8edea', 'fed6e3'),
        ('ff9a9e', 'fecfef'),
    ]
    idx = len(name or '') % len(colors)
    return f"#{colors[idx][0]}, #{colors[idx][1]}"

# ================================================================================
# AUTHENTICATION ROUTES
# ================================================================================
# Simple role-based authentication system using access codes

@app.get("/login")
def login_page():
    """Display the login form"""
    nxt = request.args.get("next") or url_for("index")  # Redirect after login
    return render_template("login.html", next=nxt)

@app.post("/login")
def login_submit():
    """Process login form submission and authenticate user"""
    email = (request.form.get("email") or "").strip().lower()
    role  = (request.form.get("role") or "Member").strip().title()
    code  = (request.form.get("code") or "").strip()
    if not email:
        flash("Email is required", "error")
        return redirect(url_for("login_page"))

    if role not in {"Member", "Officer"}:
        role = "Member"

    if role == "Officer":
        required = os.getenv("OFFICER_ACCESS_CODE", "").strip()
        if not required or code != required:
            flash("Invalid officer access code", "error")
            return redirect(url_for("login_page"))

    # optional: pull name if student exists
    try:
        student = db.get_student_by_email(email)
        name = (student or {}).get("name", "")
    except Exception:
        name = ""

    login_user(email=email, role=role, name=name)
    session.permanent = True
    flash(f"Logged in as {role}", "success")
    return redirect(request.form.get("next") or url_for("index"))

@app.post("/logout")
def do_logout():
    logout_user()
    flash("Logged out", "success")
    return redirect(url_for("index"))

# ---------------- WEB ROUTES ----------------
@app.route("/")
def index():
    search_query = request.args.get("search", "")
    try:
        clubs = db.search_clubs(search_query) if search_query else db.get_all_clubs()
        return render_template("index.html", clubs=clubs, search_query=search_query)
    except Exception:
        logger.exception("Error loading index")
        flash("Error loading clubs", "error")
        return render_template("index.html", clubs=[], search_query=search_query)

@app.route("/students")
def students():
    try:
        students = db.get_students_with_memberships()
        clubs = db.get_all_clubs()
        return render_template("students.html", students=students, clubs=clubs)
    except Exception:
        logger.exception("Error loading students")
        flash("Error loading students", "error")
        return redirect(url_for("index"))

@app.route("/clubs/<club_id>/roster")
def club_roster(club_id):
    try:
        club = db.get_club(club_id)
        if not club:
            flash("Club not found", "error")
            return redirect(url_for("index"))

        members = db.get_club_members(club_id)

        # search/filter/sort
        q = (request.args.get("q") or "").strip().lower()
        if q:
            members = [m for m in members if q in (m.get("name","").lower()) or q in (m.get("email","").lower())]

        selected_role = request.args.get("role", "")
        selected_sort = request.args.get("sort", "")

        if selected_role:
            members = [m for m in members if m.get("role") == selected_role]

        if selected_sort == "name":
            members.sort(key=lambda m: (m.get("name") or "").lower())
        elif selected_sort == "join_date":
            members.sort(key=lambda m: m.get("join_date", ""), reverse=True)

        # students available to add
        all_students = db.get_all_students()
        current_ids = {m.get("id") for m in members}
        students = [s for s in all_students if s.get("id") not in current_ids]

        return render_template(
            "roster.html",
            club=club, members=members, students=students,
            selected_role=selected_role, selected_sort=selected_sort, q=q
        )
    except Exception:
        logger.exception("Error loading roster")
        flash("Error loading roster", "error")
        return redirect(url_for("index"))

# Officer-only: CSV export (and club must be verified)
@app.get("/clubs/<club_id>/export.csv")
@require_officer
def export_roster_csv(club_id):
    club = db.get_club(club_id)
    if not club:
        abort(404)
    if not club.get("verified"):
        abort(403)

    members = db.get_club_members(club_id)

    # match screen filters
    q = (request.args.get("q") or "").strip().lower()
    if q:
        members = [m for m in members if q in (m.get("name","").lower()) or q in (m.get("email","").lower())]
    role = request.args.get("role") or ""
    if role:
        members = [m for m in members if m.get("role") == role]
    sort = request.args.get("sort") or ""
    if sort == "name":
        members.sort(key=lambda m: (m.get("name") or "").lower())
    elif sort == "join_date":
        members.sort(key=lambda m: m.get("join_date",""), reverse=True)

    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["student_id", "name", "email", "role", "join_date"])
    for m in members:
        writer.writerow([
            m.get("id",""),
            m.get("name",""),
            m.get("email",""),
            m.get("role",""),
            (m.get("join_date","") or "")[:19],
        ])
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    fname = f"{club.get('name','club').replace(' ','_').lower()}_roster.csv"
    resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp

# Officer-only: verify club
@app.post("/clubs/<club_id>/verify")
@require_officer
def verify_club(club_id):
    club = db.get_club(club_id)
    if not club:
        abort(404)
    db.set_club_verified(club_id, True)
    flash("Club verified.", "success")
    return redirect(url_for("club_roster", club_id=club_id, **request.args.to_dict()))

# ---------------- API - CLUBS ----------------
@app.get("/api/clubs")
def api_get_clubs():
    try:
        search_query = request.args.get("search", "")
        clubs = db.search_clubs(search_query) if search_query else db.get_all_clubs()
        return jsonify({"success": True, "clubs": clubs})
    except Exception as e:
        logger.exception("Error getting clubs")
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/api/clubs")
@require_officer
def api_create_club():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        desc = (data.get("description") or "").strip()
        if not name or not desc:
            return jsonify({"success": False, "error": "Name and description required"}), 400
        if any(((c.get("name") or "").lower() == name.lower()) for c in db.get_all_clubs()):
            return jsonify({"success": False, "error": "Club name already exists"}), 400

        club_id = db.create_club({"name": name, "description": desc})
        return jsonify({"success": True, "club_id": club_id, "message": "Club created"}), 201
    except Exception as e:
        logger.exception("Error creating club")
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/clubs/<club_id>")
def api_get_club(club_id):
    try:
        club = db.get_club(club_id)
        if not club:
            return jsonify({"success": False, "error": "Club not found"}), 404
        return jsonify({"success": True, "club": club})
    except Exception as e:
        logger.exception("Error fetching club")
        return jsonify({"success": False, "error": str(e)}), 500

@app.put("/api/clubs/<club_id>")
@require_officer
def api_update_club(club_id):
    try:
        data = request.get_json() or {}
        new_name = (data.get("name") or "").strip()
        new_desc = (data.get("description") or "").strip()
        if not new_name or not new_desc:
            return jsonify({"success": False, "error": "Name and description required"}), 400
        club = db.get_club(club_id)
        if not club:
            return jsonify({"success": False, "error": "Club not found"}), 404
        if any(c["id"] != club_id and ((c.get("name") or "").lower() == new_name.lower()) for c in db.get_all_clubs()):
            return jsonify({"success": False, "error": "Another club already uses that name"}), 400
        db.update_club(club_id, {"name": new_name, "description": new_desc})
        return jsonify({"success": True, "message": "Club updated"})
    except Exception as e:
        logger.exception("Error updating club")
        return jsonify({"success": False, "error": str(e)}), 500

@app.delete("/api/clubs/<club_id>")
@require_officer
def api_delete_club(club_id):
    try:
        club = db.get_club(club_id)
        if not club:
            return jsonify({'success': False, 'error': 'Club not found'}), 404
        db.delete_club(club_id)
        return jsonify({'success': True, 'message': 'Club deleted successfully'}), 200
    except ValueError as ve:
        logger.warning("Delete club validation: %s", ve)
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception:
        logger.exception("Error deleting club")
        return jsonify({'success': False, 'error': 'Server error'}), 500
    
    
# ---------------- Verification (Two-step) ----------------
@app.post("/api/clubs/<club_id>/verify/request")
def api_request_verify_club(club_id):
    try:
        role = session.get("role", "Member")
        if role != "Officer":
            return jsonify({"success": False, "error": "Forbidden"}), 403

        user_email = session.get("user_email") or os.getenv("DEMO_OFFICER_EMAIL", "officer@example.com")
        note = (request.get_json() or {}).get("note") or ""
        club = db.get_club(club_id)
        if not club:
            return jsonify({"success": False, "error": "Club not found"}), 404
        if club.get("verified"):
            return jsonify({"success": True, "message": "Already verified"})

        db.set_verification_request(club_id, user_email, note)
        return jsonify({"success": True, "message": "Verification requested"})
    except Exception as e:
        logger.exception("Error requesting verification")
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/api/clubs/<club_id>/verify/confirm")
def api_confirm_verify_club(club_id):
    try:
        role = session.get("role", "Member")
        if role != "Officer":
            return jsonify({"success": False, "error": "Forbidden"}), 403

        club = db.get_club(club_id)
        if not club:
            return jsonify({"success": False, "error": "Club not found"}), 404
        if club.get("verified"):
            return jsonify({"success": True, "message": "Already verified"})

        data = request.get_json() or {}
        advisor_code = (data.get("advisor_code") or "").strip()
        expected = (os.getenv("ADVISOR_CODE") or "").strip()

        # Path A: Advisor code (bypasses two-officer rule)
        if advisor_code and expected and advisor_code == expected:
            confirmer = session.get("user_email") or "advisor@local"
            db.confirm_verification(club_id, confirmer)
            return jsonify({"success": True, "message": "Club verified via advisor code"})

        # Path B: second officer must be different from requester
        confirmer = session.get("user_email") or os.getenv("DEMO_OFFICER_EMAIL", "officer@example.com")
        db.confirm_verification(club_id, confirmer)
        return jsonify({"success": True, "message": "Club verified"})
    except ValueError as ve:
        logger.warning("Verify confirm validation: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error confirming verification")
        return jsonify({"success": False, "error": "Server error"}), 500


# ---------------- API - MEMBERSHIPS ----------------
@app.get('/api/clubs/<club_id>/members')
def api_get_club_members(club_id):
    try:
        role = request.args.get('role', '')
        sort = request.args.get('sort', '')
        q = (request.args.get('q') or '').strip().lower()

        members = db.get_club_members(club_id)
        if q:
            members = [m for m in members if q in (m.get('name','').lower()) or q in (m.get('email','').lower())]
        if role:
            members = [m for m in members if m.get('role') == role]
        if sort == 'name':
            members.sort(key=lambda m: (m.get('name') or '').lower())
        elif sort == 'join_date':
            members.sort(key=lambda m: m.get('join_date', ''), reverse=True)
        return jsonify({'success': True, 'members': members})
    except Exception as e:
        logger.exception("Error getting club members")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.post("/api/clubs/<club_id>/members")
@require_officer
def api_add_member(club_id):
    try:
        data = request.get_json() or {}
        student_id = data.get("student_id")
        role = data.get("role")
        if not student_id:
            return jsonify({"success": False, "error": "Student ID is required"}), 400
        if not role:
            return jsonify({"success": False, "error": "Role is required"}), 400
        if not validate_role(role):
            return jsonify({"success": False, "error": "Invalid role"}), 400

        club = db.get_club(club_id)
        if not club:
            return jsonify({"success": False, "error": "Club not found"}), 404
        student = db.get_student(student_id)
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404

        membership_id = db.add_member_to_club(club_id, student_id, role)
        return jsonify({"success": True, "membership_id": membership_id, "message": "Member added"}), 201
    except ValueError as ve:
        logger.warning("Validation error adding member: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error adding member")
        return jsonify({"success": False, "error": str(e)}), 500

@app.put("/api/clubs/<club_id>/members/<student_id>")
@require_officer
def api_update_member_role(club_id, student_id):
    try:
        data = request.get_json() or {}
        new_role = (data.get("role") or "").strip()
        if not new_role:
            return jsonify({"success": False, "error": "Role is required"}), 400
        if not validate_role(new_role):
            return jsonify({"success": False, "error": "Invalid role"}), 400
        if not db.get_club(club_id):
            return jsonify({"success": False, "error": "Club not found"}), 404
        if not db.get_student(student_id):
            return jsonify({"success": False, "error": "Student not found"}), 404
        db.update_member_role(club_id, student_id, new_role)
        return jsonify({"success": True, "message": "Member role updated"})
    except ValueError as ve:
        logger.warning("Validation error updating role: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error updating role")
        return jsonify({"success": False, "error": str(e)}), 500

@app.delete("/api/clubs/<club_id>/members/<student_id>")
@require_officer
def api_remove_member(club_id, student_id):
    try:
        if not db.get_club(club_id):
            return jsonify({"success": False, "error": "Club not found"}), 404
        members = db.get_club_members(club_id)
        if not any(m.get("id") == student_id for m in members):
            return jsonify({"success": False, "error": "Student is not a member of this club"}), 404
        db.remove_member_from_club(club_id, student_id)
        return jsonify({"success": True, "message": "Member removed"})
    except ValueError as ve:
        logger.warning("Validation error removing member: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.exception("Error removing member")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------- API - STUDENTS ----------------
@app.get("/api/students")
def api_get_students():
    try:
        students = db.get_all_students()
        return jsonify({"success": True, "students": students})
    except Exception as e:
        logger.exception("Error getting students")
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/api/students")
def api_create_student():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        email_raw = (data.get("email") or "").strip()
        if not name or not email_raw:
            return jsonify({"success": False, "error": "Name and email required"}), 400
        if not validate_name(name):
            return jsonify({"success": False, "error": "Invalid name"}), 400
        email = normalize_email(email_raw)
        if not valid_email(email):
            return jsonify({"success": False, "error": "Invalid email format. Please provide a properly formatted email address."}), 400
        if db.get_student_by_email(email):
            return jsonify({"success": False, "error": "already registered"}), 400
        sid = db.create_student({"name": name, "email": email})
        return jsonify({"success": True, "message": "Student created", "student_id": sid}), 201
    except Exception as e:
        logger.exception("Error creating student")
        return jsonify({"success": False, "error": str(e)}), 500

@app.put("/api/students/<student_id>")
def api_update_student(student_id):
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        email_raw = (data.get("email") or "").strip()
        if not name or not email_raw:
            return jsonify({"success": False, "error": "Both name and email required"}), 400
        if not validate_name(name):
            return jsonify({"success": False, "error": "Invalid name"}), 400
        email = normalize_email(email_raw)
        if not valid_email(email):
            return jsonify({"success": False, "error": "Invalid email format. Please provide a properly formatted email address."}), 400
        all_students = [s for s in db.get_all_students() if s.get("id") != student_id]
        if any(((s.get("email") or "").lower() == email.lower()) for s in all_students):
            return jsonify({"success": False, "error": "Email already used"}), 400
        db.update_student(student_id, {"name": name, "email": email})
        return jsonify({"success": True, "message": "Student updated"})
    except Exception as e:
        logger.exception("Error updating student")
        return jsonify({"success": False, "error": str(e)}), 500

@app.delete("/api/students/<student_id>")
def api_delete_student(student_id):
    try:
        student = db.get_student(student_id)
        if not student:
            return jsonify({"success": False, "error": "Student not found"}), 404
        db.delete_student(student_id)
        return jsonify({"success": True, "message": "Student deleted"}), 200
    except ValueError as ve:
        logger.warning("Delete student validation: %s", ve)
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception:
        logger.exception("Error deleting student")
        return jsonify({"success": False, "error": "Server error"}), 500

@app.get('/api/students/check')
def api_check_student_email():
    try:
        email_raw = (request.args.get('email') or '').strip()
        exclude_id = request.args.get('exclude_id')
        if not email_raw:
            return jsonify({'success': False, 'error': 'email required'}), 400
        email = normalize_email(email_raw)
        student = db.get_student_by_email(email)
        exists = bool(student and (not exclude_id or student.get('id') != exclude_id))
        return jsonify({'success': True, 'exists': exists})
    except Exception:
        logger.exception("Error checking student email")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# ---------------- Students with Membership Filters ----------------
@app.get('/api/students/memberships')
def api_get_students_with_memberships():
    try:
        club_ids_raw = request.args.get('club_id', '').strip()
        role = (request.args.get('role') or '').strip()
        club_ids = None
        if club_ids_raw:
            club_ids = [cid.strip() for cid in club_ids_raw.split(',') if cid.strip()]
        students = db.get_students_with_memberships(club_ids=club_ids, role=role if role else None)
        return jsonify({'success': True, 'students': students})
    except Exception:
        logger.exception("Error getting students with memberships")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# ------------- Errors -------------
@app.errorhandler(403)
def forbidden(e):
    return ("Forbidden", 403)

@app.errorhandler(404)
def not_found(e):
    try:
        return render_template("404.html"), 404
    except Exception:
        return "404 Not Found", 404

@app.errorhandler(500)
def internal_error(e):
    try:
        return render_template("500.html"), 500
    except Exception:
        return "500 Internal Server Error", 500

# ================================================================================
# INVITE LINK SYSTEM
# ================================================================================
# Additional functionality for invite-based registration

import secrets
import hashlib
from datetime import datetime, timedelta

# Store active invite tokens (in production, use Redis or database)
ACTIVE_INVITES = {}

@app.route("/invite/generate", methods=["POST"])
@require_officer
def generate_invite():
    """Generate invite links for officer or member roles"""
    role = request.form.get("role", "Member").strip()
    expires_days = int(request.form.get("expires_days", 7))
    
    if role not in ["Officer", "Member"]:
        flash("Invalid role specified", "error")
        return redirect(url_for("index"))
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=expires_days)
    
    # Store invite info
    ACTIVE_INVITES[token] = {
        "role": role,
        "created_by": g.current_user.get("email") if g.current_user else "admin",
        "created_at": datetime.now(),
        "expires_at": expires_at,
        "used": False
    }
    
    # Generate invite URL
    invite_url = request.host_url + f"invite/join/{token}"
    
    flash(f"Invite link generated for {role} role: {invite_url}", "success")
    logger.info(f"Invite generated by {g.current_user.get('email', 'unknown')} for role {role}")
    
    return redirect(url_for("index"))

@app.route("/invite/join/<token>")
def join_via_invite(token):
    """Join using an invite link"""
    invite = ACTIVE_INVITES.get(token)
    
    if not invite:
        flash("Invalid or expired invite link", "error")
        return redirect(url_for("login_page"))
    
    if invite["used"]:
        flash("This invite link has already been used", "error")
        return redirect(url_for("login_page"))
    
    if datetime.now() > invite["expires_at"]:
        flash("This invite link has expired", "error")
        return redirect(url_for("login_page"))
    
    # Pass invite info to registration
    return render_template("invite_register.html", 
                         invite=invite, 
                         token=token,
                         role=invite["role"])

@app.route("/invite/register", methods=["POST"])
def register_via_invite():
    """Complete registration via invite link"""
    token = request.form.get("token", "").strip()
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    
    invite = ACTIVE_INVITES.get(token)
    
    if not invite or invite["used"] or datetime.now() > invite["expires_at"]:
        flash("Invalid or expired invite link", "error")
        return redirect(url_for("login_page"))
    
    if not valid_email(email):
        flash("Please enter a valid email address", "error")
        return render_template("invite_register.html", 
                             invite=invite, 
                             token=token,
                             role=invite["role"])
    
    if not validate_name(name):
        flash("Please enter a valid name", "error")
        return render_template("invite_register.html", 
                             invite=invite, 
                             token=token,
                             role=invite["role"])
    
    # Mark invite as used
    invite["used"] = True
    invite["used_by"] = email
    invite["used_at"] = datetime.now()
    
    # Log the user in with the invited role
    login_user(email, invite["role"], name)
    
    flash(f"Welcome! You've been registered as {invite['role']}", "success")
    logger.info(f"User {email} registered via invite as {invite['role']}")
    
    return redirect(url_for("index"))

@app.route("/invite/manage")
@require_officer
def manage_invites():
    """View and manage active invites"""
    # Clean up expired invites
    current_time = datetime.now()
    expired_tokens = [token for token, invite in ACTIVE_INVITES.items() 
                     if invite["expires_at"] < current_time]
    
    for token in expired_tokens:
        del ACTIVE_INVITES[token]
    
    return render_template("manage_invites.html", 
                         invites=ACTIVE_INVITES,
                         base_url=request.host_url)

# ================================================================================
# NOTIFICATION & ANNOUNCEMENT SYSTEM
# ================================================================================
# Club announcements and notifications functionality

@app.route("/api/notifications")
def get_notifications():
    """Get recent notifications for the current user"""
    try:
        # Get recent announcements from all clubs (last 7 days)
        notifications = db.get_recent_announcements(days=7)
        logger.info(f"Fetched {len(notifications)} notifications")
        return jsonify({'success': True, 'notifications': notifications or []})
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({'success': True, 'notifications': []})

@app.route("/api/notifications/mark-read", methods=["POST"])
def mark_notification_read():
    """Mark a notification as read"""
    try:
        announcement_id = request.json.get('announcement_id', '').strip()
        user_email = g.current_user.get('email') if g.current_user else None
        
        if not announcement_id or not user_email:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        db.mark_announcement_read(announcement_id, user_email)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/clubs/<club_id>/announcements")
def club_announcements(club_id):
    """View announcements for a specific club"""
    try:
        club = db.get_club_by_id(club_id)
        if not club:
            flash("Club not found", "error")
            return redirect(url_for("index"))
        
        announcements = db.get_club_announcements(club_id)
        return render_template("club_announcements.html", 
                             club=club, 
                             announcements=announcements)
    except Exception as e:
        logger.error(f"Error loading club announcements: {e}")
        flash("Error loading announcements", "error")
        return redirect(url_for("index"))

@app.route("/clubs/<club_id>/announcements/new", methods=["GET", "POST"])
@require_officer
def create_announcement(club_id):
    """Create a new announcement for a club"""
    try:
        club = db.get_club_by_id(club_id)
        if not club:
            flash("Club not found", "error")
            return redirect(url_for("index"))
        
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            priority = request.form.get("priority", "normal").strip()
            
            if not title or not content:
                flash("Title and content are required", "error")
                return render_template("create_announcement.html", club=club)
            
            announcement_data = {
                "title": title,
                "content": content,
                "priority": priority,
                "club_id": club_id,
                "club_name": club["name"],
                "created_by": g.current_user.get("email", "unknown"),
                "created_at": datetime.now(),
                "read_by": []
            }
            
            db.create_announcement(announcement_data)
            flash(f"Announcement '{title}' created successfully", "success")
            logger.info(f"Announcement created for club {club_id} by {g.current_user.get('email', 'unknown')}")
            
            return redirect(url_for("club_announcements", club_id=club_id))
        
        return render_template("create_announcement.html", club=club)
    except Exception as e:
        logger.error(f"Error creating announcement: {e}")
        flash("Error creating announcement", "error")
        return redirect(url_for("index"))

@app.route("/api/announcements/<announcement_id>/delete", methods=["DELETE"])
@require_officer
def delete_announcement(announcement_id):
    """Delete an announcement"""
    try:
        db.delete_announcement(announcement_id)
        logger.info(f"Announcement {announcement_id} deleted by {g.current_user.get('email', 'unknown')}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting announcement: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



# ------------- Run -------------
if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "False").strip().lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.getenv("PORT", 5002)))
