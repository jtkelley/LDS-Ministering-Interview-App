# Minimal version - no Chrome/Selenium, smaller image
# Use this if you don't need LCR scraping (CSV import only)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy application files
COPY requirements.txt ./
COPY app.py ./
COPY core/ ./core/
COPY templates/ ./templates/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create instance directory for SQLite database
RUN mkdir -p /app/instance && chmod 777 /app/instance

# Expose port
EXPOSE 8181

# Run with gunicorn
CMD gunicorn --bind 0.0.0.0:${PORT:-8181} --workers 1 --timeout 120 app:app
