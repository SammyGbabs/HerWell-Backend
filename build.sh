#!/usr/bin/env bash
# Render build command. Runs on every deploy.
# The free plan has no pre-deploy step or shell, so migrations and the first
# admin account are handled here.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py ensure_superuser
