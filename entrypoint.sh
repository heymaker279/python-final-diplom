#!/bin/sh

python manage.py flush --no-input
python manage.py migrate
python manage.py collectstatic --no-input
#python manage.py runserver
gunicorn --bind 0.0.0.0:8000 shopping_service.wsgi:application
celery -A shopping_service.celery:app worker -l INFO


set -e
