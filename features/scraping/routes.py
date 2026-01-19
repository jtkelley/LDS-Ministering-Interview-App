"""
Scraping routes for LCR web scraping functionality.
These routes are only available in the full app version.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
import uuid
import threading
import io
import csv

from core.utils import admin_required, group_results_by_district
from core.shared import progress_store, progress_lock
from core.models import db, District, Companionship, Member, InterviewSlot, Booking

# Create blueprint - will be registered under /admin prefix by the main app
scraping_bp = Blueprint('scraping', __name__, url_prefix='/admin')


@scraping_bp.route('/scrape', methods=['GET', 'POST'])
@admin_required
def scrape_data():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        group = request.form.get('group', 'brothers')

        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('scraping.scrape_data'))

        # Run scraping in a thread to avoid blocking
        progress_id = str(uuid.uuid4())
        with progress_lock:
            progress_store[progress_id] = {
                'status': 'running',
                'message': 'Initializing scraper...',
                'step': 0,
                'total_steps': 10,
                'districts_found': 0,
                'companionships_found': 0,
                'members_found': 0,
                'errors': [],
                'group': group
            }

        def run_scrape():
            try:
                # Import the scraper module
                print(f"[DEBUG] Starting scraper thread for progress_id: {progress_id}")
                from features.scraping.scraper import scrape_ministering_data
                print(f"[DEBUG] Successfully imported scrape_ministering_data")

                def progress_callback(message, counts=None):
                    print(f"[DEBUG] Progress callback: {message}, counts: {counts}")
                    # Update progress store with the message
                    with progress_lock:
                        progress_store[progress_id]['message'] = message

                        # Update counts if provided
                        if counts and isinstance(counts, dict):
                            if 'districts' in counts:
                                progress_store[progress_id]['districts_found'] = counts['districts']
                            if 'companionships' in counts:
                                progress_store[progress_id]['companionships_found'] = counts['companionships']
                            if 'members' in counts:
                                progress_store[progress_id]['members_found'] = counts['members']

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
                print(f"[DEBUG] Calling scrape_ministering_data with username: {username[:3]}..., group: {group}")
                results = scrape_ministering_data(username, password, progress_callback, group=group)
                print(f"[DEBUG] Scraper returned {len(results) if results else 0} results")

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
                print(f"[ERROR] Scraper thread failed: {e}")
                import traceback
                traceback.print_exc()
                with progress_lock:
                    progress_store[progress_id]['status'] = 'error'
                    progress_store[progress_id]['message'] = str(e)
                    progress_store[progress_id]['errors'].append(str(e))

        thread = threading.Thread(target=run_scrape)
        thread.start()

        return redirect(url_for('scraping.scrape_progress', progress_id=progress_id))

    return render_template('scrape.html')


@scraping_bp.route('/scrape_progress/<progress_id>')
@admin_required
def scrape_progress(progress_id):
    return render_template('scrape_progress.html', progress_id=progress_id)


@scraping_bp.route('/download_csv/<progress_id>')
@admin_required
def download_csv(progress_id):
    with progress_lock:
        progress_data = progress_store.get(progress_id)

    if not progress_data or progress_data['status'] != 'completed':
        flash('No completed scrape data found.')
        return redirect(url_for('scraping.scrape_data'))

    raw_results = progress_data.get('raw_results')
    if not raw_results:
        flash('No raw data available for download.')
        return redirect(url_for('scraping.scrape_data'))

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['district', 'interviewer', 'name', 'phone', 'email', 'companionship_id'])
    writer.writeheader()
    for row in raw_results:
        writer.writerow(row)

    # Create response with appropriate filename based on group
    group = progress_data.get('group', 'brothers')
    output.seek(0)
    response = send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'ministering_{group}.csv'
    )

    return response


@scraping_bp.route('/import_confirm', methods=['GET'])
@admin_required
def import_confirm():
    """Redirect to new import preview with smart matching"""
    progress_id = request.args.get('progress_id')
    if not progress_id:
        flash('No progress ID provided.')
        return redirect(url_for('scraping.scrape_data'))

    with progress_lock:
        progress_data = progress_store.get(progress_id)
        if not progress_data or progress_data['status'] != 'completed':
            flash('No completed scrape data found.')
            return redirect(url_for('scraping.scrape_data'))

    # Redirect to the new preview system in admin routes
    return redirect(url_for('admin.import_preview', source='scrape', progress_id=progress_id))
