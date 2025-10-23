from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import os
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func
from twilio_config import twilio_client, twilio_number
import secrets
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time
import uuid
import threading

# Global thread-safe storage for progress data
progress_store = {}
progress_lock = threading.Lock()

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interviews.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration (update with your SMTP settings)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

db = SQLAlchemy(app)
mail = Mail(app)

# Database Models
class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    interviewer_name = db.Column(db.String(100), nullable=False)
    teams = db.relationship('Team', backref='district', lazy=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    members = db.relationship('Member', backref='team', lazy=True)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_hex(16))

class InterviewSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    max_slots = db.Column(db.Integer, nullable=False)
    bookings = db.relationship('Booking', backref='slot', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('interview_slot.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    member = db.relationship('Member', backref='bookings')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    today = datetime.now().date()
    selected_district_id = request.args.get('district', type=int)
    
    if selected_district_id:
        districts = District.query.filter_by(id=selected_district_id).all()
    else:
        districts = District.query.all()
    
    district_slots = {}
    for district in districts:
        slots = InterviewSlot.query.filter_by(district_id=district.id).filter(InterviewSlot.date >= today).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
        district_slots[district.id] = slots
    
    all_districts = District.query.all()  # For the filter dropdown
    return render_template('admin_calendar.html', districts=districts, district_slots=district_slots, all_districts=all_districts, selected_district_id=selected_district_id)

@app.route('/admin/districts')
def manage_districts():
    districts = District.query.all()
    return render_template('admin.html', districts=districts)

@app.route('/admin/scrape', methods=['GET', 'POST'])
def scrape_data():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('scrape_data'))
        
        # Run scraping in a thread to avoid blocking
        progress_id = str(uuid.uuid4())
        with progress_lock:
            progress_store[progress_id] = {
                'status': 'running',
                'message': 'Initializing scraper...',
                'step': 0,
                'total_steps': 10,
                'companionships_found': 0,
                'members_found': 0,
                'errors': []
            }
        
        def run_scrape():
            try:
                # Import the scraper module
                from app_scraper import scrape_ministering_data

                def progress_callback(message):
                    # Update progress store with the message
                    with progress_lock:
                        progress_store[progress_id]['message'] = message
                        # Try to extract step information from message
                        if 'Step' in message:
                            try:
                                step_num = int(message.split('Step')[1].split(':')[0].strip())
                                progress_store[progress_id]['step'] = step_num
                            except:
                                pass
                        
                        # Check if this is an error message and add to errors list
                        if message.startswith('❌') or message.startswith('[ERROR]') or 'Error' in message or 'Failed' in message:
                            progress_store[progress_id]['errors'].append(message)
                            progress_store[progress_id]['status'] = 'error'
                        else:
                            progress_store[progress_id]['status'] = 'running'

                # Run the scraper
                results = scrape_ministering_data(username, password, progress_callback)

                if results:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'completed'
                        progress_store[progress_id]['message'] = 'Scraping completed'
                        progress_store[progress_id]['step'] = 10
                        progress_store[progress_id]['districts_found'] = len(set(row['district'] for row in results))
                        progress_store[progress_id]['companionships_found'] = len(set(row['companionship_id'] for row in results))
                        progress_store[progress_id]['members_found'] = len(results)
                        progress_store[progress_id]['scraped_districts'] = group_results_by_district(results)
                        progress_store[progress_id]['raw_results'] = results  # Store raw results for CSV download
                else:
                    with progress_lock:
                        progress_store[progress_id]['status'] = 'error'
                        # Check if we have any error messages from the progress callback
                        if progress_store[progress_id]['errors']:
                            progress_store[progress_id]['message'] = 'Scraping failed - check errors below'
                        else:
                            progress_store[progress_id]['message'] = 'Scraping failed - no data returned'
                            progress_store[progress_id]['errors'].append('Scraper returned no data. Check credentials and network connection.')

            except Exception as e:
                with progress_lock:
                    progress_store[progress_id]['status'] = 'error'
                    progress_store[progress_id]['message'] = str(e)
                    progress_store[progress_id]['errors'].append(str(e))
        
        thread = threading.Thread(target=run_scrape)
        thread.start()
        
        return redirect(url_for('scrape_progress', progress_id=progress_id))
    
    return render_template('scrape.html')

@app.route('/admin/scrape_progress/<progress_id>')
def scrape_progress(progress_id):
    return render_template('scrape_progress.html', progress_id=progress_id)

@app.route('/admin/download_csv/<progress_id>')
def download_csv(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)
    
    if not progress_data or progress_data['status'] != 'completed':
        flash('No completed scrape data found.')
        return redirect(url_for('scrape_data'))
    
    raw_results = progress_data.get('raw_results')
    if not raw_results:
        flash('No raw data available for download.')
        return redirect(url_for('scrape_data'))
    
    # Create CSV in memory
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['district', 'interviewer', 'name', 'phone', 'email', 'companionship_id'])
    writer.writeheader()
    for row in raw_results:
        writer.writerow(row)
    
    # Create response
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='ministering_brothers.csv'
    )
    
    return response

