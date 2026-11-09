FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
# sounddevice (micro local) est inutile dans le cloud : l'audio arrive de l'application
RUN grep -v '^sounddevice' requirements.txt > req-cloud.txt && pip install --no-cache-dir -r req-cloud.txt
COPY app ./app
ENV HOST=0.0.0.0 PORT=8080 AUDIO_SOURCE=remote USAGE_FILE=/data/usage.json
EXPOSE 8080
CMD ["python", "-m", "app.main"]
