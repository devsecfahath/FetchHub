FROM python:3.12-slim

# Install system dependencies: FFmpeg and ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create volume for persistent SQLite and downloads
VOLUME ["/app/downloads"]

# Run the bot
CMD ["python", "run.py"]
