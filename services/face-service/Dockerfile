FROM python:3.11-slim

WORKDIR /app

# ffmpeg: RTSP decoding for OpenCV. libgl/libglib: OpenCV runtime deps.
# build-essential: insightface builds a C extension at install time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Prefer TCP for RTSP — UDP drops frames badly over Wi-Fi/VLAN hops.
ENV OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"

CMD ["python", "-m", "app.main"]
