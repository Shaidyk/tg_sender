#!/bin/bash

sudo echo "Restarting..."

docker-compose down

PORT=5432
PID=$(sudo lsof -t -i:$PORT)

if [ -z "$PID" ]; then
  echo "Процесс, использующий порт $PORT, не найден."
else
  echo "Завершение процесса с PID $PID, использующего порт $PORT."
  sudo kill -9 $PID
fi

if [ "$1" = "build-hard" ]; then
  pip freeze > requirements.txt
  sudo docker-compose build --no-cache
fi

if [ "$1" = "build" ]; then
  sudo docker-compose build
fi

docker-compose up -d
docker-compose logs -f