import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

handler = logging.FileHandler("logger.log", mode="a")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - [User: %(user)s] - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class UserAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[User: {self.extra['user']}]: {msg}", kwargs


def get_logger_for_user(user):
    return UserAdapter(logger, {"user": user.username})