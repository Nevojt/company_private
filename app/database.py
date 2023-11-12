import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from typing import AsyncGenerator
from .config import settings
import psycopg2
from psycopg2.extras import RealDictCursor


Base = declarative_base()
SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.database_name}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_username}'



engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=20, max_overflow=30)
        
        
ASINC_SQLALCHEMY_DATABASE_URL = f'postgresql+asyncpg://{settings.database_name}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_username}'

engine_asinc = create_async_engine(ASINC_SQLALCHEMY_DATABASE_URL)
async_session_maker = sessionmaker(engine_asinc, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


while True:   
    try:
        conn = psycopg2.connect(host=settings.database_hostname, database=settings.database_name, user=settings.database_username,
                                password=settings.database_password, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("Database connection was successful")
        break

    except Exception as error:
            print('Conection to database failed')
            print("Error:",  error)
            time.sleep(2)