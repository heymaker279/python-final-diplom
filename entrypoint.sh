#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py flush --no-input
python manage.py migrate
python manage.py collectstatic --no-input
gunicorn --bind 0.0.0.0:8000 shopping_service.wsgi:application
celery -A shopping_service.celery:app worker -l INFO


set -e

psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" <<-EOSQL
    CREATE ROLE 'Admin@user.ru' with SUPERUSER PASSWORD 'Admin2022';


EOSQL

exec "$@"