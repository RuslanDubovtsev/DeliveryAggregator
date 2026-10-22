FROM python:3.12-slim

WORKDIR /project

COPY requirements.txt .

RUN pip install --upgrade pip

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install -r requirements.txt

COPY aggregator/ ./aggregator/
COPY mock_services/ ./mock_services/
