# Club House Management System - CSE3311 Team 4

A comprehensive web-based system for managing student club memberships at universities. This Flask application provides an intuitive interface for students, officers, and advisors to manage club information, track memberships, and handle administrative tasks.

## 🎯 Project Overview

**Problem**: Current platforms for tracking club memberships are inefficient, overwhelming, or too complicated. Students and club officers often rely on manual systems like paper sign-up sheets, spreadsheets, or informal group chats, leading to inaccurate data and communication difficulties.

**Solution**: A clean, easy-to-use platform that demonstrates database operations (Create, Read, Update, Delete) within a context highly relatable to students, providing efficient club membership management.

## 👥 Team Members
- **Mohammad Hasibur Rahman** - Lead Developer & Database Design
- **Ariston Stitt** - Frontend Development & UI/UX
- **Joshua Thomas** - Backend Development & Testing
- **Kaitlynn Hernandez** - System Architecture & Documentation

## 🛠 Technical Architecture

### **Backend Stack**
- **Flask 3.0.0** - Python web framework
- **Firebase Firestore** - NoSQL cloud database
- **Python-dotenv** - Environment configuration management
- **Jinja2** - Template engine for dynamic HTML generation

### **Frontend Stack**
- **Bootstrap 5.3.0** - Responsive CSS framework
- **Bootstrap Icons** - UI iconography
- **Custom CSS** - Application-specific styling
- **Vanilla JavaScript** - Interactive features

### **Database Design**
```
Collections:
├── students/           # Student records
│   ├── {email_key}/   # Document ID: normalized email
│   └── Fields: name, email, phone, graduation_term, graduation_year
├── clubs/             # Club information  
│   ├── {club_name}/   # Document ID: club name
│   └── Fields: name, description, officers{}, member_count
└── memberships/       # Student-Club relationships
    ├── {email_key}/   # Document ID: normalized email
    └── Fields: student_email, club_name, role, join_date
```

## 🚀 Getting Started

### **Prerequisites**
- Python 3.8+
- Firebase Project with Firestore enabled
- Git

### **Installation**

1. **Clone the repository**
```bash
git clone https://github.com/MohammadHR10/Team4_CSE3311.git
cd Team4_CSE3311/Team4
```

2. **Set up virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Firebase**
```bash
# Copy the template and add your credentials
cp serviceAccountKey.json.template serviceAccountKey.json
# Edit serviceAccountKey.json with your Firebase credentials
```

5. **Set up environment variables**
```bash
# Copy and customize the environment file
cp .env.example .env
# Edit .env with your specific configuration
```

### **Configuration Files Explained**

#### **.env Configuration**
```bash
# Flask Application Settings
FLASK_SECRET_KEY=your-secret-key-here           # Change in production!
FLASK_DEBUG=True                                # Development mode
FLASK_ENV=development                           # Environment type
PORT=5002                                       # Application port

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_PATH=serviceAccountKey.json  # Path to credentials

# Authentication Codes
OFFICER_ACCESS_CODE=let-me-manage               # Officer authentication
ADVISOR_CODE=SECRET123                          # Advisor authentication

# Logging
APP_LOG_LEVEL=DEBUG                            # Log verbosity
```  
FLASK_SECRET_KEY=your-super-secret-key-here-change-this-in-production

Firebase Setup
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or select existing one
3. Go to Project Settings > Service Accounts
4. Generate a new private key (downloads a JSON file)
5. Either:
   - Save the JSON file in your project and set FIREBASE_SERVICE_ACCOUNT_PATH
   - Copy the JSON content and set FIREBASE_SERVICE_ACCOUNT_KEY
     
Installation
1.	Create a virtual environment
python3 –m venv venv
Source venv/bin/activate
2.	Install dependencies:
pip install -r requirements.txt
3.	 Run the application:
python app.py
The application will be available at http://localhost:5000

Features
- Create, read, update, delete clubs
- Search clubs by name or description
- View club rosters and member details
- Add/remove members from clubs



