import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище групповых игр
group_games = {}


def get_lobby_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Я в деле!", callback_data="grp_join", style="success")
    builder.button(text="🚀 Я готов!", callback_data="grp_ready", style="primary")
    builder.button(text="🚪 Отменить", callback_data="grp_exit", style="danger")
    builder.adjust(1, 2)  # Первая кнопка широкая, остальные две под ней
    return builder.as_markup()


def get_group_game_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Камень 🪨", callback_data="gchoice_Камень 🪨", style="danger")
    builder.button(text="Ножницы ✂️", callback_data="gchoice_Ножницы ✂️", style="success")
    builder.button(text="Бумага 📄", callback_data="gchoice_Бумага 📄", style="primary")
    builder.adjust(1)
    return builder.as_markup()


def generate_lobby_text(game):
    text = "🎲 <b>СУ-ЛИ-ФА | ЛОББИ</b>\n━━━━━━━━━━━━━━━━━━\n"
    text += f"Участники ({len(game['players'])}/5):\n"

    if not game['players']:
        text += "<i>Пока никого нет...</i>\n"
    else:
        for uid, name in game["players"].items():
            # Если игрок нажал "Готов", ставим галочку, иначе часики
            status = "✅ Готов" if uid in game["ready"] else "⏳ Ожидает"
            text += f"👤 {name} — {status}\n"

    text += "\n<i>Для старта ВСЕ участники должны нажать «🚀 Я готов!» (минимум 2 человека).</i>"
    return text


@dp.message(Command("game"))
async def start_group_cmd(message: types.Message):
    chat_id = message.chat.id

    if message.chat.type == "private":
        await message.answer("Брат, эта команда работает только в группах! Добавь меня в свой чат.")
        return

    # Удаляем сообщение с командой /game, чтобы не засорять чат
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    if chat_id in group_games:
        msg = await message.answer("⚠️ <i>Игра в этом чате уже собирается!</i>", parse_mode="HTML")
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
        return

    user_id = message.from_user.id
    name = message.from_user.first_name

    game = {
        "state": "lobby",
        "players": {user_id: name},
        "ready": set(),
        "choices": {},
        "msg_id": 0
    }

    msg = await message.answer(generate_lobby_text(game), parse_mode="HTML", reply_markup=get_lobby_kb())
    game["msg_id"] = msg.message_id
    group_games[chat_id] = game


