import json
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from aiocryptopay import AioCryptoPay, Networks

from config import TOKEN, CRYPTO_TOKEN

# Налаштування логів
logging.basicConfig(level=logging.INFO)

# Telegram bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

def get_cabinet_inline():
    kb = InlineKeyboardBuilder()
    kb.button(text='💰 ПОПОВНИТИ БАЛАНС', callback_data='topup')
    kb.button(text='🎁 ПРИДБАТИ ЛУТ(METRO)', callback_data='buy_loot')
    kb.button(text='🔄 Змінити ігрове ID', callback_data='change_game_id')
    kb.button(text='💬 Тех підтримка', callback_data='tech_support')
    kb.button(text='💵 Продати лут/Стати продавцем', callback_data='become_seller')
    kb.adjust(2)
    return kb.as_markup()

@dp.message(Command('start'))
async def cmd_start(message: types.Message, state: FSMContext): 
    await message.answer('Головне меню', reply_markup=get_cabinet_inline())

# Запуск
async def on_shutdown():
    pass

async def main():
    await dp.start_polling(bot, shutdown=on_shutdown)

if __name__ == '__main__':
    asyncio.run(main())