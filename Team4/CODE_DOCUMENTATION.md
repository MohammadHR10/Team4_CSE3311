# Code Documentation - Club House Management System

## 📁 Project Structure & Architecture

```
Team4/
├── app.py                      # Main Flask application and route handlers
├── firebase_config.py          # Database configuration and operations
├── logger.py                   # Centralized logging configuration
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
├── serviceAccountKey.json      # Firebase credentials (not in git)
├── utils/
│   ├── validators.py           # Input validation functions
│   └── authz.py               # Authentication and authorization
├── templates/                  # Jinja2 HTML templates
│   ├── base.html              # Main layout template
│   ├── index.html             # Dashboard/home page
│   ├── students.html          # Student management page
│   ├── clubs.html             # Club management page
│   ├── roster.html            # Membership roster page
│   └── login.html             # Authentication page
├── static/                     # CSS and static assets
│   ├── styles.css             # Main stylesheet
│   └── style2.css             # Additional styles
└── tests/                      # Unit and integration tests
```

## 🔧 Core Modules Explained

### 1. **app.py** - Main Application Controller
The heart of the Flask application containing all route handlers and business logic.

**Key Sections:**
- **Authentication Routes** (`/login`, `/logout`) - Handle user login/logout
- **Dashboard Route** (`/`) - Main page showing system overview  
- **Student Management** (`/students`) - CRUD operations for students
- **Club Management** (`/clubs`) - CRUD operations for clubs
- **Roster Management** (`/roster`) - Member-club relationship management
- **CSV Import/Export** - Bulk data operations

**Important Functions:**
```python
@app.route("/students", methods=["GET", "POST"])
@require_officer  # Decorator requiring officer permissions
def students():
    """Handles student management - view, add, edit, delete students"""
    
@app.route("/api/students/<email_key>", methods=["DELETE"])  
def delete_student_api(email_key):
    """API endpoint for deleting students via AJAX"""

@app.route("/roster")
def roster():
    """Display and manage club memberships"""
```

### 2. **firebase_config.py** - Database Layer
Handles all Firebase Firestore database operations with a clean API.

**Key Classes:**
```python
class FirebaseDB:
    """Main database interface providing CRUD operations"""
    
    # Student Operations
    def add_student(self, student_data):
        """Add new student to database"""
        
    def get_all_students(self):
        """Retrieve all students with pagination support"""
        
    def update_student(self, email_key, updated_data):
        """Update existing student information"""
        
    def delete_student(self, email_key):
        """Remove student and all related memberships"""
    
    # Club Operations  
    def add_club(self, club_data):
        """Create new club with initial setup"""
        
    def get_all_clubs(self):
        """Get all clubs with member counts"""
        
    def assign_officer(self, club_name, email, role):
        """Assign officer role to student in club"""
    
    # Membership Operations
    def add_membership(self, student_email, club_name, role="Member"):
        """Add student to club with specified role"""
        
    def get_memberships_by_club(self, club_name):
        """Get all members of a specific club"""
```

**Database Collections:**
- **students**: Individual student records
- **clubs**: Club information and officer assignments  
- **memberships**: Student-club relationships (junction table)

### 3. **utils/validators.py** - Input Validation
Ensures data integrity and security through comprehensive validation.

**Key Functions:**
```python
def valid_email(email: str) -> bool:
    """Validates email format using regex pattern"""
    # Prevents: double periods, invalid characters, malformed domains
    
def normalize_email(email: str) -> str:
    """Converts email to lowercase and trims whitespace"""
    
def normalize_email_key(email: str) -> str:
    """Creates Firestore-safe document ID from email"""
    # Replaces @ and . with _ for use as document keys
    
def validate_name(name: str) -> bool:
    """Validates person names (letters, spaces, hyphens, apostrophes)"""
    
def validate_role(role: str) -> bool:
    """Ensures role is in allowed set"""
    # Allowed: Member, Officer, President, Vice President, etc.
```

### 4. **utils/authz.py** - Authentication & Authorization
Manages user sessions and role-based access control.

**Key Functions:**
```python
def current_user():
    """Returns logged-in user information from session"""
    
def get_current_role():
    """Gets user role with fallback to 'Member'"""
    # Includes development override via ?as=Officer URL parameter
    
@require_officer
def protected_function():
    """Decorator requiring Officer role to access function"""
    
@require_login  
def logged_in_function():
    """Decorator requiring any authenticated user"""
```

