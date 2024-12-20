from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import time
import threading
import pytz
import random
import string
from werkzeug.utils import secure_filename

# إعدادات التطبيق
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# تعيين المنطقة الزمنية للسعودية
TIMEZONE = pytz.timezone('Asia/Riyadh')

# إعدادات قاعدة البيانات
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# مجلد الملفات المرفقة
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# إعدادات البريد الإلكتروني
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'a07516213@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'hwto mlld swtf bxcm')

# تهيئة المكونات
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
bcrypt = Bcrypt(app)

# تعريف النماذج (Models)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    phone = db.Column(db.String(20))
    email_notifications = db.Column(db.Boolean, default=True)
    tasks = db.relationship('Task', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    due_date = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(20))
    attachment = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reminders = db.relationship('TaskReminder', backref='task')

    def format_created_at(self):
        # تحويل التوقيت إلى المنطقة الزمنية للسعودية
        if self.created_at.tzinfo is None:
            aware_date = pytz.UTC.localize(self.created_at)
        else:
            aware_date = self.created_at
        local_time = aware_date.astimezone(TIMEZONE)
        return local_time.strftime('%Y/%m/%d %H:%M:%S')

    def format_due_date(self):
        if not self.due_date:
            return "لا يوجد موعد"
        
        # تحويل الوقت الحالي والموعد النهائي إلى UTC
        now = datetime.now(pytz.UTC)
        if self.due_date.tzinfo is None:
            due_date = pytz.UTC.localize(self.due_date)
        else:
            due_date = self.due_date
        
        time_left = due_date - now
        
        if time_left.total_seconds() <= 0:
            return "انتهى الوقت"
        
        days = time_left.days
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        
        if days > 0:
            return f"متبقي {days} يوم و {hours} ساعة"
        elif hours > 0:
            return f"متبقي {hours} ساعة و {minutes} دقيقة"
        else:
            return f"متبقي {minutes} دقيقة"

class TaskReminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    reminder_time = db.Column(db.DateTime, nullable=False)
    reminder_type = db.Column(db.String(20), nullable=False)  # 'week', 'two_days', 'five_hours', 'ten_minutes', 'one_minute'
    sent = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# إنشاء المجلدات المطلوبة
if not os.path.exists('instance'):
    os.makedirs('instance')

def send_email(to_email, subject, body):
    try:
        msg = Message(subject,
                     sender=app.config['MAIL_USERNAME'],
                     recipients=[to_email])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_notification(user, message):
    """إرسال الإشعارات عبر البريد الإلكتروني فقط"""
    if user.email_notifications:
        return send_email(user.email, "إشعار من نظام إدارة المهام", message)
    return False

def send_task_notification(task):
    """إرسال إشعار للمستخدم عن المهمة"""
    user = task.user
    if user.email_notifications:
        message = f"""
        تم إنشاء مهمة جديدة:
        العنوان: {task.title}
        الوصف: {task.description}
        تاريخ الاستحقاق: {task.format_due_date()}
        """
        return send_email(user.email, "مهمة جديدة - نظام إدارة المهام", message)
    return False

def create_task_reminders(task):
    """إنشاء تنبيهات للمهمة"""
    if task.due_date:
        # التنبيهات قبل الموعد النهائي
        reminders = [
            ('week', timedelta(days=7)),
            ('two_days', timedelta(days=2)),
            ('five_hours', timedelta(hours=5)),
            ('ten_minutes', timedelta(minutes=10)),
            ('one_minute', timedelta(minutes=1))
        ]
        
        for reminder_type, time_before in reminders:
            reminder_time = task.due_date - time_before
            # إنشاء تنبيه فقط إذا كان الوقت لم يمر بعد
            if reminder_time > datetime.now(pytz.UTC):
                reminder = TaskReminder(
                    task_id=task.id,
                    reminder_type=reminder_type,
                    reminder_time=reminder_time
                )
                db.session.add(reminder)
        
        try:
            db.session.commit()
        except Exception as e:
            app.logger.error(f'خطأ في إنشاء التنبيهات: {str(e)}')
            db.session.rollback()

def send_reminder_notification(reminder):
    """إرسال تنبيه للمستخدم"""
    task = reminder.task
    user = task.user
    
    if user.email_notifications:
        time_left = task.format_due_date()
        message = f"""
        تذكير بموعد المهمة:
        العنوان: {task.title}
        الوصف: {task.description}
        الوقت المتبقي: {time_left}
        """
        return send_email(user.email, "تذكير بموعد المهمة - نظام إدارة المهام", message)
    return False

def check_and_send_reminders():
    """التحقق من التنبيهات وإرسالها"""
    try:
        # البحث عن التنبيهات التي حان وقتها ولم يتم إرسالها بعد
        current_time = datetime.now(pytz.UTC)
        due_reminders = TaskReminder.query.filter(
            TaskReminder.reminder_time <= current_time,
            TaskReminder.sent == False
        ).all()

        for reminder in due_reminders:
            if send_reminder_notification(reminder):
                reminder.sent = True
                db.session.commit()
    except Exception as e:
        app.logger.error(f'خطأ في إرسال التنبيهات: {str(e)}')

