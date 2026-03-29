from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import re
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'coop-support-app-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///coop.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_student_id(sid):
    return bool(re.match(r'^\d{9}$', sid))


def validate_email(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email))


def send_email_notification(to_email, subject, body):
    """Simulated email — logs to console. Replace with Flask-Mail for production."""
    print(f"\n{'='*60}")
    print(f"  EMAIL TO:      {to_email}")
    print(f"  SUBJECT:       {subject}")
    print(f"  BODY:\n{body}")
    print(f"{'='*60}\n")


# ─────────────────────────── MODELS ───────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20), nullable=False)   # student | coordinator | employer
    student_id = db.Column(db.String(20), unique=True, nullable=True)
    company = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw, method='pbkdf2:sha256')

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    gpa = db.Column(db.Float, nullable=True)
    # Pending | Provisionally Accepted | Provisionally Rejected | Finally Accepted | Finally Rejected
    status = db.Column(db.String(30), default='Pending')
    provisional_date = db.Column(db.DateTime, nullable=True)
    final_decision_date = db.Column(db.DateTime, nullable=True)
    final_decision_due = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejections = db.relationship('PlacementRejection', backref='application', lazy=True)


class PlacementRejection(db.Model):
    __tablename__ = 'placement_rejections'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    company_name = db.Column(db.String(200), nullable=True)
    rejection_date = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.Text, nullable=True)
    logged_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class WorkTermReport(db.Model):
    __tablename__ = 'work_term_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    term = db.Column(db.String(50), nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='reports')


class EmployerEvaluation(db.Model):
    __tablename__ = 'employer_evaluations'
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    student_name = db.Column(db.String(100), nullable=True)
    student_id_str = db.Column(db.String(20), nullable=True)
    behavior_score = db.Column(db.Integer, nullable=True)
    skills_score = db.Column(db.Integer, nullable=True)
    knowledge_score = db.Column(db.Integer, nullable=True)
    attitude_score = db.Column(db.Integer, nullable=True)
    overall_comments = db.Column(db.Text, nullable=True)
    pdf_path = db.Column(db.String(300), nullable=True)
    pdf_filename = db.Column(db.String(200), nullable=True)
    submission_type = db.Column(db.String(10), nullable=True)  # online | pdf
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    employer = db.relationship('User', foreign_keys=[employer_id])


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))


