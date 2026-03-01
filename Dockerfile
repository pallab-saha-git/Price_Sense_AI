FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (Prophet requires these)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages (layer cached — only rebuilds on requirements.txt change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Port that Dash runs on
EXPOSE 8050

# Generate synthetic data + start app
CMD ["python", "app.py"]