# حذف وإعادة إنشاء قاعدة البيانات
with app.app_context():
    db.drop_all()
    db.create_all()

# الملفات المسموح بها
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        email_notifications = 'email_notifications' in request.form
        
        # التحقق من عدم وجود المستخدم
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مستخدم بالفعل')
            return redirect(url_for('register'))
        
        # إنشاء مستخدم جديد
        user = User(
            username=username,
            email=email,
            phone=phone,
            email_notifications=email_notifications
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # إرسال بريد ترحيب
            if email_notifications:
                msg = Message('مرحباً بك في تطبيق إدارة المهام',
                            sender=app.config['MAIL_USERNAME'],
                            recipients=[email])
                msg.body = f'''مرحباً {username}،

شكراً لتسجيلك في تطبيق إدارة المهام. يمكنك الآن:
- إضافة مهام جديدة
- تتبع مواعيد المهام
- رفع المرفقات
- استلام إشعارات عبر البريد الإلكتروني

نتمنى لك تجربة ممتعة!
'''
                mail.send(msg)
            
            flash('تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'خطأ في التسجيل: {str(e)}')
            flash('حدث خطأ أثناء التسجيل. الرجاء المحاولة مرة أخرى')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False) == 'on'
        
        user = User.query.filter(
            (User.username == username) | 
            (User.email == username) | 
            (User.phone == username)
        ).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        email_notifications = 'email_notifications' in request.form
        phone = request.form.get('phone')
        
        try:
            current_user.email_notifications = email_notifications
            current_user.phone = phone
            db.session.commit()
            flash('تم تحديث المعلومات الشخصية بنجاح')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'خطأ في تحديث المعلومات الشخصية: {str(e)}')
            flash('حدث خطأ أثناء تحديث المعلومات')
    
    return render_template('profile.html')

@app.route('/')
@login_required
def index():
    now = datetime.now(TIMEZONE)
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template('index.html', tasks=tasks, now=now)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        
        # تحويل التاريخ والوقت إلى المنطقة الزمنية للسعودية
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            try:
                # تحويل التاريخ والوقت المدخل إلى كائن datetime مع المنطقة الزمنية
                naive_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                due_date = TIMEZONE.localize(naive_date)
                # تحويل إلى UTC للتخزين في قاعدة البيانات
                due_date = due_date.astimezone(pytz.UTC)
            except ValueError as e:
                app.logger.error(f'خطأ في تحويل التاريخ: {str(e)}')
                flash('صيغة التاريخ غير صحيحة', 'error')
                return redirect(url_for('index'))
        
        # معالجة المرفق
        attachment_filename = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash('نوع الملف غير مسموح به')
                    return redirect(url_for('index'))
                
                filename = secure_filename(file.filename)
                timestamp = datetime.now(TIMEZONE).strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    if os.path.exists(file_path):
                        attachment_filename = filename
                    else:
                        flash('حدث خطأ أثناء حفظ الملف')
                        return redirect(url_for('index'))
                except Exception as e:
                    app.logger.error(f'خطأ في حفظ الملف: {str(e)}')
                    flash('حدث خطأ أثناء حفظ الملف')
                    return redirect(url_for('index'))

        try:
            # إنشاء المهمة مع created_at في UTC
            task = Task(
                title=title,
                description=description,
                due_date=due_date,
                priority=priority,
                attachment=attachment_filename,
                user_id=current_user.id,
                created_at=datetime.now(pytz.UTC)
            )
            
            db.session.add(task)
            db.session.commit()
            
            # إنشاء التنبيهات للمهمة
            if due_date:
                create_task_reminders(task)
            
            # إرسال إشعار بالبريد
            send_task_notification(task)
            
            flash('تم إضافة المهمة بنجاح')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'خطأ في حفظ المهمة: {str(e)}')
            flash('حدث خطأ أثناء حفظ المهمة')
            if attachment_filename:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], attachment_filename))
                except:
                    pass
        
        return redirect(url_for('index'))
    
    return render_template('index.html')

@app.route('/update_status/<int:task_id>', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({'error': 'غير مصرح'}), 403
    
    new_status = request.form.get('status')
    task.status = new_status
    db.session.commit()
    
    if new_status == 'completed':
        send_notification(current_user, f"تهانينا! لقد أكملت المهمة: {task.title}")
    
    return jsonify({'success': True})

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('غير مصرح لك بحذف هذه المهمة')
        return redirect(url_for('index'))
    
    if task.attachment:
        try:
            os.remove(os.path.join(app.static_folder, task.attachment))
        except:
            pass
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))

def start_reminder_scheduler():
    def run_scheduler():
        while True:
            with app.app_context():
                check_and_send_reminders()
            time.sleep(60)  # انتظار دقيقة واحدة
    
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

# تشغيل جدولة التنبيهات عند بدء التطبيق
if __name__ == '__main__':
    start_reminder_scheduler()
    app.run(debug=True, port=8080)
