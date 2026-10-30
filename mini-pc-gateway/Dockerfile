FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'paho-mqtt>=2,<3' 'bleak>=1,<4'
WORKDIR /gateway
COPY gateway.py adapter_example.py ble_scan.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "gateway.py"]
