FROM python:3.11-slim

WORKDIR /home/ali/Coding/grad_project/PD-Server

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "app:create_app()"]
