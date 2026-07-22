#!/bin/bash
sleep 2

mkdir -p data/backups
timestamp=$(date +"%Y%m%d_%H%M%S")
if [ -f "data/gefahrstoffe.db" ]; then
    cp data/gefahrstoffe.db "data/backups/gefahrstoffe_${timestamp}.db"
elif [ -f "gefahrstoffe.db" ]; then
    cp gefahrstoffe.db "data/backups/gefahrstoffe_${timestamp}.db"
fi

# Branch wechseln falls angegeben (via Umgebungsvariable TARGET_BRANCH)
if [ -n "$TARGET_BRANCH" ]; then
    git fetch
    git checkout "$TARGET_BRANCH"
fi

git pull

source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=main.py
flask db upgrade

nohup python main.py > error.log 2>&1 &