# ─────────────────────────── PUBLIC ROUTES ───────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sid = request.form.get('student_id', '').strip()
        email = request.form.get('email', '').strip()
        gpa_str = request.form.get('gpa', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        errors = []
        if not name:
            errors.append('Full name is required.')
        if not sid:
            errors.append('Student ID is required.')
        elif not validate_student_id(sid):
            errors.append('Student ID must be exactly 9 digits.')
        if not email:
            errors.append('Email address is required.')
        elif not validate_email(email):
            errors.append('Please enter a valid email address.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        elif password != confirm_password:
            errors.append('Passwords do not match.')

        gpa = None
        if gpa_str:
            try:
                gpa = float(gpa_str)
                if not (0.0 <= gpa <= 4.0):
                    errors.append('GPA must be between 0.0 and 4.0.')
            except ValueError:
                errors.append('GPA must be a number.')

        if not errors:
            if Application.query.filter_by(student_id=sid).first():
                errors.append(f'An application with student ID {sid} already exists.')
            if Application.query.filter_by(email=email).first():
                errors.append('An application with this email already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('apply.html', form_data=request.form)

        rec = Application(student_name=name, student_id=sid, email=email, gpa=gpa, status='Pending',
                          password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(rec)
        db.session.commit()

        send_email_notification(
            email,
            'Co-op Application Received',
            f'Dear {name},\n\nYour application (Student ID: {sid}) has been received and is now Pending review.\n\nBest regards,\nCo-op Office'
        )
        flash(f'Application submitted! A confirmation has been sent to {email}.', 'success')
        return redirect(url_for('apply_success', app_id=rec.id))

    return render_template('apply.html', form_data={})


@app.route('/apply/success/<int:app_id>')
def apply_success(app_id):
    rec = Application.query.get_or_404(app_id)
    return render_template('apply_success.html', application=rec)


# ─────────────────────────── AUTH ───────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in as a different role, log out first so the user can switch accounts
    if current_user.is_authenticated:
        logout_user()

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            nxt = request.args.get('next')
            return redirect(nxt or url_for('dashboard_redirect'))
        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard_redirect():
    roles = {'coordinator': 'coordinator_dashboard', 'student': 'student_dashboard', 'employer': 'employer_dashboard'}
    return redirect(url_for(roles.get(current_user.role, 'index')))


# ─────────────────────────── COORDINATOR ───────────────────────────

def coordinator_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'coordinator':
            flash('Coordinator access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


@app.route('/coordinator/dashboard')
@login_required
@coordinator_required
def coordinator_dashboard():
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()

    q = Application.query
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    if search:
        q = q.filter(
            db.or_(
                Application.student_name.ilike(f'%{search}%'),
                Application.student_id.ilike(f'%{search}%'),
                Application.email.ilike(f'%{search}%')
            )
        )
    applications = q.order_by(Application.created_at.desc()).all()

    stats = {
        'total': Application.query.count(),
        'pending': Application.query.filter_by(status='Pending').count(),
        'prov_accepted': Application.query.filter_by(status='Provisionally Accepted').count(),
        'prov_rejected': Application.query.filter_by(status='Provisionally Rejected').count(),
        'finally_accepted': Application.query.filter_by(status='Finally Accepted').count(),
        'finally_rejected': Application.query.filter_by(status='Finally Rejected').count(),
    }
    return render_template('coordinator/dashboard.html',
                           applications=applications, stats=stats,
                           status_filter=status_filter, search=search)


@app.route('/coordinator/application/<int:app_id>')
@login_required
@coordinator_required
def coordinator_application(app_id):
    application = Application.query.get_or_404(app_id)
    report = None
    evaluations = []
    if application.user_id:
        report = WorkTermReport.query.filter_by(user_id=application.user_id).order_by(WorkTermReport.submitted_at.desc()).first()
        evaluations = EmployerEvaluation.query.filter_by(student_user_id=application.user_id).all()
    return render_template('coordinator/application.html',
                           application=application, report=report, evaluations=evaluations)


@app.route('/coordinator/application/<int:app_id>/decide', methods=['POST'])
@login_required
@coordinator_required
def coordinator_decide(app_id):
    application = Application.query.get_or_404(app_id)
    dtype = request.form.get('decision_type')
    decision = request.form.get('decision')
    notes = request.form.get('notes', '').strip()
    final_due_str = request.form.get('final_due', '').strip()

    if notes:
        application.notes = notes

    if dtype == 'provisional':
        application.provisional_date = datetime.utcnow()
        if final_due_str:
            try:
                application.final_decision_due = datetime.strptime(final_due_str, '%Y-%m-%d')
            except ValueError:
                pass

        if decision == 'accept':
            application.status = 'Provisionally Accepted'
            # Create student login account using their chosen password
            existing = User.query.filter_by(email=application.email).first()
            if not existing:
                u = User(name=application.student_name, email=application.email,
                         role='student', student_id=application.student_id)
                u.password_hash = application.password_hash
                db.session.add(u)
                db.session.flush()
                application.user_id = u.id
            else:
                application.user_id = existing.id

            due_msg = f' The final decision will be made by {application.final_decision_due.strftime("%B %d, %Y")}.' if application.final_decision_due else ''
            send_email_notification(
                application.email,
                'Co-op Application: Provisionally Accepted',
                f'Dear {application.student_name},\n\nCongratulations! Your application has been provisionally accepted.{due_msg}\n\n'
                f'You can now log in to the student portal:\n  URL: http://localhost:5000/login\n  Email: {application.email}\n  Password: (the password you set when you applied)\n\nBest regards,\nCo-op Office'
            )
            flash(f'{application.student_name} provisionally accepted. Student portal access granted.', 'success')

        elif decision == 'reject':
            application.status = 'Provisionally Rejected'
            send_email_notification(
                application.email,
                'Co-op Application: Provisional Decision',
                f'Dear {application.student_name},\n\nWe regret to inform you that your application was not provisionally accepted.\n\nBest regards,\nCo-op Office'
            )
            flash(f'{application.student_name} provisionally rejected.', 'warning')

    elif dtype == 'final':
        application.final_decision_date = datetime.utcnow()
        if decision == 'accept':
            application.status = 'Finally Accepted'
            send_email_notification(
                application.email,
                'Co-op Application: Final Decision — Accepted',
                f'Dear {application.student_name},\n\nCongratulations! You have been finally accepted into the co-op program.\n\nBest regards,\nCo-op Office'
            )
            flash(f'{application.student_name} finally accepted.', 'success')
        elif decision == 'reject':
            application.status = 'Finally Rejected'
            send_email_notification(
                application.email,
                'Co-op Application: Final Decision',
                f'Dear {application.student_name},\n\nWe regret to inform you that your application was not accepted.\n\nBest regards,\nCo-op Office'
            )
            flash(f'{application.student_name} finally rejected.', 'warning')

    elif dtype == 'placement_rejection':
        company = request.form.get('company', '').strip()
        reason = request.form.get('reason', '').strip()
        pr = PlacementRejection(application_id=application.id, company_name=company,
                                reason=reason, logged_by=current_user.id)
        db.session.add(pr)
        flash(f'Placement rejection logged for {application.student_name}.', 'info')

    db.session.commit()
    return redirect(url_for('coordinator_application', app_id=app_id))


@app.route('/coordinator/reports')
@login_required
@coordinator_required
def coordinator_reports():
    all_apps = Application.query.order_by(Application.created_at.desc()).all()
    accepted = [a for a in all_apps if a.status in ('Provisionally Accepted', 'Finally Accepted')]

    with_reports, without_reports = [], []
    with_evals, without_evals = [], []

    for a in accepted:
        if a.user_id:
            r = WorkTermReport.query.filter_by(user_id=a.user_id).first()
            (with_reports if r else without_reports).append(a)
            e = EmployerEvaluation.query.filter_by(student_user_id=a.user_id).count()
            (with_evals if e > 0 else without_evals).append(a)
        else:
            without_reports.append(a)
            without_evals.append(a)

    return render_template('coordinator/reports.html',
                           all_apps=all_apps, accepted=accepted,
                           with_reports=with_reports, without_reports=without_reports,
                           with_evals=with_evals, without_evals=without_evals)


@app.route('/coordinator/send-reminders', methods=['POST'])
@login_required
@coordinator_required
def send_reminders():
    accepted = Application.query.filter(
        Application.status.in_(['Provisionally Accepted', 'Finally Accepted'])
    ).all()
    sent = 0
    for a in accepted:
        if a.user_id and not WorkTermReport.query.filter_by(user_id=a.user_id).first():
            send_email_notification(
                a.email,
                'Reminder: Work Term Report Not Submitted',
                f'Dear {a.student_name},\n\nThis is a reminder that your work term report has not been submitted. Please log in and submit it as soon as possible.\n\nBest regards,\nCo-op Office'
            )
            sent += 1
    flash(f'Reminder emails sent to {sent} student(s).', 'info')
    return redirect(url_for('coordinator_reports'))


# ─────────────────────────── STUDENT ───────────────────────────

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Student access required.', 'danger')
        return redirect(url_for('dashboard_redirect'))

    application = Application.query.filter_by(user_id=current_user.id).first() or \
                  Application.query.filter_by(email=current_user.email).first()
    reports = WorkTermReport.query.filter_by(user_id=current_user.id).order_by(WorkTermReport.submitted_at.desc()).all()
    deadline = datetime(datetime.now().year, 12, 15)
    return render_template('student/dashboard.html', application=application, reports=reports,
                           deadline=deadline, now=datetime.utcnow())


@app.route('/student/upload-report', methods=['GET', 'POST'])
@login_required
def student_upload_report():
    if current_user.role != 'student':
        flash('Student access required.', 'danger')
        return redirect(url_for('dashboard_redirect'))

    deadline = datetime(datetime.now().year, 12, 15)

    if request.method == 'POST':
        file = request.files.get('report_file')
        term = request.form.get('term', 'Fall 2024').strip()

        if not file or file.filename == '':
            flash('Please select a file.', 'danger')
            return render_template('student/upload_report.html', deadline=deadline)

        if not allowed_file(file.filename):
            flash('Only PDF files are accepted.', 'danger')
            return render_template('student/upload_report.html', deadline=deadline)

        fname = secure_filename(f"{current_user.student_id}_{term.replace(' ', '_')}_{file.filename}")
        fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        file.save(fpath)

        existing = WorkTermReport.query.filter_by(user_id=current_user.id, term=term).first()
        if existing:
            if os.path.exists(existing.file_path):
                os.remove(existing.file_path)
            existing.file_path = fpath
            existing.original_filename = file.filename
            existing.submitted_at = datetime.utcnow()
            flash(f'Report for {term} updated.', 'success')
        else:
            rpt = WorkTermReport(user_id=current_user.id, file_path=fpath,
                                 original_filename=file.filename, term=term, deadline=deadline)
            db.session.add(rpt)
            flash(f'Report for {term} submitted.', 'success')

        db.session.commit()
        return redirect(url_for('student_dashboard'))

    return render_template('student/upload_report.html', deadline=deadline)


@app.route('/student/download-template')
@login_required
def download_template():
    if current_user.role != 'student':
        flash('Student access required.', 'danger')
        return redirect(url_for('dashboard_redirect'))

    pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica-Bold>>endobj
5 0 obj<</Length 900>>
stream
BT /F1 16 Tf 50 750 Td (CO-OP WORK TERM REPORT TEMPLATE) Tj
/F1 11 Tf 0 -35 Td (Student Name: ___________________________________) Tj
0 -20 Td (Student ID:   ___________________________________) Tj
0 -20 Td (Work Term:    ___________________________________) Tj
0 -20 Td (Employer:     ___________________________________) Tj
0 -20 Td (Position:     ___________________________________) Tj
0 -30 Td (1. INTRODUCTION) Tj
0 -18 Td (Briefly describe the organization and your role.) Tj
0 -18 Td (___________________________________________________) Tj
0 -18 Td (___________________________________________________) Tj
0 -30 Td (2. WORK TERM DESCRIPTION) Tj
0 -18 Td (Describe your main responsibilities and projects.) Tj
0 -18 Td (___________________________________________________) Tj
0 -18 Td (___________________________________________________) Tj
0 -30 Td (3. LEARNING OUTCOMES) Tj
0 -18 Td (Describe what technical and professional skills you developed.) Tj
0 -18 Td (___________________________________________________) Tj
0 -18 Td (___________________________________________________) Tj
0 -30 Td (4. CONCLUSIONS) Tj
0 -18 Td (Summarize your overall co-op experience.) Tj
0 -18 Td (___________________________________________________) Tj
0 -18 Td (___________________________________________________) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000274 00000 n
0000000352 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
1304
%%EOF"""
    return send_file(io.BytesIO(pdf), as_attachment=True,
                     download_name='work_term_report_template.pdf', mimetype='application/pdf')


# ─────────────────────────── EMPLOYER ───────────────────────────

@app.route('/employer/register', methods=['GET', 'POST'])
def employer_register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        company = request.form.get('company', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        errors = []
        if not name:
            errors.append('Name is required.')
        if not email or not validate_email(email):
            errors.append('A valid email is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('employer/register.html', form_data=request.form)

        u = User(name=name, email=email, role='employer', company=company)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('Employer account created. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('employer/register.html', form_data={})


@app.route('/employer/dashboard')
@login_required
def employer_dashboard():
    if current_user.role != 'employer':
        flash('Employer access required.', 'danger')
        return redirect(url_for('dashboard_redirect'))

    evaluations = EmployerEvaluation.query.filter_by(employer_id=current_user.id).all()
    students = User.query.filter_by(role='student').all()
    return render_template('employer/dashboard.html', evaluations=evaluations, students=students)


@app.route('/employer/evaluate', methods=['GET', 'POST'])
@login_required
def employer_evaluate():
    if current_user.role != 'employer':
        flash('Employer access required.', 'danger')
        return redirect(url_for('dashboard_redirect'))

    students = User.query.filter_by(role='student').all()

    if request.method == 'POST':
        stype = request.form.get('submission_type', 'online')
        sid_form = request.form.get('student_user_id', '').strip()

        student_user = User.query.get(int(sid_form)) if sid_form.isdigit() else None
        sname = student_user.name if student_user else request.form.get('student_name_manual', '').strip()
        sid_str = student_user.student_id if student_user else request.form.get('student_id_manual', '').strip()

        ev = EmployerEvaluation(
            employer_id=current_user.id,
            student_user_id=student_user.id if student_user else None,
            student_name=sname, student_id_str=sid_str,
            submission_type=stype
        )

        if stype == 'online':
            ev.behavior_score = int(request.form.get('behavior_score', 3))
            ev.skills_score = int(request.form.get('skills_score', 3))
            ev.knowledge_score = int(request.form.get('knowledge_score', 3))
            ev.attitude_score = int(request.form.get('attitude_score', 3))
            ev.overall_comments = request.form.get('overall_comments', '').strip()
            db.session.add(ev)
            db.session.commit()
            flash('Online evaluation submitted successfully.', 'success')
            return redirect(url_for('employer_dashboard'))

        elif stype == 'pdf':
            file = request.files.get('eval_pdf')
            if not file or file.filename == '':
                flash('Please upload a PDF file.', 'danger')
                return render_template('employer/evaluate.html', students=students)
            if not allowed_file(file.filename):
                flash('Only PDF files are accepted.', 'danger')
                return render_template('employer/evaluate.html', students=students)
            fname = secure_filename(f"eval_{current_user.id}_{sid_str}_{file.filename}")
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            file.save(fpath)
            ev.pdf_path = fpath
            ev.pdf_filename = file.filename
            db.session.add(ev)
            db.session.commit()
            flash('PDF evaluation uploaded successfully.', 'success')
            return redirect(url_for('employer_dashboard'))

    return render_template('employer/evaluate.html', students=students)


# ─────────────────────────── DB INIT ───────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='coordinator@coop.com').first():
            coord = User(name='Co-op Coordinator', email='coordinator@coop.com', role='coordinator')
            coord.set_password('admin123')
            db.session.add(coord)
            db.session.commit()
            print('Coordinator created: coordinator@coop.com / admin123')
        print('Database ready.')

# Run on startup regardless of how the app is launched (gunicorn or python app.py)
init_db()


if __name__ == '__main__':
    init_db()
    print('\n' + '='*55)
    print('  Co-op Support Application')
    print('='*55)
    print('  URL:  http://localhost:5000')
    print('  Apply: http://localhost:5000/apply')
    print()
    print('  Coordinator Login')
    print('    Email:    coordinator@coop.com')
    print('    Password: admin123')
    print()
    print('  Employer Registration: http://localhost:5000/employer/register')
    print('='*55 + '\n')
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
