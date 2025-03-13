import random
import asyncio

from database import User
from project import Project
from config import config



async def init_worker(user: User):
    try:
        project = Project(user=user)

        is_registered = await project.check_registration_request()
        await asyncio.sleep(random.uniform(*config.check_registration_sleep))

        if is_registered:
            await project.init_session()

            await project.send_transaction()
            ws, transaction = await project.receive_websocket_transaction()
            await asyncio.sleep(random.uniform(*config.before_sign_transaction_sleep))

            signed_transaction = await project.sign_received_transaction(transaction=transaction)
            await asyncio.sleep(random.uniform(*config.after_sign_transaction_sleep))

            message = await project.create_message_with_signed_transaction(signed_transaction=signed_transaction)

            await asyncio.sleep(random.uniform(*config.before_send_confirm_message_to_websocket_sleep))
            await project.send_websocket_message(ws=ws, message=message)

            await asyncio.sleep(random.uniform(*config.before_update_points_and_transactions_count_sleep))
            await project.update_points_and_transactions_count()

            await asyncio.sleep(random.uniform(*config.before_close_session))
            await project.close_session()

    except Exception as error:
        raise Exception("Worker error: ", error)