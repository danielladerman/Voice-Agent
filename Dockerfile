
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set an environment variable to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for compiling audio packages
RUN apt-get update && apt-get install -y build-essential portaudio19-dev

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the rest of the application code
COPY . .

# Copy the Google client secret file into the container
# IMPORTANT: Make sure you have a `client_secret.json` file in your project root.
COPY client_secret.json /app/client_secret.json

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# Use gunicorn for a production-ready server
# Bind to the port provided by Render's $PORT environment variable
CMD ["/bin/sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:$PORT src.core_api.main:app"] 