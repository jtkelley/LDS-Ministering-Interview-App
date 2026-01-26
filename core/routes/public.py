"""
Public and member-facing routes for the Ministering Interview application.
These routes do not require admin authentication.
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, current_app
from flask_user import current_user
from datetime import datetime
from sqlalchemy import func

from core.models import db, User, UserInvitation, District, Member, InterviewSlot, Booking, Companionship, MessageTemplates
from core.shared import mail

# Create blueprint (no URL prefix - these are root-level routes)
public_bp = Blueprint('public', __name__)


@public_bp.route('/favicon.ico')
def favicon():
    return send_from_directory(current_app.static_folder, 'favicon.ico')


@public_bp.route('/login_redirect')
def login_redirect():
    """Custom login redirect handler based on user role"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:
            # For non-admin users, redirect to home or show access denied
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('public.index'))
    else:
        return redirect(url_for('user.login'))


@public_bp.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    """Initial admin account setup - only accessible when no admin exists"""
    from flask import current_app

    # Only allow if no admin exists
    if User.query.filter_by(role='admin').first():
        return redirect(url_for('user.login'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate required fields
        if not email or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return redirect(url_for('public.setup_admin'))

        # Check password match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('public.setup_admin'))

        # Check minimum password length
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('public.setup_admin'))

        # Check password length (Werkzeug limit is 72 bytes)
        if len(password.encode('utf-8')) > 72:
            flash('Password must be 72 bytes or less. Please choose a shorter password.', 'error')
            return redirect(url_for('public.setup_admin'))

        # Let Flask-User handle password hashing
        user_manager = current_app.user_manager
        user = User(
            email=email,
            password=user_manager.hash_password(password),
            role='admin',
            active=True,
            email_confirmed_at=datetime.now()
        )
        db.session.add(user)
        db.session.commit()
        flash('Admin account created successfully! Please log in.', 'success')
        return redirect(url_for('user.login'))

    return render_template('setup_admin.html')


@public_bp.route('/clear-session')
def clear_session():
    """Utility route to clear session (for debugging)"""
    session.clear()
    flash('Session cleared. Please log in again.')
    return redirect(url_for('public.index'))


@public_bp.route('/')
def index():
    """Landing page - redirects based on authentication status"""
    # If already logged in, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin'))
        else:  # interviewer
            return redirect(url_for('public.interviewer_dashboard'))

    # Check if any admin exists
    admin_exists = User.query.filter_by(role='admin').first()
    # If no admin, show setup admin form
    if not admin_exists:
        return redirect(url_for('public.setup_admin'))
    # Otherwise, redirect to login
    return redirect(url_for('user.login'))


@public_bp.route('/dashboard')
def interviewer_dashboard():
    """Dashboard for interviewers - shows their interview calendar"""
    # Require login
    if not current_user.is_authenticated:
        return redirect(url_for('user.login', next=request.path))

    # Interviewers can access their calendar
    # Admin can also access this if they want

    # Get all districts
    today = datetime.now().date()
    current_month = today.month
    current_quarter = ((current_month - 1) // 3) + 1

    districts = District.query.all()
    district_slots = {}

    # Get slots for the current and future quarters only
    for district in districts:
        slots = InterviewSlot.query.filter_by(district_id=district.id)\
            .filter(InterviewSlot.date >= today)\
            .order_by(InterviewSlot.date, InterviewSlot.start_time).all()
        district_slots[district.id] = slots

    return render_template('interviewer_dashboard.html', districts=districts, district_slots=district_slots)


@public_bp.route('/user/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    """Accept user invitation and create account"""
    from flask import current_app

    invitation = UserInvitation.query.filter_by(token=token, is_used=False).first_or_404()

    # Check if invitation has expired
    if invitation.expires_at < datetime.now():
        flash('This invitation has expired. Please contact an administrator for a new one.', 'error')
        return redirect(url_for('public.index'))

    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if not password:
            flash('Password is required.', 'error')
            return redirect(url_for('public.accept_invitation', token=token))

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('public.accept_invitation', token=token))

        try:
            # Check password length
            if len(password.encode('utf-8')) > 72:
                flash('Password must be 72 bytes or less.', 'error')
                return redirect(url_for('public.accept_invitation', token=token))

            # Create user account
            user_manager = current_app.user_manager
            user = User(
                email=invitation.email,
                password=user_manager.hash_password(password),
                role=invitation.role,
                active=True,
                email_confirmed_at=datetime.now()
            )
            db.session.add(user)
            db.session.flush()  # Get the user ID

            # Mark invitation as used
            invitation.is_used = True
            invitation.accepted_at = datetime.now()
            invitation.accepted_by_user_id = user.id

            db.session.commit()

            flash('Account created successfully! Please log in with your credentials.', 'success')
            return redirect(url_for('user.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('public.accept_invitation', token=token))

    return render_template('accept_invitation.html', email=invitation.email, expires_at=invitation.expires_at)


@public_bp.route('/schedule/<token>')
def schedule(token):
    """Member scheduling interface"""
    member = Member.query.filter_by(token=token).first_or_404()
    district = member.companionship.district
    today = datetime.now().date()

    # Calculate current and next quarter
    current_quarter = ((datetime.now().month - 1) // 3) + 1
    current_year = datetime.now().year
    next_quarter = current_quarter + 1 if current_quarter < 4 else 1
    next_year = current_year if current_quarter < 4 else current_year + 1

    # Get target quarter from URL params (default to current)
    target_quarter = request.args.get('q', type=int, default=current_quarter)
    target_year = request.args.get('y', type=int, default=current_year)

    # Validate: only allow current or next quarter
    valid_quarters = [
        (current_quarter, current_year),
        (next_quarter, next_year)
    ]
    if (target_quarter, target_year) not in valid_quarters:
        target_quarter = current_quarter
        target_year = current_year

    # Check which quarters have slots for this district
    current_quarter_has_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.quarter == current_quarter,
        func.extract('year', InterviewSlot.date) == current_year,
        InterviewSlot.date >= today
    ).first() is not None

    next_quarter_has_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.quarter == next_quarter,
        func.extract('year', InterviewSlot.date) == next_year
    ).first() is not None

    # Find member's UPCOMING booking for target quarter
    my_booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == target_quarter,
        func.extract('year', InterviewSlot.date) == target_year,
        InterviewSlot.date >= today
    ).first()

    # Find member's PAST booking for target quarter
    past_booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == target_quarter,
        func.extract('year', InterviewSlot.date) == target_year,
        InterviewSlot.date < today
    ).first()

    # Find if any companion has already booked a slot (upcoming)
    companion_booking = None
    past_companion_booking = None
    if member.companionship:
        for companionship_member in member.companionship.members:
            if companionship_member.id != member.id:
                # Check for upcoming booking
                booking = Booking.query.join(InterviewSlot).filter(
                    Booking.member_id == companionship_member.id,
                    InterviewSlot.quarter == target_quarter,
                    func.extract('year', InterviewSlot.date) == target_year,
                    InterviewSlot.date >= today
                ).first()
                if booking and not companion_booking:
                    companion_booking = {
                        'slot': booking.slot,
                        'companion_name': companionship_member.name
                    }

                # Check for past booking
                past = Booking.query.join(InterviewSlot).filter(
                    Booking.member_id == companionship_member.id,
                    InterviewSlot.quarter == target_quarter,
                    func.extract('year', InterviewSlot.date) == target_year,
                    InterviewSlot.date < today
                ).first()
                if past and not past_companion_booking:
                    past_companion_booking = {
                        'slot': past.slot,
                        'companion_name': companionship_member.name
                    }

    # Get all slots for this district and target quarter
    all_slots = InterviewSlot.query.filter_by(district_id=district.id).filter(
        InterviewSlot.date >= today,
        InterviewSlot.quarter == target_quarter,
        func.extract('year', InterviewSlot.date) == target_year
    ).order_by(InterviewSlot.date, InterviewSlot.start_time).all()

    # Filter to only show slots that are available to book, but always include:
    # 1. The member's own booked slot (if they have one)
    # 2. The companion's booked slot (if companion has one)
    available_slots = []
    for slot in all_slots:
        # Check if slot is full
        is_full = len(slot.bookings) >= slot.max_slots

        # Check if slot is reserved for another companionship
        is_reserved_for_other = False
        if slot.bookings:
            # If slot has bookings, check if they're from a different companionship
            existing_companionship = slot.bookings[0].member.companionship
            if member.companionship != existing_companionship:
                is_reserved_for_other = True

        # Slot is available if it's not full and not reserved for another companionship
        is_available = not is_full and not is_reserved_for_other

        # Always show member's own slot and companion's slot
        is_my_slot = my_booking and my_booking.slot.id == slot.id
        is_companion_slot = companion_booking and companion_booking['slot'].id == slot.id

        if is_available or is_my_slot or is_companion_slot:
            available_slots.append(slot)

    # Get custom instructions from message templates
    msg_config = MessageTemplates.get_or_create()
    custom_instructions = msg_config.custom_instructions if msg_config else None

    return render_template('schedule.html',
        member=member,
        slots=available_slots,
        companion_booking=companion_booking,
        my_booking=my_booking,
        past_booking=past_booking,
        past_companion_booking=past_companion_booking,
        custom_instructions=custom_instructions,
        target_quarter=target_quarter,
        target_year=target_year,
        current_quarter=current_quarter,
        current_year=current_year,
        next_quarter=next_quarter,
        next_year=next_year,
        current_quarter_has_slots=current_quarter_has_slots,
        next_quarter_has_slots=next_quarter_has_slots
    )


@public_bp.route('/book/<int:slot_id>/<token>', methods=['POST'])
def book_slot(slot_id, token):
    """Book an interview slot"""
    member = Member.query.filter_by(token=token).first_or_404()
    slot = InterviewSlot.query.get_or_404(slot_id)
    interview_type = request.form.get('interview_type', 'in-person')

    # Get quarter params to preserve in redirect
    target_quarter = request.form.get('q', type=int) or request.args.get('q', type=int)
    target_year = request.form.get('y', type=int) or request.args.get('y', type=int)

    # Use the slot's quarter for validation
    slot_quarter = slot.quarter
    slot_year = slot.date.year

    # Check if member already has an upcoming booking for this slot's quarter
    existing_quarter_booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == slot_quarter,
        func.extract('year', InterviewSlot.date) == slot_year,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    redirect_params = {'token': token}
    if target_quarter:
        redirect_params['q'] = target_quarter
    if target_year:
        redirect_params['y'] = target_year

    if existing_quarter_booking:
        flash('You already have a booking for this quarter. Please cancel it first if you want to book a different time.', 'warning')
        return redirect(url_for('public.schedule', **redirect_params))

    # Check if already booked for this specific slot (shouldn't happen with above check, but keep as safety)
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash('You are already booked for this slot.')
        return redirect(url_for('public.schedule', **redirect_params))

    # Check companionship restriction
    if slot.bookings:
        existing_companionship = slot.bookings[0].member.companionship
        if member.companionship != existing_companionship:
            flash('This slot is reserved for another companionship.')
            return redirect(url_for('public.schedule', **redirect_params))

    if len(slot.bookings) < slot.max_slots:
        booking = Booking(slot_id=slot_id, member_id=member.id, interview_type=interview_type)
        db.session.add(booking)
        db.session.commit()
        flash('Slot booked successfully!', 'success')
    else:
        flash('Slot is full.', 'error')

    return redirect(url_for('public.schedule', **redirect_params))


@public_bp.route('/unbook/<token>', methods=['POST'])
def unbook_slot(token):
    """Cancel an interview booking"""
    member = Member.query.filter_by(token=token).first_or_404()

    # Get quarter params from form or URL
    target_quarter = request.form.get('q', type=int) or request.args.get('q', type=int)
    target_year = request.form.get('y', type=int) or request.args.get('y', type=int)

    # Default to current quarter if not specified
    if not target_quarter:
        target_quarter = ((datetime.now().month - 1) // 3) + 1
    if not target_year:
        target_year = datetime.now().year

    # Find member's current booking for the target quarter
    booking = Booking.query.join(InterviewSlot).filter(
        Booking.member_id == member.id,
        InterviewSlot.quarter == target_quarter,
        func.extract('year', InterviewSlot.date) == target_year,
        InterviewSlot.date >= datetime.now().date()
    ).first()

    redirect_params = {'token': token}
    if target_quarter:
        redirect_params['q'] = target_quarter
    if target_year:
        redirect_params['y'] = target_year

    if booking:
        db.session.delete(booking)
        db.session.commit()
        flash('Your booking has been cancelled. You can now book a different time slot.', 'success')
    else:
        flash('No booking found to cancel.', 'error')

    return redirect(url_for('public.schedule', **redirect_params))
