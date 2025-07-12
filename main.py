import asyncio
import logging

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
import db

# Налаштування логів
logging.basicConfig(level=logging.INFO)

# Telegram bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# CryptoBot API
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

#@dp.message(lambda m: m.sticker is not None)
#async def get_sticker_id(message: types.Message):
#    await message.answer(f"file_id цього стікера:\n<code>{message.sticker.file_id}</code>", parse_mode='HTML')

# Стан машини
class Shop(StatesGroup):
    id = State()
    balance = State()
    payment = State()
    buy_thing = State()

# Reply-клавіатура тільки з "МІЙ КАБІНЕТ"
reply_bt = ReplyKeyboardBuilder()
reply_bt.button(text='🖥 Головне меню')
reply_bt.adjust(1)
REPLY_BT = reply_bt.as_markup(resize_keyboard=True)

# Inline-клавіатура для кабінету
def get_cabinet_inline():
    kb = InlineKeyboardBuilder()
    kb.button(text='💰 ПОПОВНИТИ БАЛАНС', callback_data='topup')
    kb.button(text='🎁 ПРИДБАТИ ЛУТ(METRO)', callback_data='buy_loot')
    kb.button(text='🔄 Змінити ігрове ID', callback_data='change_game_id')
    kb.button(text='💬 Тех підтримка', callback_data='tech_support')
    kb.button(text='💵 Продати лут/Стати продавцем', callback_data='become_seller')
    kb.adjust(1)
    return kb.as_markup()