@app.route('/admin/import_csv', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected.')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected.')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('File must be a CSV.')
            return redirect(request.url)
        
        try:
            import csv
            import io
            
            # Read the CSV content
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)
            results = list(reader)
            
            # Group by district and companionship_id
            from collections import defaultdict
            districts_data = defaultdict(lambda: {'companionships': defaultdict(list)})
            for row in results:
                district_name = row['district']
                interviewer = row['interviewer']
                comp_id = row['companionship_id']
                districts_data[district_name]['interviewer'] = interviewer
                districts_data[district_name]['companionships'][comp_id].append({
                    'name': row['name'],
                    'phone': row['phone'],
                    'email': row['email']
                })
            
            scraped_districts = []
            for district_name, data in districts_data.items():
                companionships = []
                for comp_id, members in data['companionships'].items():
                    companionships.append({
                        'companionship_id': comp_id,
                        'members': members
                    })
                scraped_districts.append({
                    'name': district_name,
                    'interviewer': data['interviewer'],
                    'companionships': companionships
                })
            
            # Store in session for confirmation
            session['uploaded_districts'] = scraped_districts
            return redirect(url_for('import_csv_confirm'))
        
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}')
            return redirect(request.url)
    
    return render_template('import_csv.html')
def send_all_notifications():
    districts = District.query.all()
    total_sent = 0
    for district in districts:
        for team in district.teams:
            for member in team.members:
                link = url_for('schedule', token=member.token, _external=True)
                if member.email:
                    msg = Message('Interview Scheduling', sender=app.config['MAIL_USERNAME'], 
                                recipients=[member.email])
                    msg.body = f'Please schedule your interview: {link}'
                    mail.send(msg)
                    total_sent += 1
                if member.phone and twilio_client:
                    twilio_client.messages.create(body=f'Interview link: {link}', from_=twilio_number, to=member.phone)
                    total_sent += 1
    flash(f'Notifications sent to {total_sent} contacts!')
    return redirect(url_for('admin'))

@app.route('/admin/district/new', methods=['GET', 'POST'])
def new_district():
    if request.method == 'POST':
        name = request.form['name']
        interviewer = request.form['interviewer']
        district = District(name=name, interviewer_name=interviewer)
        db.session.add(district)
        db.session.commit()
        flash('District created successfully!')
        return redirect(url_for('admin'))
    return render_template('new_district.html')

@app.route('/admin/district/<int:id>')
def district_detail(id):
    district = District.query.get_or_404(id)
    return render_template('district_detail.html', district=district)

