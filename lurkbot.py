from aiogram import Bot, Dispatcher, types
from datetime import datetime, date, timezone, timedelta
import logging
from aiogram.filters.command import Command
import asyncio
from aiogram.enums import ParseMode
import requests
from aiogram.types import InputFile
import io

from config import config



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

bot = Bot(token=config.BOT_TOKEN.get_secret_value())
channel_id = '@lurkmojo'        #LurkNews
dp = Dispatcher()

#chapter========================================================================================================================= Commands
def f_______commands________________():
    pass

#------------------------------------------------------------------------------------- Команда start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):        #, state: FSMContext, pool
    vUserID = message.chat.id
    str_Msg = (
        "<b>Hello</b>\n"
        "<i>hihihi</i>"
        "<blockquote>ekhm</blockquote>"
    )
    #builder = InlineKeyboardBuilder()

    #msg = await message.answer(str_Msg, parse_mode=ParseMode.HTML)      #reply_markup=builder.as_markup(),
    #await bot.send_message(chat_id=channel_id, text=str_Msg)

    # Download media
    media_url = 'https://deadline.com/wp-content/uploads/2025/07/Screenshot-2025-07-08-at-11.36.00.png'
    response = requests.get(media_url, timeout=10)
    response.raise_for_status()

    # Determine media type
    content_type = response.headers.get('content-type', '').lower()
    print('content_type - ', content_type)
    if 'image' in content_type:

        await bot.send_photo(
            chat_id=channel_id,
            photo=media_url,
            caption=str_Msg,
            parse_mode='HTML'
        )
    else:
        # Fallback to text-only
        await bot.send_message(chat_id=channel_id, text=str_Msg)


    await bot.session.close()  # important to properly close aiohttp session


# Создаем экземпляр бота
async def main():

    await dp.start_polling(bot)  #


if __name__ == '__main__':
    asyncio.run(main())

