# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by ffmpeg and other libraries
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends     ffmpeg     && rm -rf /var/lib/apt/lists/*

# Copy the common library code
COPY common/ ./common/

# Copy the specific service code
COPY services/job_creator/ ./services/job_creator/

# Copy and install service-specific requirements
COPY services/job_creator/requirements.txt ./service_requirements.txt
RUN pip install --no-cache-dir -r service_requirements.txt

# Set the Python path to include the current directory
ENV PYTHONPATH=/app

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Command to run the specific service
CMD ["uvicorn", "services.job_creator.main:app", "--host", "0.0.0.0", "--port", "8080"]
