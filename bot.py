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

# Данные теста
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
        self.pending_questions = []  # Оставшиеся вопросы (включая ошибки)
        self.answered_correctly = set()  # Вопросы, на которые ответили правильно
        self.current_attempts = 0  # Попытки для текущего вопроса

    def shuffle_questions(self):
        """Перемешивает вопросы для начала теста"""
        self.shuffled_questions = TEST_DATA.copy()
        random.shuffle(self.shuffled_questions)
        self.pending_questions = self.shuffled_questions.copy()
        self.answered_correctly = set()
        self.current_question = 0
        self.score = 0
        self.mistakes = []
        self.current_attempts = 0

    def shuffle_options(self, question_data):
        """Перемешивает варианты ответов для вопроса"""
        options = question_data['options'].copy()
        correct_answer = question_data['correct_answer']
        correct_index = options.index(correct_answer)
        random.shuffle(options)
        new_correct_index = options.index(correct_answer)
        return options, new_correct_index

    def get_next_question(self):
        """Получает следующий вопрос (перемешивает pending_questions если нужно)"""
        if not self.pending_questions:
            return None

        # Если это начало или закончились вопросы в текущей итерации - перемешиваем
        if self.current_question >= len(self.pending_questions):
            self.current_question = 0
            random.shuffle(self.pending_questions)

        return self.pending_questions[self.current_question]

    def mark_question_correct(self, question_data):
        """Помечает вопрос как правильно отвеченный и удаляет из pending"""
        question_text = question_data['question']
        self.answered_correctly.add(question_text)
        # Удаляем вопрос из pending_questions
        self.pending_questions = [q for q in self.pending_questions if q['question'] != question_text]
        self.score += 1
        self.current_question += 1
        self.current_attempts = 0

    def mark_question_incorrect(self, question_data, user_answer):
        """Обрабатывает неправильный ответ"""
        question_text = question_data['question']

        # Добавляем в ошибки если это первая ошибка на этот вопрос
        if not any(m['question'] == question_text for m in self.mistakes):
            mistake_info = {
                'question': question_text,
                'user_answer': user_answer,
                'correct_answer': question_data['correct_answer'],
            }
            self.mistakes.append(mistake_info)

        self.current_attempts += 1
        # Вопрос остается в pending_questions для повторения
        self.current_question += 1

    def is_test_complete(self):
        """Проверяет, завершен ли тест"""
        return len(self.pending_questions) == 0

    def get_progress_text(self):
        """Возвращает текст прогресса"""
        total_questions = len(self.shuffled_questions)
        answered = len(self.answered_correctly)
        remaining = len(self.pending_questions)
        return f"Прогресс: {answered}/{total_questions} | Осталось: {remaining}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
    Привет! Я бот для тестирования.

    Доступные команды:
    /start_test - Начать тестирование
    /my_mistakes - Показать мои ошибки

    🔄 Особенность: Если вы ошибаетесь в вопросе, он будет повторяться до тех пор, пока вы не ответите правильно!
    """
    await update.message.reply_text(welcome_text)


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало тестирования"""
    user_id = update.effective_user.id
    user_data[user_id] = UserProgress()
    user_data[user_id].shuffle_questions()
    await send_question(update, context, user_id)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отправка вопроса пользователю"""
    progress = user_data[user_id]

    if progress.is_test_complete():
        await finish_test(update, context, user_id)
        return

    question_data = progress.get_next_question()
    if not question_data:
        await finish_test(update, context, user_id)
        return

    # Перемешиваем варианты ответов
    shuffled_options, correct_index = progress.shuffle_options(question_data)

    progress.current_correct_index = correct_index
    progress.current_shuffled_options = shuffled_options
    progress.current_question_data = question_data

    keyboard = []
    for i, option in enumerate(shuffled_options):
        keyboard.append([InlineKeyboardButton(option, callback_data=f"answer_{i}")])
    keyboard.append([InlineKeyboardButton("🚪 Завершить тестирование", callback_data="end_test")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    progress_text = progress.get_progress_text()
    attempts_text = f" (Попытка: {progress.current_attempts + 1})" if progress.current_attempts > 0 else ""

    question_text = (
        f"{progress_text}{attempts_text}\n"
        f"Вопрос: {question_data['question']}"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(question_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question_text, reply_markup=reply_markup)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответов на вопросы"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id not in user_data:
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

    progress = user_data[user_id]
    question_data = progress.current_question_data

    answer_index = int(query.data.split('_')[1])
    is_correct = answer_index == progress.current_correct_index

    user_answer_text = progress.current_shuffled_options[answer_index]
    correct_answer_text = question_data['correct_answer']

    if is_correct:
        # Правильный ответ - помечаем вопрос как завершенный
        progress.mark_question_correct(question_data)
        result_text = f"✅ Правильно!\n{progress.get_progress_text()}"
    else:
        # Неправильный ответ - вопрос останется в списке
        progress.mark_question_incorrect(question_data, user_answer_text)
        result_text = f"❌ Неправильно!\nВаш ответ: {user_answer_text}\nПравильный ответ: {correct_answer_text}\n{progress.get_progress_text()}"

    # Создаем кнопки для продолжения
    keyboard = []
    if not progress.is_test_complete():
        keyboard.append([InlineKeyboardButton("Следующий вопрос →", callback_data="next_question")])
    else:
        keyboard.append([InlineKeyboardButton("🏁 Завершить тест", callback_data="finish_test_now")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{result_text}\n\nНажмите для продолжения:",
        reply_markup=reply_markup
    )


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к следующему вопросу"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await send_question(update, context, user_id)


async def handle_end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик досрочного завершения теста"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    progress = user_data[user_id]

    keyboard = [
        [InlineKeyboardButton("✅ Да, завершить", callback_data="confirm_end_test")],
        [InlineKeyboardButton("❌ Нет, продолжить", callback_data="continue_test")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Вы уверены, что хотите завершить тестирование?\n{progress.get_progress_text()}",
        reply_markup=reply_markup
    )


async def confirm_end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение досрочного завершения теста"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await finish_test(update, context, user_id, early_exit=True)


async def continue_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продолжение теста после отмены выхода"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await send_question(update, context, user_id)


async def finish_test_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик завершения теста после последнего вопроса"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await finish_test(update, context, user_id)


async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, early_exit=False):
    """Завершение теста и вывод результатов"""
    progress = user_data[user_id]
    total_questions = len(progress.shuffled_questions)

    if early_exit:
        answered = len(progress.answered_correctly)
        result_text = (
            f"📊 Тест завершен досрочно!\n"
            f"Правильно отвечено: {answered}/{total_questions}\n"
            f"Осталось вопросов: {len(progress.pending_questions)}\n\n"
        )
    else:
        result_text = (
            f"🎉 Тест завершен!\n"
            f"Ваш результат: {progress.score}/{total_questions}\n"
            f"Процент правильных ответов: {progress.score / total_questions * 100:.1f}%\n\n"
        )

    if progress.mistakes:
        result_text += f"Количество ошибок: {len(progress.mistakes)}\n"
        result_text += "Используйте /my_mistakes чтобы посмотреть ошибки"
    else:
        result_text += "Поздравляем! Вы ответили правильно на все вопросы! 🏆"

    keyboard = []
    if progress.mistakes:
        keyboard.append([InlineKeyboardButton("📝 Посмотреть ошибки", callback_data="view_mistakes")])
    keyboard.append([InlineKeyboardButton("🔄 Пройти тест снова", callback_data="restart_test")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(result_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(result_text, reply_markup=reply_markup)


async def show_mistakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ошибки пользователя"""
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
        [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mistakes_text, reply_markup=reply_markup)


async def handle_mistakes_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с ошибками"""
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
            [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mistakes_text, reply_markup=reply_markup)

    elif query.data == "restart_test":
        user_data[user_id] = UserProgress()
        user_data[user_id].shuffle_questions()
        await send_question(update, context, user_id)

    elif query.data == "end_mistakes_session":
        await query.edit_message_text("Работа с ошибками завершена. Используйте /start_test для нового теста.")


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
    application.add_handler(CallbackQueryHandler(handle_end_test, pattern="^end_test$"))
    application.add_handler(CallbackQueryHandler(confirm_end_test, pattern="^confirm_end_test$"))
    application.add_handler(CallbackQueryHandler(continue_test, pattern="^continue_test$"))
    application.add_handler(
        CallbackQueryHandler(handle_mistakes_actions, pattern="^(view_mistakes|restart_test|end_mistakes_session)$"))

    # Запуск бота
    application.run_polling()
    logger.info("Бот остановлен")


if __name__ == '__main__':
    main()