@dp.callback_query(F.data == "grp_join")
async def grp_join(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    game = group_games.get(chat_id)

    if not game or callback.message.message_id != game.get("msg_id"):
        await callback.answer("Это лобби уже не активно!")
        return

    if game["state"] != "lobby":
        await callback.answer("Игра уже началась!")
        return

    user_id = callback.from_user.id
    name = callback.from_user.first_name

    if user_id in game["players"]:
        await callback.answer("Ты уже в списке! Нажимай '🚀 Я готов!'")
        return

    if len(game["players"]) >= 5:
        await callback.answer("Лобби заполнено! Максимум 5 игроков.", show_alert=True)
        return

    game["players"][user_id] = name

    await callback.message.edit_text(generate_lobby_text(game), parse_mode="HTML", reply_markup=get_lobby_kb())
    await callback.answer("Ты успешно присоединился! ✅")


@dp.callback_query(F.data == "grp_ready")
async def grp_ready(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    game = group_games.get(chat_id)

    if not game or callback.message.message_id != game.get("msg_id"):
        return

    user_id = callback.from_user.id

    if user_id not in game["players"]:
        await callback.answer("Сначала нажми '🟢 Я в деле'!", show_alert=True)
        return

    if user_id in game["ready"]:
        await callback.answer("Ты уже подтвердил готовность! Ждем остальных.")
        return

    game["ready"].add(user_id)

    # Проверка: если все в лобби нажали "Готов" и их >= 2
    if len(game["ready"]) == len(game["players"]) and len(game["players"]) >= 2:
        game["state"] = "playing"
        await callback.message.edit_text(
            f"⚔️ <b>ВСЕ ГОТОВЫ! ИГРА НАЧАЛАСЬ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤫 Жмите на кнопки ниже! Выбор никто не увидит.\n"
            f"⏳ Сделано ходов: 0/{len(game['players'])}",
            parse_mode="HTML",
            reply_markup=get_group_game_kb()
        )
        await callback.answer("Все готовы! Погнали!")
    else:
        await callback.message.edit_text(generate_lobby_text(game), parse_mode="HTML", reply_markup=get_lobby_kb())
        await callback.answer("Готовность подтверждена! ✅")


@dp.callback_query(F.data.startswith("gchoice_"))
async def grp_choice(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    game = group_games.get(chat_id)

    if not game or callback.message.message_id != game.get("msg_id"):
        await callback.answer("Этот раунд уже завершен!")
        return

    user_id = callback.from_user.id

    if user_id not in game["players"]:
        await callback.answer("Ты не участвуешь в этом раунде!")
        return

    if user_id in game["choices"]:
        await callback.answer("Ты уже сделал ход!")
        return

    choice = callback.data.split("_")[1]
    game["choices"][user_id] = choice

    # Легкое уведомление без кнопки ОК
    await callback.answer(f"Твой выбор: {choice} 🤫 Принято!")

    total_players = len(game["players"])
    ready_players = len(game["choices"])

    if ready_players < total_players:
        await callback.message.edit_text(
            f"⚔️ <b>ИГРА ИДЕТ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤫 Ждем остальных...\n"
            f"⏳ Сделано ходов: {ready_players}/{total_players}",
            parse_mode="HTML",
            reply_markup=get_group_game_kb()
        )
    else:
        await resolve_group_game(chat_id, game)


async def resolve_group_game(chat_id, game):
    # 1. Удаляем меню с кнопками
    try:
        await bot.delete_message(chat_id=chat_id, message_id=game["msg_id"])
    except TelegramBadRequest:
        pass

    choices = game["choices"]
    players = game["players"]
    unique_choices = set(choices.values())

    # 2. Формируем результат
    result_text = "📊 <b>РЕЗУЛЬТАТЫ РАУНДА</b>\n━━━━━━━━━━━━━━━━━━\n"
    for uid, name in players.items():
        result_text += f"👤 {name}: <b>{choices[uid]}</b>\n"

    result_text += "\n"

    if len(unique_choices) == 1 or len(unique_choices) == 3:
        result_text += "🤝 <b>ИТОГ: НИЧЬЯ!</b> (Выпало всё или одинаковое)"
    else:
        if "Камень 🪨" in unique_choices and "Ножницы ✂️" in unique_choices:
            winner_choice = "Камень 🪨"
        elif "Ножницы ✂️" in unique_choices and "Бумага 📄" in unique_choices:
            winner_choice = "Ножницы ✂️"
        else:
            winner_choice = "Бумага 📄"

        winners = [players[uid] for uid, c in choices.items() if c == winner_choice]
        result_text += f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {', '.join(winners)}!"

    # 3. Отправляем результат навсегда
    await bot.send_message(chat_id, result_text, parse_mode="HTML")

    # 4. Автоматически создаем новое лобби
    game["state"] = "lobby"
    game["players"] = {}
    game["ready"] = set()
    game["choices"] = {}

    msg = await bot.send_message(chat_id, generate_lobby_text(game), parse_mode="HTML", reply_markup=get_lobby_kb())
    game["msg_id"] = msg.message_id


@dp.callback_query(F.data == "grp_exit")
async def grp_exit(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    if chat_id in group_games:
        del group_games[chat_id]

    await bot.send_message(
        chat_id,
        "🚪 <b>Игровая сессия завершена.</b>\nЧтобы начать новую игру, напишите /game.",
        parse_mode="HTML"
    )
    await callback.answer("Игра завершена! ✅")


async def main():
    print("Бот запущен и готов к работе! 🚀")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())