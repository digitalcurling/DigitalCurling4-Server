# DigitalCurling4

This is a new server for digital curling.

## Dependencies

- Python 3.11 (or later)
- Docker
- Docker Compose
- FastAPI
- Uvicorn
- Gunicorn
- Pydantic
- SQLAlchemy

## Setup and Development

### Register user data to use basic authentication

This server use Basic authentication to identify client.
Basic authentication use username and password. Administrator can register user data in src/authentication/basic_authentication.py

```bash
cd ./src/authentication
python3 basic_authentication.py --username user --password password
```

This branch has the following default credentials:
username=user0, password=pass0
username=user1, password=pass1
If you set these in your client-side .env file, you can start playing immediately.

Example:
```
MATCH_USER_NAME="user0"
PASS_WORD="pass0"
```
or
```
MATCH_USER_NAME="user1"
PASS_WORD="pass1"
```

### Start server

1. first you need to install docker and docker-compose, then pull this repository.

1. Please input this command at Linux or WSL.
    ```bash
    sudo sysctl -w vm.overcommit_memory=1
    ```

1. Create a `.env` file in the root of the project and add the following variables:

    ```bash
    POSTGRES_USER=your_user
    POSTGRES_PASSWORD=your_password
    POSTGRES_DB=your_db
    POSTGRES_HOST=your_host
    POSTGRES_PORT=your_port
    ```
    For details, refer to the [.env.sample](./.env.sample) file.

1. Create docker network:

    ```bash
    docker network create dc_network
    ```

1. If you want to run dc-server in production env, run the following command

    ```bash
    docker compose -f docker-compose.yml up --build
    ```

1. If you want to run dc-server in development env, run the following command:

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up
    ```

    or

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
    ```

    In development mode, changes in the code will be reflected in the server automatically.

    If you don't want to see the logs, you can run the server in daemon mode with the `-d` flag.

### Database migration

When the database schema is updated, existing databases need to be migrated manually.
This project does not use a migration tool, so you need to apply changes directly.

**Apply changes to an existing database (keeps existing data)**

1. Check the container name of the `db` service:

    ```bash
    docker compose ps
    ```

1. Connect to the database:

    ```bash
    docker exec -it <db_container_name> psql -U <POSTGRES_USER> -d <POSTGRES_DB>
    ```

    Replace `<POSTGRES_USER>` and `<POSTGRES_DB>` with the values in your `.env` file.

1. Run the migration SQL. For example, to add the `actual_angular_velocity` column:

    ```sql
    ALTER TABLE shot_info ADD COLUMN actual_angular_velocity DOUBLE PRECISION;
    ```

1. Verify and exit:

    ```sql
    \d shot_info
    \q
    ```

## Communication through SSE

Board data is sent to the client by SSE.
When communication by SSE is disconnected, all board data within the end of the current match is sent to the client.
In this case, the old board data is divided into "**state_update**" in event.type and the latest board data into "**latest_state_update**" in event.type.

## For developpers

### Generate requirements.txt

```bash
uv pip compile pyproject.toml -o requirements.txt
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## TODOs

- [ ] Add tests
- [ ] Preparation for operation in a production environment
- [ ] Develop a mode for multiple simultaneous matches in Webhook
- [ ] Add REST API for GUI, and tumeshogi mode and so on...

