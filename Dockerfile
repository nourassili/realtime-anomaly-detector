FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY app/*.py ./
EXPOSE 9000
CMD ["python", "-m", "app.main"]
