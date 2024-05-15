#!/bin/bash

# Lazy script for create migrations in migrations
commands="alembic revision -m 'init' --autogenerate
alembic upgrade head"

docker exec -it app /bin/bash -c "$commands"