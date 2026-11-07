FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py render.py schedule.py font.json FONT_LICENSE.txt ./
COPY static ./static
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data FIRMWARE_DIR=/firmware
EXPOSE 18443
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,ssl; urllib.request.urlopen('https://127.0.0.1:18443/health',context=ssl._create_unverified_context(),timeout=3)" || exit 1
CMD ["python", "app.py"]
