#!/bin/bash
sleep 2

mkdir -p backups
timestamp=$(date +"%Y%m%d_%H%M%S")
if [ -f "gefahrstoffe.db" ]; then
    cp gefahrstoffe.db "backups/gefahrstoffe_${timestamp}.db"
fi

git pull

source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=main.py
flask db upgrade

nohup python main.py > error.log 2>&1 &
