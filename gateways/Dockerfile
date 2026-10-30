FROM python:3.12-slim
WORKDIR /gateway
COPY gateways/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY gateways/*.py ./
ENV PYTHONUNBUFFERED=1
