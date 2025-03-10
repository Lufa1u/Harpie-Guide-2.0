from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os


DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, echo=True)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    proxy = Column(String, nullable=True)
    email = Column(String, nullable=False, unique=True)
    wallet = Column(String, nullable=True)
    private_key = Column(String, nullable=False, unique=True)
    cookie = Column(String, nullable=True)
    points = Column(Integer, default=0)



Base.metadata.create_all(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()


async def add_users_from_files(data_folder="data"):
    files = {
        "username": "username.txt",
        "proxy": "proxy.txt",
        "email": "email.txt",
        "wallet": "wallet.txt",
        "private_key": "private_key.txt",
        "cookie": "cookie.txt"
    }

    data = {key: [] for key in files}

    for key, filename in files.items():
        path = os.path.join(data_folder, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file:
                data[key] = [line.strip() for line in file.readlines()]

    num_records = min(len(v) for v in data.values() if v)

    for i in range(num_records):
        new_user = User(
            username=data["username"][i],
            proxy=data["proxy"][i],
            email=data["email"][i],
            wallet=data["wallet"][i],
            private_key=data["private_key"][i],
            cookie=data["cookie"][i] if data["cookie"] else None
        )
        session.add(new_user)

    session.commit()
    session.close()