**Session Structure:**
```python
session['user'] = {
    'email': 'user@example.com',
    'role': 'Officer',  # or 'Member'
    'name': 'John Doe'
}
```

### 5. **logger.py** - Logging System
Centralized logging with both console and file output.

**Features:**
- **Dual Output**: Console for development, files for production
- **Log Rotation**: Prevents large log files (5MB max, 3 backups)
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR via environment
- **Structured Format**: Timestamps, levels, source locations

```python
def get_logger(name: str = None) -> logging.Logger:
    """Creates configured logger with console and file handlers"""
    
# Usage in modules:
logger = get_logger(__name__)
logger.info("Student added successfully")
logger.error("Database connection failed")
```

## 🔐 Security Features

### **Authentication System**
- **Role-based Access**: Member, Officer, Advisor roles
- **Access Codes**: Simple code-based authentication
- **Session Management**: Secure session handling with timeouts
- **CSRF Protection**: Built-in Flask session security

### **Input Validation**
- **Email Validation**: Comprehensive regex pattern matching
- **Name Validation**: Prevents injection attacks
- **Role Validation**: Whitelist-based role checking
- **SQL Injection Prevention**: Firestore NoSQL prevents traditional SQL injection

### **Data Security**
- **Credential Management**: Service account keys not in version control
- **Environment Variables**: Sensitive data in .env files
- **Firestore Rules**: Server-side security rules (configured in Firebase)

## 🎨 Frontend Architecture

### **Template System (Jinja2)**
- **base.html**: Main layout with navigation and common elements
- **Page Templates**: Extend base template for consistent layout
- **Dynamic Navigation**: Role-based menu items
- **Flash Messages**: User feedback system

### **Responsive Design (Bootstrap 5)**
- **Mobile-First**: Responsive grid system
- **Component Library**: Cards, forms, tables, modals
- **Icon System**: Bootstrap Icons for UI elements
- **Custom Styling**: Application-specific CSS overrides

### **JavaScript Features**
- **AJAX Operations**: Delete operations without page refresh
- **Form Validation**: Client-side validation before submission
- **Interactive Elements**: Dynamic content updates
- **Modal Dialogs**: Confirmation dialogs for destructive operations

## 📊 Data Flow Examples

### **Adding a Student**
1. User fills form on `/students` page
2. `@require_officer` decorator checks permissions
3. `validate_email()` and `validate_name()` check input
4. `normalize_email_key()` creates document ID
5. `db.add_student()` saves to Firestore
6. Flash message confirms success
7. Page redirects with updated student list

### **Managing Club Membership**
1. Officer accesses `/roster` page
2. Form submission triggers membership creation
3. `db.add_membership()` creates relationship record
4. `db.update_club_member_count()` increments club counter
5. Real-time updates reflect in club statistics

### **Authentication Flow**
1. User visits protected route
2. `@require_officer` decorator intercepts request
3. `current_user()` checks session for user info
4. If not authenticated, redirects to `/login`
5. Login form validates access code
6. Successful login stores user in session
7. User redirected to original destination

## 🧪 Testing Strategy

### **Unit Tests** (`tests/unit_test_validators.py`)
- Input validation function testing
- Edge case handling
- Error condition testing

### **Integration Tests** (`tests/integration_test_membership_api.py`)
- Database operation testing
- API endpoint testing  
- End-to-end workflow testing

### **Test Configuration** (`tests/conftest.py`)
- Shared test fixtures
- Mock database setup
- Test environment configuration

## 🚀 Deployment Considerations

### **Environment Setup**
- **Development**: Local Flask dev server with DEBUG=True
- **Production**: WSGI server (Gunicorn) with DEBUG=False
- **Database**: Firebase Firestore (cloud-hosted)
- **Static Files**: Served via CDN or web server

### **Security Checklist**
- [ ] Change default secret keys
- [ ] Set secure session cookies
- [ ] Configure Firebase security rules
- [ ] Enable HTTPS in production
- [ ] Set appropriate log levels
- [ ] Validate all user inputs
- [ ] Implement rate limiting

### **Monitoring & Maintenance**
- **Logging**: Centralized logging with rotation
- **Error Tracking**: Application error monitoring
- **Performance**: Database query optimization
- **Backup**: Regular Firestore backups
- **Updates**: Regular dependency updates for security

This documentation provides a comprehensive overview of how the Club House Management System is architected and implemented. Each module is designed with separation of concerns, making the codebase maintainable and extensible.