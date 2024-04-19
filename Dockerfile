FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
COPY .env ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

ENV MODULE_NAME="src.main"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]