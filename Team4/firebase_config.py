# ================================================================================
# FIREBASE CONFIGURATION AND DATABASE OPERATIONS
# ================================================================================
# This file handles all Firebase Firestore database operations for the club system.
# It provides a centralized interface for CRUD operations on students, clubs, and memberships.
#
# Collections Structure:
# - students: Student records with contact info and graduation details
# - clubs: Club information, officer assignments, and member counts  
# - memberships: Junction table linking students to clubs with roles
# ================================================================================

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables for Firebase configuration
load_dotenv()

def initialize_firebase():
    """
    Initialize Firebase Admin SDK with service account credentials.
    
    Two authentication methods supported:
    1. JSON string via FIREBASE_SERVICE_ACCOUNT_KEY environment variable
    2. JSON file path via FIREBASE_SERVICE_ACCOUNT_PATH environment variable
    
    Returns:
        firestore.Client: Firestore database client instance
    """
    if not firebase_admin._apps:  # Only initialize once
        # Method 1: Use JSON string from environment variable (recommended for production)
        key_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if key_json:
            service_account_info = json.loads(key_json)
            cred = credentials.Certificate(service_account_info)
        else:
            # Method 2: Use JSON file path (used in development)
            path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
            cred = credentials.Certificate(path)
        
        # Initialize the Firebase app with credentials
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def get_db():
    """Get Firestore database client instance"""
    return initialize_firebase()

