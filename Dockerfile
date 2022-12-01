FROM python:3.9-alpine

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

RUN pip install --upgrade pip

COPY ./requirements-dev.txt ./requirements-dev.txt

COPY . .

COPY ./entrypoint.sh ./entrypoint.sh

RUN pip install --no-cache-dir -r ./requirements-dev.txt

RUN pip install gunicorn

RUN chmod +x /usr/src/app/entrypoint.sh

CMD ["/usr/src/app/entrypoint.sh"]