@app.route('/admin/district/<int:id>/team/new', methods=['GET', 'POST'])
def new_team(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        team = Team(district_id=id)
        db.session.add(team)
        db.session.commit()
        
        # Handle existing members
        existing_member_ids = request.form.getlist('existing_members[]')
        for member_id in existing_member_ids:
            member = Member.query.get(int(member_id))
            if member and member.team.district_id == id:
                # Cancel existing bookings
                bookings = Booking.query.filter_by(member_id=member.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                # Reassign to new team
                member.team_id = team.id
        
        # Add new members
        member_names = request.form.getlist('member_name[]')
        member_phones = request.form.getlist('member_phone[]')
        member_emails = request.form.getlist('member_email[]')
        
        for name, phone, email in zip(member_names, member_phones, member_emails):
            if name:  # Only require name
                member = Member(team_id=team.id, name=name, phone=phone, email=email)
                db.session.add(member)
        
        db.session.commit()
        flash('Companionship created successfully!')
        return redirect(url_for('district_detail', id=id))
    
    # Get existing members from all districts for reassignment
    existing_members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name, Member.name).all()
    return render_template('new_team.html', district=district, existing_members=existing_members)

@app.route('/admin/district/<int:id>/slots', methods=['GET', 'POST'])
def manage_slots(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        if 'day_of_week' in request.form:
            # Generate slots
            day_of_week = int(request.form['day_of_week'])
            start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
            duration = int(request.form['duration'])
            num_slots = int(request.form['num_slots'])
            weeks_ahead = int(request.form['weeks_ahead'])
            
            # Find the next occurrence of the day
            today = datetime.now().date()
            days_ahead = (day_of_week - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week if today is the day
            next_date = today + timedelta(days=days_ahead)
            
            # Generate slots for the next weeks_ahead weeks
            for i in range(weeks_ahead):
                slot_date = next_date + timedelta(weeks=i)
                for j in range(num_slots):
                    slot_time = (datetime.combine(slot_date, start_time) + timedelta(minutes=duration * j)).time()
                    slot = InterviewSlot(district_id=id, date=slot_date, start_time=slot_time, 
                                       duration=duration, max_slots=10)  # Allow up to 10 members per slot
                    db.session.add(slot)
            
            db.session.commit()
            flash(f'Generated {weeks_ahead * num_slots} recurring slots!')
            return redirect(url_for('manage_slots', id=id))
        elif request.form.get('action') == 'delete_all':
            # Delete all slots for this district
            slots = InterviewSlot.query.filter_by(district_id=id).all()
            for slot in slots:
                bookings = Booking.query.filter_by(slot_id=slot.id).all()
                for booking in bookings:
                    db.session.delete(booking)
                db.session.delete(slot)
            db.session.commit()
            flash('All slots deleted!')
            return redirect(url_for('manage_slots', id=id))
        elif request.form.get('action') == 'delete_selected':
            # Delete selected slots
            slot_ids = request.form.getlist('slot_ids')
            for slot_id in slot_ids:
                slot = InterviewSlot.query.get(int(slot_id))
                if slot and slot.district_id == id:
                    bookings = Booking.query.filter_by(slot_id=slot.id).all()
                    for booking in bookings:
                        db.session.delete(booking)
                    db.session.delete(slot)
            db.session.commit()
            flash(f'Deleted {len(slot_ids)} slots!')
            return redirect(url_for('manage_slots', id=id))
    
    slots = InterviewSlot.query.filter_by(district_id=id).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('manage_slots.html', district=district, slots=slots)

@app.route('/schedule/<token>')
def schedule(token):
    member = Member.query.filter_by(token=token).first_or_404()
    district = member.team.district
    available_slots = InterviewSlot.query.filter_by(district_id=district.id).outerjoin(Booking).group_by(InterviewSlot.id).having(
        func.count(Booking.id) < InterviewSlot.max_slots).order_by(InterviewSlot.date, InterviewSlot.start_time).all()
    return render_template('schedule.html', member=member, slots=available_slots)

@app.route('/book/<int:slot_id>/<token>', methods=['POST'])
def book_slot(slot_id, token):
    member = Member.query.filter_by(token=token).first_or_404()
    slot = InterviewSlot.query.get_or_404(slot_id)
    
    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member.id).first()
    if existing:
        flash('You are already booked for this slot.')
        return redirect(url_for('schedule', token=token))
    
    # Check team restriction
    if slot.bookings:
        existing_team = slot.bookings[0].member.team
        if member.team != existing_team:
            flash('This slot is reserved for another team.')
            return redirect(url_for('schedule', token=token))
    
    if len(slot.bookings) < slot.max_slots:
        booking = Booking(slot_id=slot_id, member_id=member.id)
        db.session.add(booking)
        db.session.commit()
        flash('Slot booked successfully!')
    else:
        flash('Slot is full.')
    
    return redirect(url_for('schedule', token=token))

@app.route('/admin/send_notifications/<int:district_id>')
def send_notifications(district_id):
    district = District.query.get_or_404(district_id)
    slots = InterviewSlot.query.filter_by(district_id=district_id).all()
    
    for team in district.teams:
        for member in team.members:
            link = url_for('schedule', token=member.token, _external=True)
            # Send email
            if member.email:
                msg = Message('Interview Scheduling', sender=app.config['MAIL_USERNAME'], 
                            recipients=[member.email])
                msg.body = f'Please schedule your interview: {link}'
                mail.send(msg)
            # Send SMS (placeholder - integrate Twilio)
            if member.phone and twilio_client:
                twilio_client.messages.create(body=f'Interview link: {link}', from_=twilio_number, to=member.phone)
    
    flash('Notifications sent!')
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/add_booking/<int:slot_id>', methods=['POST'])
def add_booking(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    member_id = request.form['member_id']
    member = Member.query.get_or_404(member_id)
    
    # Check if already booked
    existing = Booking.query.filter_by(slot_id=slot_id, member_id=member_id).first()
    if existing:
        flash(f'{member.name} is already booked for this slot.')
    else:
        # Check team restriction
        if slot.bookings:
            existing_team = slot.bookings[0].member.team
            if member.team != existing_team:
                flash('This slot is reserved for another team.')
                return redirect(url_for('admin'))
        
        if len(slot.bookings) < slot.max_slots:
            booking = Booking(slot_id=slot_id, member_id=member_id)
            db.session.add(booking)
            db.session.commit()
            flash(f'Added {member.name} to the slot.')
        else:
            flash('Slot is full.')
    
    return redirect(url_for('admin'))

@app.route('/admin/remove_booking/<int:booking_id>', methods=['POST'])
def remove_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    slot = booking.slot
    member_name = booking.member.name
    db.session.delete(booking)
    db.session.commit()
    flash(f'Removed {member_name} from the slot.')
    return redirect(url_for('admin'))

@app.route('/admin/delete_slot/<int:slot_id>', methods=['POST'])
def delete_slot(slot_id):
    slot = InterviewSlot.query.get_or_404(slot_id)
    district_id = slot.district_id
    
    # Delete associated bookings first
    bookings = Booking.query.filter_by(slot_id=slot_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    db.session.delete(slot)
    db.session.commit()
    flash('Interview slot deleted successfully!')
    return redirect(url_for('manage_slots', id=district_id))

@app.route('/admin/team/<int:team_id>/add_member', methods=['GET', 'POST'])
def add_member(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Get all members from all districts for reassignment
    all_members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name, Member.name).all()
    
    if request.method == 'POST':
        # Check if reassigning an existing member or creating a new one
        existing_member_id = request.form.get('existing_member_id')
        
        if existing_member_id:
            # Reassign existing member to this team
            member = Member.query.get_or_404(existing_member_id)
            
            # Remove any existing bookings
            bookings = Booking.query.filter_by(member_id=member.id).all()
            for booking in bookings:
                db.session.delete(booking)
            
            # Reassign to new team
            old_team_id = member.team_id
            member.team_id = team_id
            db.session.commit()
            flash(f'Reassigned {member.name} to this companionship!')
            return redirect(url_for('district_detail', id=team.district_id))
        else:
            # Create new member
            name = request.form['name']
            phone = request.form.get('phone', '')
            email = request.form['email']
            if name and email:
                member = Member(team_id=team_id, name=name, phone=phone, email=email)
                db.session.add(member)
                db.session.commit()
                flash(f'Added {name} to companionship!')
                return redirect(url_for('district_detail', id=team.district_id))
    
    return render_template('add_member.html', team=team, all_members=all_members)

@app.route('/admin/unassign_member/<int:member_id>', methods=['POST'])
def unassign_member(member_id):
    member = Member.query.get_or_404(member_id)
    district_id = member.team.district_id if member.team else None
    
    # Cancel any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Unassign from team
    member.team_id = None
    db.session.commit()
    flash(f'Unassigned {member.name} from companionship!')
    
    if district_id:
        return redirect(url_for('district_detail', id=district_id))
    else:
        return redirect(url_for('manage_members'))

@app.route('/admin/remove_team/<int:team_id>', methods=['POST'])
def remove_team(team_id):
    team = Team.query.get_or_404(team_id)
    district_id = team.district_id
    name = f"Companionship {team.id}"
    
    # Remove all members and their bookings
    for member in team.members:
        bookings = Booking.query.filter_by(member_id=member.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(member)
    
    db.session.delete(team)
    db.session.commit()
    flash(f'{name} removed!')
    return redirect(url_for('district_detail', id=district_id))

@app.route('/admin/district/<int:id>/edit', methods=['GET', 'POST'])
def edit_district(id):
    district = District.query.get_or_404(id)
    if request.method == 'POST':
        district.name = request.form['name']
        district.interviewer_name = request.form['interviewer']
        db.session.commit()
        flash('District updated!')
        return redirect(url_for('district_detail', id=id))
    return render_template('edit_district.html', district=district)

@app.route('/admin/members')
def manage_members():
    """View and manage all members across all districts."""
    members = Member.query.outerjoin(Team).outerjoin(District).order_by(District.name.nulls_last(), Team.id.nulls_last(), Member.name).all()
    districts = District.query.all()
    return render_template('manage_members.html', members=members, districts=districts)

@app.route('/admin/member/<int:member_id>/reassign', methods=['POST'])
def reassign_member(member_id):
    """Reassign a member to a different companionship."""
    member = Member.query.get_or_404(member_id)
    new_team_id = request.form.get('new_team_id', type=int)
    
    if not new_team_id:
        flash('Please select a companionship.')
        return redirect(url_for('manage_members'))
    
    new_team = Team.query.get_or_404(new_team_id)
    old_team_id = member.team_id
    
    # Remove any existing bookings
    bookings = Booking.query.filter_by(member_id=member_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    # Reassign to new team
    member.team_id = new_team_id
    db.session.commit()
    
    flash(f'Reassigned {member.name} to Companionship {new_team_id} in {new_team.district.name}')
    return redirect(url_for('manage_members'))

@app.route('/admin/edit_member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.name = request.form['name']
        member.phone = request.form['phone']
        member.email = request.form['email']
        db.session.commit()
        flash(f'Updated {member.name}!')
        return redirect(url_for('district_detail', id=member.team.district_id))
    return render_template('edit_member.html', member=member)

def group_results_by_district(results):
    """Group scraping results by district for display."""
    from collections import defaultdict
    districts_data = defaultdict(lambda: {'companionships': defaultdict(list)})
    
    for row in results:
        district_name = row['district']
        interviewer = row['interviewer']
        comp_id = row['companionship_id']
        districts_data[district_name]['interviewer'] = interviewer
        districts_data[district_name]['companionships'][comp_id].append({
            'name': row['name'],
            'phone': row['phone'],
            'email': row['email']
        })
    
    scraped_districts = []
    for district_name, data in districts_data.items():
        companionships = []
        for comp_id, members in data['companionships'].items():
            companionships.append({
                'companionship_id': comp_id,
                'members': members
            })
        scraped_districts.append({
            'name': district_name,
            'interviewer': data['interviewer'],
            'companionships': companionships
        })
    
    return scraped_districts

@app.route('/admin/import_companionships', methods=['GET', 'POST'])
def import_companionships():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Initialize progress tracking
        progress_id = str(uuid.uuid4())
        progress_data = {
            'id': progress_id,
            'status': 'starting',
            'message': 'Setting up Chrome browser...',
            'step': 0,
            'total_steps': 8,
            'companionships_found': 0,
            'members_found': 0,
            'errors': []
        }
        
        with progress_lock:
            progress_store[progress_id] = progress_data
        
        # Start the scraping in a background thread
        from threading import Thread
        thread = Thread(target=perform_scraping, args=(username, password, progress_id, app))
        thread.daemon = True
        thread.start()
        
        # Return progress ID for frontend polling
        return {'progress_id': progress_id, 'status': 'started'}
    
    return render_template('import_companionships.html')

@app.route('/admin/import_progress/<progress_id>')
def import_progress(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)
    if progress_data:
        return {
            'status': progress_data['status'],
            'message': progress_data['message'],
            'step': progress_data['step'],
            'total_steps': progress_data['total_steps'],
            'districts_found': progress_data.get('districts_found', 0),
            'companionships_found': progress_data['companionships_found'],
            'members_found': progress_data['members_found'],
            'errors': progress_data['errors'],
            'redirect_url': progress_data.get('redirect_url'),
            'scraped_districts': progress_data.get('scraped_districts', [])
        }
    return {'status': 'not_found'}

@app.route('/admin/import_confirm', methods=['GET', 'POST'])
def import_confirm():
    progress_id = request.args.get('progress_id')
    
    with progress_lock:
        progress_data = progress_store.get(progress_id)
        if not progress_data or progress_data['status'] != 'completed':
            flash('No completed scrape data found.')
            return redirect(url_for('scrape_data'))
        
        scraped_districts = progress_data['scraped_districts']
    
    if request.method == 'POST' and 'confirm_import' in request.form:
        # Import the data
        try:
            # Clear existing data if requested
            if 'clear_existing' in request.form:
                # Delete in correct order due to foreign keys
                Booking.query.delete()
                InterviewSlot.query.delete()
                Member.query.delete()
                Team.query.delete()
                District.query.delete()
                db.session.commit()
                flash('Cleared all existing data for fresh import.')
            
            for district_data in scraped_districts:
                district_name = district_data['name']
                interviewer_name = district_data['interviewer']
                
                # Find or create district
                district = District.query.filter_by(name=district_name).first()
                if not district:
                    district = District(name=district_name, interviewer_name=interviewer_name)
                    db.session.add(district)
                    db.session.commit()
                
                for comp_data in district_data['companionships']:
                    # Create team
                    team = Team(district_id=district.id)
                    db.session.add(team)
                    db.session.commit()
                    
                    for member_data in comp_data['members']:
                        # Try to find existing member by email globally
                        existing_member = Member.query.filter_by(email=member_data['email']).first()
                        
                        if existing_member:
                            # Update phone if different
                            if existing_member.phone != member_data['phone'] and member_data['phone']:
                                existing_member.phone = member_data['phone']
                            # Update name if different
                            if existing_member.name != member_data['name']:
                                existing_member.name = member_data['name']
                            # Reassign to new team
                            existing_member.team_id = team.id
                            member = existing_member
                        else:
                            # Create new member
                            member = Member(
                                name=member_data['name'],
                                phone=member_data['phone'],
                                email=member_data['email'],
                                team_id=team.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the team
                        if member not in team.members:
                            team.members.append(member)
                    
                    db.session.commit()
            
            flash('Data imported successfully!')
            return redirect(url_for('admin_calendar'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}')
            return redirect(url_for('scrape_progress', progress_id=progress_id))
    
    # Display confirmation
    return render_template('import_confirm.html', scraped_districts=scraped_districts, progress_id=progress_id, confirm_endpoint='import_confirm')

@app.route('/admin/import_csv_confirm', methods=['GET', 'POST'])
def import_csv_confirm():
    scraped_districts = session.get('uploaded_districts')
    if not scraped_districts:
        flash('No uploaded data found.')
        return redirect(url_for('import_csv'))
    
    if request.method == 'POST' and 'confirm_import' in request.form:
        # Import the data
        try:
            # Clear existing data if requested
            if 'clear_existing' in request.form:
                # Delete in correct order due to foreign keys
                Booking.query.delete()
                InterviewSlot.query.delete()
                Member.query.delete()
                Team.query.delete()
                District.query.delete()
                db.session.commit()
                flash('Cleared all existing data for fresh import.')
            
            for district_data in scraped_districts:
                district_name = district_data['name']
                interviewer_name = district_data['interviewer']
                
                # Find or create district
                district = District.query.filter_by(name=district_name).first()
                if not district:
                    district = District(name=district_name, interviewer_name=interviewer_name)
                    db.session.add(district)
                    db.session.commit()
                
                for comp_data in district_data['companionships']:
                    # Create team
                    team = Team(district_id=district.id)
                    db.session.add(team)
                    db.session.commit()
                    
                    for member_data in comp_data['members']:
                        # Try to find existing member by email globally
                        existing_member = Member.query.filter_by(email=member_data['email']).first()
                        
                        if existing_member:
                            # Update phone if different
                            if existing_member.phone != member_data['phone'] and member_data['phone']:
                                existing_member.phone = member_data['phone']
                            # Update name if different
                            if existing_member.name != member_data['name']:
                                existing_member.name = member_data['name']
                            # Reassign to new team
                            existing_member.team_id = team.id
                            member = existing_member
                        else:
                            # Create new member
                            member = Member(
                                name=member_data['name'],
                                phone=member_data['phone'],
                                email=member_data['email'],
                                team_id=team.id
                            )
                            db.session.add(member)
                        
                        # Ensure member is in the team
                        if member not in team.members:
                            team.members.append(member)
                    
                    db.session.commit()
            
            session.pop('uploaded_districts', None)
            flash('Data imported successfully!')
            return redirect(url_for('admin_calendar'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}')
            return redirect(url_for('import_csv_confirm'))
    
    # Display confirmation
    return render_template('import_confirm.html', scraped_districts=scraped_districts, confirm_endpoint='import_csv_confirm')

@app.route('/admin/send_all_notifications')
def send_all_notifications():
    districts = District.query.all()
    total_sent = 0
    for district in districts:
        for team in district.teams:
            for member in team.members:
                link = url_for('schedule', token=member.token, _external=True)
                if member.email:
                    msg = Message('Interview Scheduling', sender=app.config['MAIL_USERNAME'], 
                                recipients=[member.email])
                    msg.body = f'Please schedule your interview: {link}'
                    mail.send(msg)
                    total_sent += 1
                if member.phone and twilio_client:
                    twilio_client.messages.create(body=f'Interview link: {link}', from_=twilio_number, to=member.phone)
                    total_sent += 1
    flash(f'Notifications sent to {total_sent} contacts!')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8181)