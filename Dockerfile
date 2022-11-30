FROM python:3.9-alpine

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

RUN pip install --upgrade pip

COPY ./requirements-dev.txt ./requirements-dev.txt

COPY . .

COPY ./entrypoint.sh .

RUN apk update \
    && apk add postgresql-dev gcc python3-dev musl-dev

RUN pip install --no-cache-dir -r ./requirements-dev.txt

RUN pip install gunicorn

#RUN chmod +x /usr/src/app/entrypoint.sh

## create the appropriate directories
#ENV HOME=/home/app
#ENV APP_HOME=/home/app/web
#RUN mkdir -p $APP_HOME
#RUN mkdir -p $APP_HOME/staticfiles
#WORKDIR $APP_HOME

