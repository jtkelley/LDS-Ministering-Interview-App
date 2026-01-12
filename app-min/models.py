"""
Database models for the Ministering Interview application (minimal - no SMS).
"""
from flask_sqlalchemy import SQLAlchemy
from flask_user import UserMixin
from datetime import datetime
import secrets

# Database instance will be initialized in app.py
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'interviewer'
    active = db.Column(db.Boolean(), nullable=False, default=True)
    email_confirmed_at = db.Column(db.DateTime())


class UserInvitation(db.Model):
    """User invitation tokens for new user registration"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    token = db.Column(db.String(64), nullable=False, unique=True)
    role = db.Column(db.String(20), nullable=False, default='interviewer')  # 'admin' or 'interviewer'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime)
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_used = db.Column(db.Boolean, default=False)


class SystemConfig(db.Model):
    """System configuration for email settings (SMS removed in minimal version)"""
    id = db.Column(db.Integer, primary_key=True)

    # Email settings
    mail_server = db.Column(db.String(255), default='localhost')
    mail_port = db.Column(db.Integer, default=1025)
    mail_use_tls = db.Column(db.Boolean, default=False)
    mail_username = db.Column(db.String(255))  # Will be encrypted
    mail_password = db.Column(db.Text)  # Encrypted
    mail_from_email = db.Column(db.String(255))
    mail_from_name = db.Column(db.String(255), default='Ministering Interview App')

    # Automated reminder scheduler settings
    reminder_enabled = db.Column(db.Boolean, nullable=False, default=True)
    reminder_day_of_week = db.Column(db.Integer, nullable=False, default=0)  # 0=Monday, 6=Sunday
    reminder_hour = db.Column(db.Integer, nullable=False, default=9)  # 0-23
    reminder_minute = db.Column(db.Integer, nullable=False, default=0)  # 0-59

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def encrypt_fields(self):
        """Encrypt sensitive fields before saving"""
        from utils import EncryptionHelper

        if self.mail_username:
            self.mail_username = EncryptionHelper.encrypt(self.mail_username)
        if self.mail_password:
            self.mail_password = EncryptionHelper.encrypt(self.mail_password)

    def decrypt_fields(self):
        """Decrypt sensitive fields when retrieving"""
        from utils import EncryptionHelper

        return {
            'mail_server': self.mail_server,
            'mail_port': self.mail_port,
            'mail_use_tls': self.mail_use_tls,
            'mail_username': EncryptionHelper.decrypt(self.mail_username) if self.mail_username else '',
            'mail_password': EncryptionHelper.decrypt(self.mail_password) if self.mail_password else '',
            'mail_from_email': self.mail_from_email,
            'mail_from_name': self.mail_from_name,
            'reminder_enabled': self.reminder_enabled,
            'reminder_day_of_week': self.reminder_day_of_week,
            'reminder_hour': self.reminder_hour,
            'reminder_minute': self.reminder_minute,
        }


class District(db.Model):
    """District organizational unit with an interviewer"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    interviewer_name = db.Column(db.String(100), nullable=False)
    companionships = db.relationship('Companionship', backref='district', lazy=True)


class Companionship(db.Model):
    """Companionship within a district"""
    __tablename__ = 'companionship'
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    members = db.relationship('Member', backref='companionship', lazy=True)


class Member(db.Model):
    """Individual member with unique scheduling token"""
    id = db.Column(db.Integer, primary_key=True)
    companionship_id = db.Column(db.Integer, db.ForeignKey('companionship.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_hex(16))

    def has_booking_for_quarter(self, quarter, year=None):
        """Check if member has a booking for the specified quarter"""
        if year is None:
            year = datetime.now().year
        bookings = Booking.query.filter_by(member_id=self.id).join(InterviewSlot).filter(
            InterviewSlot.quarter == quarter,
            db.extract('year', InterviewSlot.date) == year
        ).first()
        return bookings is not None


class InterviewSlot(db.Model):
    """Available interview time slot with capacity"""
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    max_slots = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.Integer, nullable=False, default=0)  # Auto-calculated
    bookings = db.relationship('Booking', backref='slot', lazy=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.date:
            self.quarter = ((self.date.month - 1) // 3) + 1


class Booking(db.Model):
    """Interview booking linking member to slot"""
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('interview_slot.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    interview_type = db.Column(db.String(20), nullable=False, default='in-person')
    member = db.relationship('Member', backref='bookings')


class NotificationLog(db.Model):
    """Track when notifications are sent to members"""
    __tablename__ = 'notification_log'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    member = db.relationship('Member', backref='notifications')
    method = db.Column(db.String(10), nullable=False)  # 'email' only in minimal version
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    quarter = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    success = db.Column(db.Boolean, nullable=False, default=True)
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<NotificationLog {self.member.name if self.member else "Unknown"} - {self.method} - Q{self.quarter} {self.year}>'