# Заглушка для неактивних кнопок
@dp.callback_query(lambda c: c.data in ['tech_support', 'become_seller'])
async def not_implemented(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Функція в розробці", show_alert=True)

# Команда старт
@dp.message(Command('start'))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer_sticker("CAACAgIAAxkBAAIE92hX8BEkQ-c4nI4mLhl3ga9PPWQ3AALOYwACmxeASsMeUM67z9rwNgQ")
    await state.clear()
    user_key = str(message.from_user.id)
    user_data = await db.get_user(int(user_key))

    if user_data:
        game_id = user_data['game_id']
        balance = user_data.get('balance', 0)
        await state.update_data(id=game_id)
        await message.answer('Раді вітати!\nВаше ігрове ID уже є в базі. Якщо бажаєте його змінити /change_id')
        await message.answer(f'Ваш баланс: {balance}', reply_markup=REPLY_BT)
        await state.set_state(Shop.balance)
    else:
        await message.answer('Привіт! Уведи своє ігрове ID:', reply_markup=REPLY_BT)
        await state.set_state(Shop.id)

# Обробка ID
@dp.message(Command('change_id'))
async def change_id(message: types.Message, state: FSMContext):
    user_key = str(message.from_user.id)
    user_data = await db.get_user(int(user_key))

    if user_data:
        await state.update_data(is_changing_id=True)
        await message.answer('Введіть нове ігрове ID:')
        await state.set_state(Shop.id)
    else:
        await message.answer('Ви не зареєстровані в системі. Спробуйте /start')

@dp.message(StateFilter(Shop.id))
async def process_id(message: types.Message, state: FSMContext):
    game_id = message.text.strip()
    user_key = str(message.from_user.id)
    user_data = await db.get_user(int(user_key))

    # Перевірка: тільки цифри
    if not game_id.isdigit():
        await message.answer('❌ Ігровий ID має містити лише цифри. Спробуйте ще раз:')
        await state.set_state(Shop.id)
        return
    if not game_id.startswith('5'):
        await message.answer('❌ Ігровий ID має починатися з 5. Спробуйте ще раз:')
        await state.set_state(Shop.id)
        return
    if len(game_id) < 9 or len(game_id) > 11:
        await message.answer('❌ Ігровий ID має містити від 9 до 11 цифр. Спробуйте ще раз:')
        await state.set_state(Shop.id)
        return
    
    # Перевіряємо чи це зміна ID
    state_data = await state.get_data()
    is_changing_id = state_data.get('is_changing_id', False)

    if is_changing_id:
        if user_data:
            await db.update_game_id(int(user_key), game_id)
            await message.answer(f'ID успішно змінено на: {game_id}')
            await state.clear()
            await state.set_state(Shop.balance)
            return

    # Якщо це нова реєстрація
    if not user_data:
        await db.create_user(int(user_key), game_id)

    await state.update_data(id=game_id)
    kb = InlineKeyboardBuilder()
    kb.button(text='CryptoBot', callback_data='button_pressed')
    await message.answer('Успішно зареєстровано!')
    await message.answer(f'Ваш баланс: 0', reply_markup=REPLY_BT)
    await message.answer('Виберіть спосіб поповнення', reply_markup=kb.as_markup())
    await state.set_state(Shop.balance)

# Обробка reply-кнопки "МІЙ КАБІНЕТ"
@dp.message(StateFilter(Shop.balance))
async def process_balance(message: types.Message, state: FSMContext):
    if message.text == '🖥 Головне меню':
        user_key = str(message.from_user.id)
        user_data = await db.get_user(int(user_key))
        if user_data:
            game_id = user_data['game_id']
            balance = user_data.get('balance', 0)
            payment_history = "\n".join([f"Поповнення: {p['amount']} USDT" for p in user_data.get('payments', [])])
            if not payment_history:
                payment_history = "Поповнень ще не було"
            
            cabinet_message = await message.answer(
                f"🎮 Ваш ігровий ID: {game_id}\n"
                f"💰 Баланс: {balance} USDT",
                reply_markup=get_cabinet_inline()
            )
            # Зберігаємо ID повідомлення для подальшого редагування
            await state.update_data(cabinet_message_id=cabinet_message.message_id)
        else:
            await message.answer('Ви не зареєстровані в системі. Спробуйте /start')
            await state.clear()

# Callback-обробник для поповнення балансу
@dp.callback_query(lambda c: c.data == 'topup')
async def handle_topup(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')

    # Клавіатура з кнопкою назад
    kb = InlineKeyboardBuilder()
    kb.button(text='⬅️ НАЗАД', callback_data='back_to_cabinet')
    kb.adjust(1)

    if cabinet_message_id:
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=cabinet_message_id,
            text='Введіть суму для поповнення:',
            reply_markup=kb.as_markup()
        )
    else:
        await callback.message.answer('Введіть суму для поповнення:', reply_markup=kb.as_markup())

    await state.set_state(Shop.payment)

# Клік по кнопці CryptoBot
@dp.callback_query(lambda c: c.data == 'button_pressed')
async def handle_button_pressed(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напишіть сумму 💸")
    await state.set_state(Shop.payment)

# Обробка суми поповнення
@dp.message(StateFilter(Shop.payment))
async def process_payment(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        user_key = str(message.from_user.id)
        user_data = await db.get_user(int(user_key))

        # Створення інвойсу
        invoice = await crypto.create_invoice(asset='USDT', amount=amount)
        invoice_url = invoice.bot_invoice_url
        invoice_id = invoice.invoice_id

        await message.answer(f"Перейдіть до оплати: {invoice_url}")
        await message.answer("Після оплати зачекайте кілька секунд...")

        # Чекаємо на оплату (до 90 сек)
        for _ in range(30):
            await asyncio.sleep(3)
            try:
                result = await crypto.get_invoices(invoice_ids=invoice_id)
                if result.status == 'paid':
                    # Додаємо платіж лише якщо такого invoice_id ще не було
                    if user_data and not any(p.get('invoice_id') == invoice_id for p in user_data['payments']):
                        await db.add_payment(int(user_key), amount, invoice_id)
                        user_data = await db.get_user(int(user_key))

                    await message.answer(f"✅ Оплата успішна!\nВаш новий баланс: {user_data['balance']}", reply_markup=REPLY_BT)
                    payment_history = "\n".join([f"Поповнення: {p['amount']} USDT" for p in user_data['payments']])
                    await message.answer(f"Історія поповнень:\n{payment_history}", reply_markup=REPLY_BT)

                    await state.set_state(Shop.balance)
                    return
            except Exception as e:
                logging.error(f"Помилка перевірки оплати: {e}")
                continue

        await message.answer("⏳ Час очікування вичерпано. Якщо ви вже оплатили — спробуйте пізніше /start")
        await state.set_state(Shop.balance)

    except ValueError:
        await message.answer("Будь ласка, введіть коректну суму (число)", reply_markup=REPLY_BT)
    except Exception as e:
        await message.answer(f"❌ Помилка при створенні інвойсу: {str(e)}")

# Закриття CryptoPay клієнта
async def on_shutdown():
    await crypto.close()

# Callback-обробник для покупки луту
@dp.callback_query(lambda c: c.data == 'buy_loot')
async def handle_buy_loot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Отримуємо ID повідомлення з кабінету
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')
    
    if cabinet_message_id:
        # Редагуємо повідомлення з кабінету
        kb = InlineKeyboardBuilder()
        kb.button(text='Речі 6-го рівня вищої якості', callback_data='6_level')
        kb.button(text='Золоті речі', callback_data='gold_stuff')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_cabinet')
        kb.adjust(1)
        
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=cabinet_message_id,
            text='Виберіть що хочете придбати',
            reply_markup=kb.as_markup()
        )
    else:
        # Якщо ID повідомлення не знайдено, надсилаємо нове
        kb = InlineKeyboardBuilder()
        kb.button(text='Речі 6-го рівня вищої якості', callback_data='6_level')
        kb.button(text='Золоті речі', callback_data='gold_stuff')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_cabinet')
        kb.adjust(1)
        await callback.message.answer('Виберіть що хочете придбати', reply_markup=kb.as_markup())
    
    await state.set_state(Shop.buy_thing)

# Callback-обробник для кнопки "НАЗАД"
@dp.callback_query(lambda c: c.data == 'back_to_cabinet')
async def handle_back_to_cabinet(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')

    if cabinet_message_id:
        user_key = str(callback.from_user.id)
        user_data = await db.get_user(int(user_key))
        if user_data:
            game_id = user_data["game_id"]
            balance = user_data.get("balance", 0)
            await bot.edit_message_text(
                chat_id=callback.from_user.id,
                message_id=cabinet_message_id,
                text=f"🎮 Ваш ігровий ID: {game_id}\n💰 Баланс: {balance} USDT",
                reply_markup=get_cabinet_inline(),
            )
    await state.set_state(Shop.balance)

@dp.callback_query(lambda c: c.data == 'gold_stuff')
async def handle_gold_stuff(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Отримуємо ID повідомлення з кабінету
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')
    
    if cabinet_message_id:
        # Редагуємо повідомлення з кабінету
        kb = InlineKeyboardBuilder()
        kb.button(text='Mk14 золота', callback_data='mk14_gold')
        kb.button(text='JS9 золота', callback_data='js9_gold')
        kb.button(text='Бронижелет("Кобра",золотий)', callback_data='cobrar_gold')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_stuff')
        kb.adjust(1)
        
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=cabinet_message_id,
            text='Виберіть річ',
            reply_markup=kb.as_markup()
        )
    else:
        # Якщо ID повідомлення не знайдено, надсилаємо нове
        kb = InlineKeyboardBuilder()
        kb.button(text='Mk14 золота', callback_data='mk14_gold')
        kb.button(text='JS9 золота', callback_data='js9_gold')
        kb.button(text='Бронижелет("Кобра",золотий)', callback_data='cobrar_gold')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_stuff')
        kb.adjust(1)
        await callback.message.answer('Виберіть річ', reply_markup=kb.as_markup())
    
    await state.set_state(Shop.buy_thing)

# Callback-обробник для кнопки "НАЗАД"
@dp.callback_query(lambda c: c.data == 'back_to_stuff')
async def handle_back_to_stuff(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Отримуємо ID повідомлення з кабінету
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')
    
    if cabinet_message_id:
        # Повертаємося до списку товарів
        kb = InlineKeyboardBuilder()
        kb.button(text='Речі 6-го рівня вищої якості', callback_data='6_level')
        kb.button(text='Золоті речі', callback_data='gold_stuff')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_cabinet')
        kb.adjust(1)
        
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=cabinet_message_id,
            text='Виберіть що хочете придбати',
            reply_markup=kb.as_markup()
        )
    
    await state.set_state(Shop.buy_thing)

@dp.callback_query(lambda c: c.data == '6_level')
async def handle_gold_stuff(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    # Отримуємо ID повідомлення з кабінету
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')
    
    if cabinet_message_id:
        # Редагуємо повідомлення з кабінету
        kb = InlineKeyboardBuilder()
        kb.button(text='Mk14 6-го рівня', callback_data='mk14_6')
        kb.button(text='JS9 6-го рівня', callback_data='js9_6')
        kb.button(text='Бронижелет("Кобра",6-го рівня)', callback_data='cobrar_6')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_stuff')
        kb.adjust(1)
        
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=cabinet_message_id,
            text='Виберіть річ',
            reply_markup=kb.as_markup()
        )
    else:
        # Якщо ID повідомлення не знайдено, надсилаємо нове
        kb = InlineKeyboardBuilder()
        kb.button(text='Mk14 золота', callback_data='mk14_gold')
        kb.button(text='JS9 золота', callback_data='js9_gold')
        kb.button(text='Бронижелет("Кобра",золотий)', callback_data='cobrar_gold')
        kb.button(text='⬅️ НАЗАД', callback_data='back_to_stuff')
        kb.adjust(1)
        await callback.message.answer('Виберіть річ', reply_markup=kb.as_markup())
    
    await state.set_state(Shop.buy_thing)

@dp.callback_query(lambda c: c.data == 'change_game_id')
async def handle_change_game_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    state_data = await state.get_data()
    cabinet_message_id = state_data.get('cabinet_message_id')
    user_key = str(callback.from_user.id)
    user_data = await db.get_user(int(user_key))
    # Клавіатура з кнопкою назад
    kb = InlineKeyboardBuilder()
    kb.button(text='⬅️ НАЗАД', callback_data='back_to_cabinet')
    kb.adjust(1)

    if user_data:
        await state.update_data(is_changing_id=True)
        if cabinet_message_id:
            await bot.edit_message_text(
                chat_id=callback.from_user.id,
                message_id=cabinet_message_id,
                text='Введіть нове ігрове ID:',
                reply_markup=kb.as_markup()
            )
        else:
            await callback.message.answer('Введіть нове ігрове ID:', reply_markup=kb.as_markup())
        await state.set_state(Shop.id)
    else:
        if cabinet_message_id:
            await bot.edit_message_text(
                chat_id=callback.from_user.id,
                message_id=cabinet_message_id,
                text='Ви не зареєстровані в системі. Спробуйте /start',
                reply_markup=kb.as_markup()
            )
        else:
            await callback.message.answer('Ви не зареєстровані в системі. Спробуйте /start', reply_markup=kb.as_markup())

# Закриття CryptoPay клієнта
async def on_shutdown():
    await crypto.close()

# Запуск
async def main():
    await db.init_pool()
    await dp.start_polling(bot, shutdown=on_shutdown)

if __name__ == '__main__':
    asyncio.run(main())

