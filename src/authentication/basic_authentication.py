import argparse
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import secrets
import hashlib
import asyncio
from uuid import UUID

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.crud import ReadData, UpdateData
from src.models.basic_authentication_models import UserModel
from src.authentication.basic_authentication_crud import (
    CreateAuthentication,
    ReadAuthentication,
    DeleteAuthentication,
)
from src.create_sqlite_engine import engine
from src.load_secrets import pepper_data

Session = async_sessionmaker(autocommit=False, class_=AsyncSession, bind=engine)
basic_authentication_router = APIRouter()
security = HTTPBasic()
create_auth = CreateAuthentication()
read_auth = ReadAuthentication()
read_data = ReadData()
update_data = UpdateData()
delete_auth = DeleteAuthentication()


class BasicAuthentication:
    def __init__(self):
        pass

    async def check_user_data(
        self, credentials: HTTPBasicCredentials = Depends(security)
    ) -> UserModel:
        """Check if the user data is valid. This function is called only once before the start of the match

        Args:
            credentials (HTTPBasicCredentials, optional): _description_. Defaults to Depends(security).

        Raises:
            HTTPException: The first time the user data is checked, the user data is not found in the database
            HTTPException: The password is incorrect

        Returns:
            bool: Basic authentication result
        """
        # await create_auth.create_user_data("user", "password")

        async with Session() as session:
            user_data: UserModel = await read_auth.read_user_data(credentials.username, session)
            if user_data is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Basic"},
                )

            hashed_password = hashlib.sha256(
                (credentials.password + user_data.salt + pepper_data).encode()
            ).hexdigest()

            if not secrets.compare_digest(hashed_password, user_data.hash_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Basic"},
                )
        return user_data

    async def check_match_data(self, user_data: UserModel, match_id: UUID) -> str:
        """Check if the match data is valid. This function is called only once before the start of the match

        Args:
            user_data (UserModel): _description_
            match_id (UUID): _description_

        Raises:
            HTTPException: The first time the user data is checked, the user data is not found in the database
            HTTPException: The password is incorrect

        Returns:
            bool: Basic authentication result
        """
        async with Session() as session:
            match_team_name: str = await read_auth.read_match_data(user_data, match_id, session)
        if match_team_name is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid match data",
                headers={"WWW-Authenticate": "Basic"},
            )
        return match_team_name

    async def create_match_data(self, user_data: UserModel, match_id: UUID, match_team_name: str):
        """Create match data for the user. This function is called only once before the start of the match

        Args:
            user_data (UserModel): _description_
            match_id (UUID): _description_
            match_team_name (str): _description_

        Returns:
            bool: Basic authentication result
        """
        async with Session() as session:
            await create_auth.create_match_data(user_data, match_id, match_team_name, session)

    async def store_user_data(self, user_name: str, password: str) -> None:
        async with Session() as session:
            # create user data
            await create_auth.create_user_data(user_name, password, session)

    # read all user data
    async def read_user_data(self, user_name) -> UserModel:
        async with Session() as session:
            user_data: UserModel = await read_auth.read_user_data(username=user_name, session=session)
        return user_data
    
    async def delete_expired_match_data(self) -> None:
        async with Session() as session:
            await delete_auth.delete_expired_match_data(session)

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Basic Authentication")
    parser.add_argument("--username", type=str, help="Username", required=True)
    parser.add_argument("--password", type=str, help="Password", required=True)
    return parser

async def main(user_name: str, password: str):
    basic_auth = BasicAuthentication()
    await basic_auth.store_user_data(user_name, password)
    user_data = await basic_auth.read_user_data(user_name)
    print(user_data.username, user_data.hash_password, user_data.salt)


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()
    asyncio.run(main(args.username, args.password))
