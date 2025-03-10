import asyncio
from core.worker import init_worker
from database import session, User
from config.config import accounts_count
from config.logger import get_logger_for_user


semaphore = asyncio.Semaphore(accounts_count)


async def start_farm(user: User):
    user_logger = get_logger_for_user(user)
    async with semaphore:
        try:
            await init_worker(user)
        except Exception as error:
            user_logger.error(str(error))


async def main():
    users = session.query(User).order_by(User.id).all()
    tasks = [start_farm(user) for user in users]
    await asyncio.gather(*tasks)
    session.close()



if __name__ == "__main__":
    asyncio.run(main())
