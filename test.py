from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    api_token: str
    bot_token: str


my_bot_settings = BotSettings()
print(my_bot_settings.api_token)
print(my_bot_settings.bot_token)