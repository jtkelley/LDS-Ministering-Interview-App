"""
Decorators for route protection and access control.
"""
from functools import wraps
from flask import redirect, url_for, flash, request
from flask_user import current_user


def admin_required(f):
    """Decorator to require admin role for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('user.login', next=request.path))
        if current_user.role != 'admin':
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('public.index'))
        return f(*args, **kwargs)
    return decorated_function
