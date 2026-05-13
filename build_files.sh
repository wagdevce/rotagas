#!/bin/bash
echo "Building project packages..."
python -m pip install -r requirements.txt

echo "Collect Static..."
python manage.py collectstatic --noinput --clear
