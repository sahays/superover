# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by ffmpeg and other libraries
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends     ffmpeg     && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the common library code
COPY common/ ./common/

# Copy the specific service code
COPY media_inspector/ ./media_inspector/

# Set the Python path to include the current directory
ENV PYTHONPATH=/app

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Command to run the specific service
CMD ["uvicorn", "media_inspector.main:app", "--host", "0.0.0.0", "--port", "8080"]
