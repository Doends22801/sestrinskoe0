import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не установлен!")
    exit(1)

# Данные теста (вопросы, варианты ответов, правильные ответы)
TEST_DATA = [
    {
        'question': 'Столица Франции?',
        'options': ['Лондон', 'Берлин', 'Париж', 'Мадрид'],
        'correct_answer': 'Париж'
    },
    {
        'question': 'Самая большая планета Солнечной системы?',
        'options': ['Земля', 'Юпитер', 'Сатурн', 'Марс'],
        'correct_answer': 'Юпитер'
    },
    {
        'question': '2 + 2 * 2 = ?',
        'options': ['6', '8', '4', '10'],
        'correct_answer': '6'
    },
    {
        'question': 'Сколько цветов у радуги?',
        'options': ['5', '6', '7', '8'],
        'correct_answer': '7'
    }
]

# Хранение данных пользователей
user_data = {}


class UserProgress:
    def __init__(self):
        self.current_question = 0
        self.score = 0
        self.mistakes = []
        self.shuffled_questions = []
        self.mistakes_test = False
        self.original_mistakes = []

    def shuffle_questions(self):
        self.shuffled_questions = TEST_DATA.copy()
        random.shuffle(self.shuffled_questions)

    def shuffle_options(self, question_data):
        options = question_data['options'].copy()
        correct_answer = question_data['correct_answer']
        correct_index = options.index(correct_answer)
        random.shuffle(options)
        new_correct_index = options.index(correct_answer)
        return options, new_correct_index


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
    Привет! Я бот для тестирования.

    Доступные команды:
    /start_test - Начать тестирование
    /my_mistakes - Показать и отработать мои ошибки
    """
    await update.message.reply_text(welcome_text)


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = UserProgress()
    user_data[user_id].shuffle_questions()
    await send_question(update, context, user_id)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    progress = user_data[user_id]

    if progress.current_question >= len(progress.shuffled_questions):
        if progress.mistakes_test:
            await finish_mistakes_test(update, context, user_id)
        else:
            await finish_test(update, context, user_id)
        return

    question_data = progress.shuffled_questions[progress.current_question]
    shuffled_options, correct_index = progress.shuffle_options(question_data)

    progress.current_correct_index = correct_index
    progress.current_shuffled_options = shuffled_options

    keyboard = []
    for i, option in enumerate(shuffled_options):
        keyboard.append([InlineKeyboardButton(option, callback_data=f"answer_{i}")])
    keyboard.append([InlineKeyboardButton("🚪 Завершить тестирование", callback_data="end_test")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if progress.mistakes_test:
        question_text = f"📝 Отработка ошибок ({progress.current_question + 1}/{len(progress.shuffled_questions)}):\n{question_data['question']}"
    else:
        question_text = f"Вопрос {progress.current_question + 1}/{len(progress.shuffled_questions)}:\n{question_data['question']}"

    if update.callback_query:
        await update.callback_query.edit_message_text(question_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question_text, reply_markup=reply_markup)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id not in user_data:
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

    progress = user_data[user_id]
    question_data = progress.shuffled_questions[progress.current_question]

    answer_index = int(query.data.split('_')[1])
    is_correct = answer_index == progress.current_correct_index

    user_answer_text = progress.current_shuffled_options[answer_index]
    correct_answer_text = question_data['correct_answer']

    if is_correct:
        progress.score += 1
        result_text = "✅ Правильно!"
    else:
        result_text = f"❌ Неправильно!\nВаш ответ: {user_answer_text}\nПравильный ответ: {correct_answer_text}"
        if not progress.mistakes_test:
            mistake_info = {
                'question': question_data['question'],
                'user_answer': user_answer_text,
                'correct_answer': correct_answer_text,
            }
            progress.mistakes.append(mistake_info)

    progress.current_question += 1

    keyboard = []
    if progress.current_question < len(progress.shuffled_questions):
        keyboard.append([InlineKeyboardButton("Следующий вопрос →", callback_data="next_question")])
    else:
        if progress.mistakes_test:
            keyboard.append([InlineKeyboardButton("🏁 Завершить отработку ошибок", callback_data="finish_mistakes_now")])
        else:
            keyboard.append([InlineKeyboardButton("🏁 Завершить тест", callback_data="finish_test_now")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{result_text}\n\nНажмите для продолжения:",
        reply_markup=reply_markup
    )


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await send_question(update, context, user_id)


async def handle_end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    keyboard = [
        [InlineKeyboardButton("✅ Да, завершить", callback_data="confirm_end_test")],
        [InlineKeyboardButton("❌ Нет, продолжить", callback_data="continue_test")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    progress = user_data[user_id]
    completed = progress.current_question
    total = len(progress.shuffled_questions)

    await query.edit_message_text(
        f"Вы уверены, что хотите завершить тестирование?\nПрогресс: {completed}/{total} вопросов",
        reply_markup=reply_markup
    )


async def confirm_end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await finish_test(update, context, user_id, early_exit=True)


async def continue_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await send_question(update, context, user_id)


async def finish_test_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await finish_test(update, context, user_id)


async def finish_mistakes_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await finish_mistakes_test(update, context, user_id)


async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, early_exit=False):
    progress = user_data[user_id]
    total_questions = len(progress.shuffled_questions)
    answered_questions = progress.current_question

    if early_exit:
        result_text = f"📊 Тест завершен досрочно!\nОтвечено вопросов: {answered_questions}/{total_questions}\n"
        if answered_questions > 0:
            percentage = (progress.score / answered_questions) * 100
            result_text += f"Правильных ответов: {progress.score}\nПроцент правильных: {percentage:.1f}%\n\n"
    else:
        result_text = f"🎉 Тест завершен!\nВаш результат: {progress.score}/{total_questions}\n"
        result_text += f"Процент правильных ответов: {progress.score / total_questions * 100:.1f}%\n\n"

    if progress.mistakes:
        result_text += f"Количество ошибок: {len(progress.mistakes)}\n"
        result_text += "Используйте /my_mistakes чтобы посмотреть и отработать ошибки"
    else:
        result_text += "Поздравляем! Вы ответили правильно на все вопросы! 🏆"

    keyboard = []
    if progress.mistakes:
        keyboard.append([InlineKeyboardButton("📝 Посмотреть и отработать ошибки", callback_data="view_mistakes")])
    keyboard.append([InlineKeyboardButton("🔄 Пройти тест снова", callback_data="restart_test")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(result_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(result_text, reply_markup=reply_markup)


async def finish_mistakes_test(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    progress = user_data[user_id]

    result_text = (
        f"🎉 Отработка ошибок завершена!\n"
        f"Ваш результат: {progress.score}/{len(progress.shuffled_questions)}\n\n"
    )

    if progress.score == len(progress.shuffled_questions):
        result_text += "Отлично! Вы исправили все ошибки! 🏆"
    else:
        result_text += "Продолжайте работать над ошибками! 💪"
        result_text += "\n\nИспользуйте /my_mistakes чтобы снова попробовать"

    keyboard = [
        [InlineKeyboardButton("🔄 Пройти полный тест", callback_data="restart_test")],
        [InlineKeyboardButton("📋 Посмотреть исходные ошибки", callback_data="view_original_mistakes")],
        [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(result_text, reply_markup=reply_markup)


async def show_mistakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_data:
        await update.message.reply_text("Вы еще не проходили тестирование. Используйте /start_test")
        return

    progress = user_data[user_id]

    if not progress.mistakes:
        await update.message.reply_text("🎉 У вас нет ошибок! Отличный результат!")
        return

    mistakes_text = "📋 Ваши ошибки:\n\n"
    for i, mistake in enumerate(progress.mistakes, 1):
        mistakes_text += (
            f"{i}. Вопрос: {mistake['question']}\n"
            f" Ваш ответ: ❌ {mistake['user_answer']}\n"
            f" Правильный ответ: ✅ {mistake['correct_answer']}\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("🔄 Пройти тест снова", callback_data="restart_test")],
        [InlineKeyboardButton("📝 Отработать ошибки", callback_data="practice_mistakes")],
        [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mistakes_text, reply_markup=reply_markup)


async def handle_mistakes_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "view_mistakes":
        progress = user_data[user_id]
        if not progress.mistakes:
            await query.edit_message_text("У вас нет ошибок!")
            return

        mistakes_text = "📋 Ваши ошибки:\n\n"
        for i, mistake in enumerate(progress.mistakes, 1):
            mistakes_text += (
                f"{i}. {mistake['question']}\n"
                f" Ваш ответ: ❌ {mistake['user_answer']}\n"
                f" Правильный: ✅ {mistake['correct_answer']}\n\n"
            )

        keyboard = [
            [InlineKeyboardButton("🔄 Пройти тест снова", callback_data="restart_test")],
            [InlineKeyboardButton("📝 Отработать ошибки", callback_data="practice_mistakes")],
            [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mistakes_text, reply_markup=reply_markup)

    elif query.data == "restart_test":
        user_data[user_id] = UserProgress()
        user_data[user_id].shuffle_questions()
        await send_question(update, context, user_id)

    elif query.data == "practice_mistakes":
        progress = user_data[user_id]
        if progress.mistakes:
            mistake_questions = []
            for mistake in progress.mistakes:
                for original_question in TEST_DATA:
                    if original_question['question'] == mistake['question']:
                        mistake_questions.append(original_question.copy())
                        break

            if mistake_questions:
                original_mistakes = progress.mistakes.copy()
                user_data[user_id] = UserProgress()
                user_data[user_id].mistakes_test = True
                user_data[user_id].original_mistakes = original_mistakes
                user_data[user_id].shuffled_questions = mistake_questions
                await send_question(update, context, user_id)
            else:
                await query.edit_message_text("Не удалось найти вопросы для отработки ошибок.")
        else:
            await query.edit_message_text("У вас нет ошибок для отработки!")

    elif query.data == "end_mistakes_session":
        await query.edit_message_text("Работа с ошибками завершена. Используйте /start_test для нового теста.")

    elif query.data == "view_original_mistakes":
        progress = user_data[user_id]
        if hasattr(progress, 'original_mistakes') and progress.original_mistakes:
            mistakes_text = "📋 Исходные ошибки:\n\n"
            for i, mistake in enumerate(progress.original_mistakes, 1):
                mistakes_text += (
                    f"{i}. {mistake['question']}\n"
                    f" Ваш ответ: ❌ {mistake['user_answer']}\n"
                    f" Правильный: ✅ {mistake['correct_answer']}\n\n"
                )

            keyboard = [
                [InlineKeyboardButton("🔄 Пройти тест снова", callback_data="restart_test")],
                [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(mistakes_text, reply_markup=reply_markup)


def main():
    logger.info("Запуск бота...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("start_test", start_test))
    application.add_handler(CommandHandler("my_mistakes", show_mistakes))

    # Обработчики callback'ов
    application.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer_"))
    application.add_handler(CallbackQueryHandler(next_question, pattern="^next_question$"))
    application.add_handler(CallbackQueryHandler(finish_test_now, pattern="^finish_test_now$"))
    application.add_handler(CallbackQueryHandler(finish_mistakes_now, pattern="^finish_mistakes_now$"))
    application.add_handler(CallbackQueryHandler(handle_end_test, pattern="^end_test$"))
    application.add_handler(CallbackQueryHandler(confirm_end_test, pattern="^confirm_end_test$"))
    application.add_handler(CallbackQueryHandler(continue_test, pattern="^continue_test$"))
    application.add_handler(CallbackQueryHandler(handle_mistakes_actions,
                                                 pattern="^(view_mistakes|restart_test|practice_mistakes|end_mistakes_session|view_original_mistakes)$"))

    # Запуск бота
    application.run_polling()
    logger.info("Бот остановлен")


if __name__ == '__main__':
    main()