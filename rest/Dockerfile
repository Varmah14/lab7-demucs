FROM python:3.11-slim
WORKDIR /app
COPY rest-server.py .
RUN pip install --no-cache-dir flask redis minio
ENV PORT=5000
EXPOSE 5000
CMD ["python", "rest-server.py"]

