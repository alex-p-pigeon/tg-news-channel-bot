from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import ClassVar
import os


class Settings(BaseSettings):


    # Желательно вместо str использовать SecretStr 
    # для конфиденциальных данных, например, токена бота
    BOT_TOKEN: SecretStr
    GGL_API_KEY: SecretStr
    TG_API_ID: SecretStr
    TG_API_HASH: SecretStr
    BOT_NAME: SecretStr
    TG_PHONE: SecretStr

    DBLOG_NAME: SecretStr

    # Database
    DB_HOST: SecretStr
    DB_PORT: SecretStr
    DB_NAME: SecretStr
    DB_USER: SecretStr
    DB_PASSWORD: SecretStr



    # APIs
    #OPENAI_API_KEY: SecretStr = ''
    TELEGRAM_BOT_TOKEN: SecretStr = ''
    TG_CHANNEL_ID: SecretStr
    TG_PHONE: SecretStr

    # RSS Feed
    RSS_URL: str = 'https://deadline.com/feed/'
    FETCH_INTERVAL_HOURS: int = 1

    # Processing limits
    MAX_ARTICLES_PER_RUN: int = 100
    MAX_DAILY_POSTS: int = 24
    MAX_API_RETRIES: int = 3

    # Thresholds
    MIN_RATING_THRESHOLD: int = 60
    MIN_LURKABLE_THRESHOLD: int = 70



    # Начиная со второй версии pydantic, настройки класса настроек задаются
    # через model_config
    # В данном случае будет использоваться файла .env, который будет прочитан
    # с кодировкой UTF-8
    if os.name == 'nt':
        font_path: ClassVar[str] = r"C:\Windows\Fonts\constan.ttf"
        model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


    else:
        model_config = SettingsConfigDict(env_file='~/lurk/lurk/env.env', env_file_encoding='utf-8')
        font_path: ClassVar[str] = "/usr/share/fonts/truetype/vista/constan.ttf"



# При импорте файла сразу создастся 
# и провалидируется объект конфига, 
# который можно далее импортировать из разных мест
config = Settings()


