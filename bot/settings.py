from typing import List

from pydantic import BaseSettings


class Settings(BaseSettings):

    telegram_token: str
    openai_api_key: str
    use_chatgpt_api: bool = True
    allowed_telegram_usernames: List = []
    new_dialog_timeout: float | int = 60 * 30
    mongodb_uri: str = f"mongodb://mongo:27017"


settings = Settings() # type: ignore
