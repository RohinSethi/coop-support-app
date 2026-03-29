# Co-op Support Application

A web-based portal for managing the co-op program — built for students, co-op coordinators, and employers.

---

## Overview

This application streamlines the entire co-op process from initial student application through to final acceptance, work term report submission, and employer evaluation. Each user role has a dedicated portal with access restricted to only what they are permitted to see.

---

## Features

### Student
- Submit a co-op application (name, student ID, email, GPA, password)
- Form validation — checks email format and 9-digit student ID
- Receive a simulated confirmation email on submission
- Log in after provisional acceptance to access the student portal
- View application status (Pending → Provisionally Accepted → Finally Accepted)
- Upload a PDF work term report with deadline displayed
- Download a work term report PDF template

### Co-op Coordinator
- Secure login with admin-level access
- Dashboard showing all applications with status badges and stats
- Search and filter applications by name, student ID, email, or status
- Review individual applications with full student details
- Issue a **provisional** accept or reject decision (with optional notes and final decision date)
- Issue a **final** accept or reject decision separately
- Log placement rejections for individual students
- View reports: which students have/haven't submitted reports or evaluations
- Send batch reminder emails to students with missing reports

### Employer
- Register an employer account (separate from student/coordinator accounts)
- Log in to the employer portal
- Submit a student evaluation via:
  - **Online form** — scores for behaviour, skills, knowledge, and attitude
  - **PDF upload** — scanned evaluation form
- View all previously submitted evaluations

---

## Role-Based Access Control

| Feature | Student | Coordinator | Employer |
|---|---|---|---|
| Apply for co-op | ✅ | — | — |
| Student portal | ✅ | — | — |
| Upload work term report | ✅ | — | — |
| Coordinator dashboard | — | ✅ | — |
| Accept / Reject applicants | — | ✅ | — |
| View all student data | — | ✅ | — |
| Submit evaluations | — | — | ✅ |
| View own evaluations | — | — | ✅ |

Navigating to `/login` while already logged in automatically logs out the current session, allowing any role to switch accounts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 / Flask 3.0 |
| Database | SQLite (via Flask-SQLAlchemy) |
| Authentication | Flask-Login + Werkzeug password hashing |
| Frontend | Jinja2 templates + Bootstrap 5 |
| File uploads | Werkzeug secure file handling |
| Production server | Gunicorn |

---

## Getting Started (Run Locally)

### Prerequisites
- Python 3.9 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/RohinSethi/coop-support-app.git
cd coop-support-app

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Then open **http://localhost:5000** in your browser.

The database is created automatically on first run, along with a default coordinator account.

---

## Default Credentials

| Role | Email | Password |
|---|---|---|
| Co-op Coordinator | coordinator@coop.com | admin123 |
| Student | *(set during application)* | *(chosen at sign-up)* |
| Employer | *(set during registration)* | *(chosen at sign-up)* |

---

## Project Structure

```
coop_app/
├── app.py                  # Main Flask application (routes, models, logic)
├── requirements.txt        # Python dependencies
├── Procfile                # Gunicorn start command for deployment
├── render.yaml             # Render deployment configuration
├── uploads/                # Uploaded PDF files (gitignored)
└── templates/
    ├── base.html           # Shared layout (navbar, flash messages)
    ├── index.html          # Landing page
    ├── apply.html          # Student application form
    ├── apply_success.html  # Confirmation page after applying
    ├── login.html          # Login page (all roles)
    ├── coordinator/
    │   ├── dashboard.html  # Application list + filters + stats
    │   ├── application.html# Individual application review + decisions
    │   └── reports.html    # Submission and evaluation reports
    ├── student/
    │   ├── dashboard.html  # Student portal + application status
    │   └── upload_report.html # Work term report upload
    └── employer/
        ├── register.html   # Employer registration
        ├── dashboard.html  # Employer portal + evaluation history
        └── evaluate.html   # Submit online form or PDF evaluation
```


---

## Database Models

| Model | Description |
|---|---|
| `User` | All user accounts (student, coordinator, employer) with hashed passwords |
| `Application` | Student co-op applications with provisional and final decision tracking |
| `WorkTermReport` | Uploaded PDF reports linked to a student user |
| `EmployerEvaluation` | Online form scores or PDF evaluations linked to a student |
| `PlacementRejection` | Log of co-op placement rejections for a student |

---