class FirebaseDB:
    """
    Main database interface class providing CRUD operations for all collections.
    
    This class encapsulates all database operations and provides a clean API
    for the Flask application to interact with Firestore.
    """
    
    def __init__(self):
        """Initialize database connection"""
        self.db = get_db()

    # ================================================================================
    # CLUB MANAGEMENT OPERATIONS
    # ================================================================================
    def create_club(self, club_data):
        data = dict(club_data)
        data.setdefault("created_at", datetime.now().isoformat())
        data.setdefault("member_count", 0)
        # Iteration-3: add verification flag
        data.setdefault("verified", False)
        doc_ref = self.db.collection("clubs").document()
        doc_ref.set(data)
        return doc_ref.id

    def set_club_verified(self, club_id: str, value: bool = True):
        self.db.collection("clubs").document(club_id).update({"verified": bool(value)})
        return True

    def get_all_clubs(self):
        clubs = []
        docs = self.db.collection("clubs").stream()
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            clubs.append(d)
        return clubs

    def get_club(self, club_id):
        doc = self.db.collection("clubs").document(club_id).get()
        if doc.exists:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None

    def update_club(self, club_id, club_data):
        self.db.collection("clubs").document(club_id).update(club_data)
        return True

    def search_clubs(self, query):
        if not query:
            return self.get_all_clubs()
        q = query.lower()
        clubs = self.get_all_clubs()
        return [
            c for c in clubs
            if q in (c.get("name","").lower()) or q in (c.get("description","").lower())
        ]

    def delete_club(self, club_id):
        # ensure club exists
        club_ref = self.db.collection('clubs').document(club_id)
        if not club_ref.get().exists:
            raise ValueError("Club not found")

        # collect membership docs and affected student ids
        membership_q = self.db.collection('memberships').where('club_id', '==', club_id).stream()
        membership_docs = list(membership_q)
        affected_students = {md.to_dict().get('student_id') for md in membership_docs if md.to_dict().get('student_id')}

        # batch delete membership docs + denorm + club
        batch = self.db.batch()
        for md in membership_docs:
            batch.delete(md.reference)

        club_members_ref = self.db.collection('club_members').document(club_id)
        if club_members_ref.get().exists:
            batch.delete(club_members_ref)

        batch.delete(club_ref)
        batch.commit()

        # remove club key from each student's student_memberships
        for student_id in affected_students:
            if not student_id:
                continue
            sm_ref = self.db.collection('student_memberships').document(student_id)
            sm_snap = sm_ref.get()
            if sm_snap.exists and club_id in (sm_snap.to_dict() or {}):
                sm_ref.update({club_id: firestore.DELETE_FIELD})

        return True

    # -------------------- STUDENTS --------------------
    def create_student(self, student_data):
        data = dict(student_data)
        if "email" in data and data["email"]:
            data["email"] = data["email"].strip().lower()
        data.setdefault("created_at", datetime.now().isoformat())
        doc_ref = self.db.collection("students").document()
        doc_ref.set(data)
        return doc_ref.id

    def get_all_students(self):
        students = []
        docs = self.db.collection("students").stream()
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            students.append(d)
        return students

    def get_student(self, student_id):
        doc = self.db.collection("students").document(student_id).get()
        if doc.exists:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None

    def get_student_by_email(self, email: str):
        if not email:
            return None
        docs = self.db.collection("students").where("email", "==", email).limit(1).stream()
        for d in docs:
            val = d.to_dict()
            val["id"] = d.id
            return val
        return None

    def update_student(self, student_id, data):
        if "email" in data and data["email"]:
            data["email"] = data["email"].strip().lower()
        self.db.collection("students").document(student_id).update(data)
        return True

    def delete_student(self, student_id: str) -> bool:
        student_ref = self.db.collection("students").document(student_id)
        if not student_ref.get().exists:
            raise ValueError("Student not found")

        memberships_q = self.db.collection("memberships").where("student_id", "==", student_id).stream()
        membership_docs = list(memberships_q)

        affected_clubs = set()
        for m in membership_docs:
            md = m.to_dict()
            if md and md.get("club_id"):
                affected_clubs.add(md["club_id"])

        batch = self.db.batch()
        for m in membership_docs:
            batch.delete(m.reference)

        for club_id in affected_clubs:
            club_members_ref = self.db.collection("club_members").document(club_id)
            batch.update(club_members_ref, {student_id: firestore.DELETE_FIELD})

        student_memberships_ref = self.db.collection("student_memberships").document(student_id)
        batch.delete(student_memberships_ref)
        batch.delete(student_ref)
        batch.commit()

        for club_id in affected_clubs:
            try:
                self.update_club_member_count(club_id)
            except Exception:
                pass
        return True

    # -------------------- MEMBERSHIPS --------------------
    def add_member_to_club(self, club_id, student_id, role="Member"):
        # duplicate checks
        existing_check = self.db.collection("memberships") \
            .where("club_id", "==", club_id) \
            .where("student_id", "==", student_id) \
            .limit(1).get()
        if any(True for _ in existing_check):
            raise ValueError("Student is already a member of this club")

        club_members_ref = self.db.collection("club_members").document(club_id)
        cm_snap = club_members_ref.get()
        if cm_snap.exists and student_id in (cm_snap.to_dict() or {}):
            raise ValueError("Student is already a member of this club")

        membership_ref = self.db.collection("memberships").document()
        real_join = datetime.now().isoformat()
        membership_data = {"club_id": club_id, "student_id": student_id, "role": role, "join_date": real_join}
        entry = {"membership_id": membership_ref.id, "role": role, "join_date": real_join}

        batch = self.db.batch()
        batch.set(membership_ref, membership_data)

        if cm_snap.exists:
            batch.update(club_members_ref, {student_id: entry})
        else:
            batch.set(club_members_ref, {student_id: entry})

        sm_ref = self.db.collection("student_memberships").document(student_id)
        batch.set(sm_ref, {club_id: entry}, merge=True)

        club_ref = self.db.collection("clubs").document(club_id)
        club_snap = club_ref.get()
        current_count = 0
        if club_snap.exists:
            current_count = club_snap.to_dict().get("member_count", 0) or 0
        batch.update(club_ref, {"member_count": current_count + 1})

        batch.commit()
        return membership_ref.id

    def remove_member_from_club(self, club_id, student_id):
        transaction = self.db.transaction()

        @firestore.transactional
        def txn_remove(transaction):
            q = self.db.collection("memberships").where("club_id", "==", club_id).where("student_id", "==", student_id).limit(1)
            docs = list(q.get(transaction=transaction))
            if not docs:
                raise ValueError("Membership not found")
            for d in docs:
                transaction.delete(d.reference)

            club_members_ref = self.db.collection("club_members").document(club_id)
            cm_snap = club_members_ref.get(transaction=transaction)
            if cm_snap.exists:
                transaction.update(club_members_ref, {student_id: firestore.DELETE_FIELD})

            sm_ref = self.db.collection("student_memberships").document(student_id)
            sm_snap = sm_ref.get(transaction=transaction)
            if sm_snap.exists:
                transaction.update(sm_ref, {club_id: firestore.DELETE_FIELD})

            club_ref = self.db.collection("clubs").document(club_id)
            club_snap = club_ref.get(transaction=transaction)
            current_count = 0
            if club_snap.exists:
                current_count = club_snap.to_dict().get("member_count", 0) or 0
            new_count = max(0, current_count - 1)
            transaction.update(club_ref, {"member_count": new_count})

        txn_remove(transaction)
        return True

    def get_club_members(self, club_id):
        club_members_doc = self.db.collection('club_members').document(club_id).get()
        if not club_members_doc.exists:
            return []
        cm = club_members_doc.to_dict() or {}
        members = []
        for student_id, member_info in cm.items():
            student = self.get_student(student_id)
            if not student:
                continue
            merged = dict(student)
            merged.update({
                'role': member_info.get('role'),
                'join_date': member_info.get('join_date'),
                'membership_id': member_info.get('membership_id')
            })
            members.append(merged)
        members.sort(key=lambda m: (m.get('name') or '').lower())
        return members

    def update_member_role(self, club_id, student_id, new_role):
        allowed = {"Member", "Officer", "President", "Vice President", "Treasurer", "Secretary"}
        if new_role not in allowed:
            raise ValueError("Invalid role")
        transaction = self.db.transaction()

        @firestore.transactional
        def txn_update(transaction):
            q = self.db.collection("memberships").where("club_id", "==", club_id).where("student_id", "==", student_id).limit(1)
            docs = list(q.get(transaction=transaction))
            if not docs:
                raise ValueError("Membership not found")
            for d in docs:
                transaction.update(d.reference, {"role": new_role})

            club_members_ref = self.db.collection("club_members").document(club_id)
            cm_snap = club_members_ref.get(transaction=transaction)
            if not cm_snap.exists:
                raise ValueError("Denormalized club_members missing")
            transaction.update(club_members_ref, {f"{student_id}.role": new_role})

            sm_ref = self.db.collection("student_memberships").document(student_id)
            sm_snap = sm_ref.get(transaction=transaction)
            if not sm_snap.exists:
                raise ValueError("Denormalized student_memberships missing")
            transaction.update(sm_ref, {f"{club_id}.role": new_role})

        txn_update(transaction)
        return True

    def update_club_member_count(self, club_id):
        members = self.get_club_members(club_id)
        count = len(members)
        self.db.collection("clubs").document(club_id).update({"member_count": count})
        return count

    # helpers
    def get_all_clubs_map(self):
        return {c["id"]: (c.get("name") or "") for c in self.get_all_clubs()}

    def get_students_with_memberships(self, club_ids=None, role=None):
        clubs_map = self.get_all_clubs_map()
        result = []
        sm_stream = self.db.collection("student_memberships").stream()

        for sm_doc in sm_stream:
            student_id = sm_doc.id
            sm_data = sm_doc.to_dict() or {}
            entries = []
            for cid, info in sm_data.items():
                if club_ids and cid not in club_ids:
                    continue
                info_role = info.get("role")
                if role and info_role != role:
                    continue
                entries.append({
                    "club_id": cid,
                    "club_name": clubs_map.get(cid, ""),
                    "role": info_role,
                    "join_date": info.get("join_date"),
                })

            if club_ids or role:
                if not entries:
                    continue

            student = self.get_student(student_id)
            if not student:
                continue

            if not (club_ids or role):
                entries = []
                for cid, info in (sm_data.items()):
                    entries.append({
                        "club_id": cid,
                        "club_name": clubs_map.get(cid, ""),
                        "role": info.get("role"),
                        "join_date": info.get("join_date"),
                    })

            result.append({
                "id": student["id"],
                "name": student.get("name"),
                "email": student.get("email"),
                "memberships": entries
            })

        if not (club_ids or role):
            present_ids = {s["id"] for s in result}
            for s in self.get_all_students():
                if s["id"] in present_ids:
                    continue
                result.append({
                    "id": s["id"],
                    "name": s.get("name"),
                    "email": s.get("email"),
                    "memberships": []
                })

        result.sort(key=lambda s: (s.get("name") or "").lower())
        return result
    
    from datetime import datetime

    # ---------- Verification (two-step) ----------
    def set_verification_request(self, club_id: str, requested_by: str, note: str | None = None) -> bool:
        """Start verification: store 'pending' state on the club."""
        club_ref = self.db.collection("clubs").document(club_id)
        snap = club_ref.get()
        if not snap.exists:
            raise ValueError("Club not found")

        data = snap.to_dict() or {}
        # If already verified, ignore
        if data.get("verified"):
            return True

        verification = {
            "status": "pending",
            "requested_by": requested_by or "",
            "requested_at": datetime.now().isoformat(),
        }
        if note:
            verification["note"] = note

        club_ref.update({"verification": verification})
        return True

    def confirm_verification(self, club_id: str, confirmer_email: str) -> bool:
        """Approve verification by a different officer (or advisor path handled in app)."""
        club_ref = self.db.collection("clubs").document(club_id)
        snap = club_ref.get()
        if not snap.exists:
            raise ValueError("Club not found")

        d = snap.to_dict() or {}
        if d.get("verified"):
            return True

        ver = (d.get("verification") or {})
        if ver.get("status") != "pending":
            # If no pending request, allow direct verify (advisor path) but keep data tidy
            ver = {"status": "pending", "requested_by": ver.get("requested_by", ""), "requested_at": datetime.now().isoformat()}

        if confirmer_email and ver.get("requested_by") and confirmer_email.strip().lower() == (ver.get("requested_by") or "").strip().lower():
            raise ValueError("Second officer must be different from requester")

        # Approve
        ver.update({
            "status": "approved",
            "approved_by": confirmer_email or "",
            "approved_at": datetime.now().isoformat(),
        })
        club_ref.update({"verified": True, "verification": ver})
        return True

