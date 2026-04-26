FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

USER app
ENTRYPOINT ["python", "main.py"]
