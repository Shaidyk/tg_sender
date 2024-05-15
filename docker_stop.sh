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

sudo service postgresql restart