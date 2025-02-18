# Use a lightweight Python image
FROM python:3.11-slim

# Install Java (default-jre)
RUN apt-get update && \
    apt-get install -y default-jre && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first, so that dependency installation can be cached
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Set the environment variable for the port
ENV PORT=8080

# Expose the port (Render will forward requests to this port)
EXPOSE 8080

# Start the app using Gunicorn with 1 worker and a 1200-second timeout
CMD ["gunicorn", "-w", "1", "--timeout", "1200", "-b", "0.0.0.0:8080", "app:app"]
