FROM python:3.11-slim

# Set the working directory in the container to /app
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the local src directory to /app/src
COPY src/ ./src/

# Expose the port the app runs on
EXPOSE 8000

# Set environment variable to specify the location of the module
ENV MODULE_NAME="src.main"

# Run app.py using uvicorn when the container launches
CMD ["uvicorn", "src.main:app", "--host", "192.168.1.10", "--port", "8000"]