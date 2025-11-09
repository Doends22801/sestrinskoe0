import os
import logging
import random
import re
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

# Медицинские вопросы
TEST_DATA = [
    {
        'question': 'Общие принципы лечения вывихов',
        'options': [
            'Иммобилизация, санация, диета',
            'Вправление, репозиция, санаторно-курортное лечение',
            'Репозиция, иммобилизация, реабилитация',
            'Вправление, фиксация, реабилитация',
            'Операция, реабилитация, фиксация'
        ],
        'correct_answers': ['Вправление, фиксация, реабилитация']
    },
    {
        'question': 'При гипогликемическом состоянии необходимо',
        'options': [
            'Напоить больного сладким чаем',
            'Срочно ввести простой инсулин',
            'Дать щелочное питье'
        ],
        'correct_answers': ['Напоить больного сладким чаем']
    },
    {
        'question': 'Запах ацетона изо рта наблюдается у больного при коме',
        'options': [
            'Гипогликемической',
            'Гипергликемической',
            'Печеночной',
            'Уремической'
        ],
        'correct_answers': ['Гипергликемической']
    },
    {
        'question': 'Влажные кожные покровы характерны для комы',
        'options': [
            'Гипергликемической',
            'Гипогликемической',
            'Уремической',
            'Почечной'
        ],
        'correct_answers': ['Гипогликемической']
    },
    {
        'question': 'Заболевания, которые приводят к развитию гипергликемической комы',
        'options': [
            'Инфаркт миокарда',
            'Вирусный гепатит',
            'Мочекаменная болезнь',
            'Сахарный диабет',
            'Аспирационная пневмония'
        ],
        'correct_answers': ['Сахарный диабет']
    },
    {
        'question': 'Жировая эмболия наблюдается при',
        'options': [
            'Эфирных судорогах',
            'Тиреоидном кризе',
            'Переломах длинных трубчатых костей',
            'Переливании крови',
            'Гемотрансфузионном шоке'
        ],
        'correct_answers': ['Переломах длинных трубчатых костей']
    }
]

# Хранение данных пользователей
user_data = {}


class UserProgress:
    def __init__(self):
        self.current_question_index = 0
        self.score = 0
        self.mistakes = []
        self.shuffled_questions = []
        self.pending_questions = []
        self.answered_correctly = set()
        self.current_attempts = 0
        self.mistakes_practice_mode = False
        self.mistakes_to_practice = []
        self.selected_answers = []
        self.current_question_data = None
        self.current_shuffled_options = []
        self.option_to_index_map = {}  # Маппинг текста ответа на индекс

    def initialize_test(self):
        """Инициализирует тест с нуля"""
        logger.info("Инициализация нового теста")
        self.shuffled_questions = TEST_DATA.copy()
        random.shuffle(self.shuffled_questions)
        self.pending_questions = self.shuffled_questions.copy()
        self.answered_correctly.clear()
        self.current_question_index = 0
        self.score = 0
        self.mistakes.clear()
        self.current_attempts = 0
        self.mistakes_practice_mode = False
        self.mistakes_to_practice.clear()
        self.selected_answers.clear()
        self.current_question_data = None
        self.current_shuffled_options.clear()
        self.option_to_index_map.clear()
        logger.info(f"Тест инициализирован с {len(self.shuffled_questions)} вопросами")

    def shuffle_options(self, question_data):
        """Перемешивает варианты ответов для вопроса"""
        options = question_data['options'].copy()
        random.shuffle(options)
        return options

    def get_current_question(self):
        """Получает текущий вопрос"""
        if self.mistakes_practice_mode:
            if not self.mistakes_to_practice:
                return None
            if self.current_question_index >= len(self.mistakes_to_practice):
                self.current_question_index = 0
                random.shuffle(self.mistakes_to_practice)
            return self.mistakes_to_practice[self.current_question_index]
        else:
            if not self.pending_questions:
                return None
            if self.current_question_index >= len(self.pending_questions):
                self.current_question_index = 0
                random.shuffle(self.pending_questions)
            return self.pending_questions[self.current_question_index]

    def is_answer_correct(self, selected_options, question_data):
        """Проверяет правильность ответа"""
        correct_answers = set(question_data['correct_answers'])
        selected_answers = set(selected_options)
        return selected_answers == correct_answers

    def handle_correct_answer(self, question_data):
        """Обрабатывает правильный ответ"""
        question_text = question_data['question']
        self.answered_correctly.add(question_text)

        if self.mistakes_practice_mode:
            self.mistakes_to_practice = [q for q in self.mistakes_to_practice if q['question'] != question_text]
            self.mistakes = [m for m in self.mistakes if m['question'] != question_text]
        else:
            self.pending_questions = [q for q in self.pending_questions if q['question'] != question_text]

        self.score += 1
        self.current_attempts = 0
        self.selected_answers.clear()

        if not self.mistakes_practice_mode:
            self.current_question_index += 1

    def handle_incorrect_answer(self, question_data, user_answers):
        """Обрабатывает неправильный ответ"""
        question_text = question_data['question']

        if not self.mistakes_practice_mode:
            if not any(m['question'] == question_text for m in self.mistakes):
                mistake_info = {
                    'question': question_text,
                    'user_answer': ", ".join(user_answers),
                    'correct_answer': ", ".join(question_data['correct_answers']),
                }
                self.mistakes.append(mistake_info)

        self.current_attempts += 1
        self.selected_answers.clear()

        if not self.mistakes_practice_mode:
            self.current_question_index += 1

    def is_test_complete(self):
        """Проверяет завершение теста"""
        if self.mistakes_practice_mode:
            return len(self.mistakes_to_practice) == 0
        else:
            return len(self.pending_questions) == 0

    def get_progress_text(self):
        """Возвращает текст прогресса"""
        if self.mistakes_practice_mode:
            total_mistakes = len(self.mistakes) + len(self.mistakes_to_practice)
            remaining = len(self.mistakes_to_practice)
            return f"Отработка ошибок: {total_mistakes - remaining}/{total_mistakes}"
        else:
            total_questions = len(self.shuffled_questions)
            answered = len(self.answered_correctly)
            remaining = len(self.pending_questions)
            return f"Прогресс: {answered}/{total_questions} | Осталось: {remaining}"

    def start_mistakes_practice(self):
        """Начинает режим отработки ошибок"""
        if not self.mistakes:
            logger.warning("Попытка начать отработку ошибок при их отсутствии")
            return False

        self.mistakes_practice_mode = True
        self.mistakes_to_practice.clear()

        for mistake in self.mistakes:
            for original_question in TEST_DATA:
                if original_question['question'] == mistake['question']:
                    self.mistakes_to_practice.append(original_question.copy())
                    break

        if not self.mistakes_to_practice:
            logger.error("Не удалось найти вопросы для отработки ошибок")
            return False

        random.shuffle(self.mistakes_to_practice)
        self.current_question_index = 0
        self.score = 0
        self.current_attempts = 0
        self.selected_answers.clear()
        logger.info(f"Начата отработка {len(self.mistakes_to_practice)} ошибок")
        return True

    def toggle_answer_selection(self, answer_text):
        """Добавляет или удаляет ответ из выбранных"""
        if answer_text in self.selected_answers:
            self.selected_answers.remove(answer_text)
        else:
            self.selected_answers.append(answer_text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    welcome_text = """
🏥 Медицинский тест-бот

Доступные команды:
/start_test - Начать тестирование
/my_mistakes - Показать и отработать ошибки

🔄 В режиме отработки ошибок вопросы повторяются до правильного ответа!
⚡ Поддерживаются вопросы с несколькими правильными ответами!
    """
    await update.message.reply_text(welcome_text)


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало тестирования"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} начал тест")

    user_data[user_id] = UserProgress()
    user_data[user_id].initialize_test()
    await send_question(update, context, user_id)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отправка вопроса пользователю"""
    logger.info(f"Отправка вопроса пользователю {user_id}")

    progress = user_data.get(user_id)
    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id}")
        await handle_user_not_found(update)
        return

    if progress.is_test_complete():
        logger.info(f"Тест завершен для пользователя {user_id}")
        await finish_test(update, context, user_id)
        return

    question_data = progress.get_current_question()
    if not question_data:
        logger.error(f"Вопрос не найден для пользователя {user_id}")
        await finish_test(update, context, user_id)
        return

    # Подготавливаем данные вопроса
    shuffled_options = progress.shuffle_options(question_data)
    progress.current_question_data = question_data
    progress.current_shuffled_options = shuffled_options
    progress.option_to_index_map.clear()

    # Создаем маппинг текста ответа на индекс
    for idx, option in enumerate(shuffled_options):
        progress.option_to_index_map[option] = idx

    # Создаем клавиатуру
    keyboard = create_question_keyboard(progress, shuffled_options)
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Формируем текст вопроса
    question_text = format_question_text(progress, question_data)

    # Отправляем сообщение
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(question_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(question_text, reply_markup=reply_markup)
        logger.info(f"Вопрос отправлен пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки вопроса пользователю {user_id}: {e}")
        await handle_error(update, "Произошла ошибка при отправке вопроса")


def create_question_keyboard(progress, shuffled_options):
    """Создает клавиатуру для вопроса"""
    keyboard = []

    # Кнопки вариантов ответов
    for option in shuffled_options:
        prefix = "✅ " if option in progress.selected_answers else ""
        # Используем индекс варианта ответа как callback_data
        index = progress.option_to_index_map[option]
        keyboard.append([InlineKeyboardButton(f"{prefix}{option}", callback_data=f"select_{index}")])

    # Кнопка отправки ответа
    if progress.selected_answers:
        keyboard.append([InlineKeyboardButton("🚀 Отправить ответ", callback_data="submit_answers")])

    # Кнопка завершения теста (только в основном режиме)
    if not progress.mistakes_practice_mode:
        keyboard.append([InlineKeyboardButton("🚪 Завершить тестирование", callback_data="end_test")])

    return keyboard


def format_question_text(progress, question_data):
    """Форматирует текст вопроса"""
    progress_text = progress.get_progress_text()
    attempts_text = f" (Попытка: {progress.current_attempts + 1})" if progress.current_attempts > 0 else ""

    correct_count = len(question_data['correct_answers'])
    correct_info = f"\n📌 Правильных ответов: {correct_count}" if correct_count > 1 else ""

    if progress.mistakes_practice_mode:
        question_text = f"📝 {progress_text}{attempts_text}{correct_info}\nВопрос: {question_data['question']}"
    else:
        question_text = f"{progress_text}{attempts_text}{correct_info}\nВопрос: {question_data['question']}"

    # Показываем выбранные ответы
    if progress.selected_answers:
        selected_text = "\n\n✅ Выбрано: " + ", ".join(progress.selected_answers)
        question_text += selected_text

    return question_text


async def handle_user_not_found(update):
    """Обрабатывает случай, когда пользователь не найден"""
    text = "Тест не начат. Используйте /start_test"
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def handle_error(update, message):
    """Обрабатывает ошибки"""
    if update.callback_query:
        await update.callback_query.edit_message_text(message)
    else:
        await update.message.reply_text(message)


async def handle_answer_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора ответов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выбрал ответ: {query.data}")

    progress = user_data.get(user_id)

    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при выборе ответа")
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

    if not progress.current_shuffled_options:
        logger.error(f"Варианты ответов не найдены для пользователя {user_id}")
        await query.answer("Ошибка: варианты ответов не загружены", show_alert=True)
        return

    try:
        index = int(query.data.replace("select_", ""))
        if index < 0 or index >= len(progress.current_shuffled_options):
            logger.error(f"Неверный индекс ответа {index} для пользователя {user_id}")
            await query.answer("Ошибка: неверный вариант ответа", show_alert=True)
            return

        original_text = progress.current_shuffled_options[index]
        progress.toggle_answer_selection(original_text)
        await send_question(update, context, user_id)
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка обработки выбора ответа для пользователя {user_id}: {e}")
        await query.answer("Ошибка: не удалось обработать выбор", show_alert=True)


async def handle_answer_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отправки ответов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} отправил ответ")

    progress = user_data.get(user_id)

    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при отправке ответа")
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

    if not progress.current_question_data:
        logger.error(f"Вопрос не найден для пользователя {user_id} при отправке ответа")
        await query.edit_message_text("Ошибка: вопрос не найден")
        return

    if not progress.selected_answers:
        await query.answer("Сначала выберите хотя бы один ответ!", show_alert=True)
        return

    question_data = progress.current_question_data
    is_correct = progress.is_answer_correct(progress.selected_answers, question_data)

    user_answers_text = ", ".join(progress.selected_answers)
    correct_answers_text = ", ".join(question_data['correct_answers'])

    logger.info(f"Ответ пользователя {user_id}: {user_answers_text}, правильный: {is_correct}")

    if is_correct:
        progress.handle_correct_answer(question_data)
        result_text = f"✅ Правильно!\n{progress.get_progress_text()}"
    else:
        progress.handle_incorrect_answer(question_data, progress.selected_answers)
        result_text = f"❌ Неправильно!\nВаш ответ: {user_answers_text}\nПравильный ответ: {correct_answers_text}\n{progress.get_progress_text()}"

    # Создаем кнопки для продолжения
    keyboard = []
    if not progress.is_test_complete():
        keyboard.append([InlineKeyboardButton("Следующий вопрос →", callback_data="next_question")])
    else:
        if progress.mistakes_practice_mode:
            keyboard.append([InlineKeyboardButton("🏁 Завершить отработку", callback_data="finish_mistakes_practice")])
        else:
            keyboard.append([InlineKeyboardButton("🏁 Завершить тест", callback_data="finish_test_now")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            f"{result_text}\n\nНажмите для продолжения:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка отправки результата пользователю {user_id}: {e}")


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к следующему вопросу"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} переходит к следующему вопросу")

    progress = user_data.get(user_id)

    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при переходе к следующему вопросу")
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

    # В режиме отработки увеличиваем индекс при переходе
    if progress.mistakes_practice_mode and not progress.is_test_complete():
        progress.current_question_index += 1

    await send_question(update, context, user_id)


async def handle_end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик досрочного завершения теста"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил завершение теста")

    progress = user_data.get(user_id)

    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при запросе завершения теста")
        await query.edit_message_text("Тест не начат. Используйте /start_test")
        return

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
    logger.info(f"Пользователь {user_id} подтвердил завершение теста")

    await finish_test(update, context, user_id, early_exit=True)


async def continue_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продолжение теста после отмены выхода"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} продолжил тест")

    await send_question(update, context, user_id)


async def finish_test_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение теста после последнего вопроса"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} завершил тест")

    await finish_test(update, context, user_id)


async def finish_mistakes_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение отработки ошибок"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    progress = user_data.get(user_id)

    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при завершении отработки ошибок")
        await query.edit_message_text("Сессия не найдена")
        return

    if progress.mistakes:
        result_text = f"📊 Отработка завершена!\nОсталось ошибок: {len(progress.mistakes)}"
    else:
        result_text = "🎉 Поздравляем! Вы исправили все ошибки! 🏆"

    keyboard = [
        [InlineKeyboardButton("📝 Посмотреть ошибки", callback_data="view_mistakes")],
        [InlineKeyboardButton("🔄 Новый тест", callback_data="restart_test")],
        [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(result_text, reply_markup=reply_markup)


async def finish_test(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, early_exit=False):
    """Завершение теста и вывод результатов"""
    progress = user_data.get(user_id)
    if not progress:
        logger.error(f"Прогресс не найден для пользователя {user_id} при завершении теста")
        await handle_user_not_found(update)
        return

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
            f"Процент правильных: {progress.score / total_questions * 100:.1f}%\n\n"
        )

    if progress.mistakes:
        result_text += f"Ошибок: {len(progress.mistakes)}\n"
        result_text += "Используйте /my_mistakes для отработки ошибок"
    else:
        result_text += "Поздравляем! Все ответы правильные! 🏆"

    keyboard = []
    if progress.mistakes:
        keyboard.append([InlineKeyboardButton("📝 Отработать ошибки", callback_data="practice_mistakes")])
    keyboard.append([InlineKeyboardButton("🔄 Новый тест", callback_data="restart_test")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(result_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(result_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка завершения теста для пользователя {user_id}: {e}")


async def show_mistakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ошибки пользователя"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил просмотр ошибок")

    progress = user_data.get(user_id)

    if not progress:
        await update.message.reply_text("Вы еще не проходили тестирование. Используйте /start_test")
        return

    if not progress.mistakes:
        await update.message.reply_text("🎉 У вас нет ошибок! Отличный результат!")
        return

    mistakes_text = "📋 Ваши ошибки:\n\n"
    for i, mistake in enumerate(progress.mistakes, 1):
        mistakes_text += (
            f"{i}. Вопрос: {mistake['question']}\n"
            f" Ваш ответ: ❌ {mistake['user_answer']}\n"
            f" Правильный: ✅ {mistake['correct_answer']}\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("📝 Отработать ошибки", callback_data="practice_mistakes")],
        [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mistakes_text, reply_markup=reply_markup)


async def handle_mistakes_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с ошибками"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выполнил действие с ошибками: {query.data}")

    progress = user_data.get(user_id)

    if not progress:
        await query.edit_message_text("Сессия не найдена")
        return

    if query.data == "view_mistakes":
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
            [InlineKeyboardButton("📝 Отработать ошибки", callback_data="practice_mistakes")],
            [InlineKeyboardButton("🚪 Завершить", callback_data="end_mistakes_session")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mistakes_text, reply_markup=reply_markup)

    elif query.data == "restart_test":
        user_data[user_id] = UserProgress()
        user_data[user_id].initialize_test()
        await send_question(update, context, user_id)

    elif query.data == "practice_mistakes":
        if progress.mistakes:
            if progress.start_mistakes_practice():
                await send_question(update, context, user_id)
            else:
                await query.edit_message_text("Не удалось начать отработку ошибок.")
        else:
            await query.edit_message_text("У вас нет ошибок для отработки!")

    elif query.data == "end_mistakes_session":
        await query.edit_message_text("Работа с ошибками завершена. Используйте /start_test для нового теста.")

    elif query.data == "finish_mistakes_practice":
        await finish_mistakes_practice(update, context)


def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")

    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.error("Токен бота не установлен! Замените YOUR_BOT_TOKEN на реальный токен.")
        return

    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("start_test", start_test))
        application.add_handler(CommandHandler("my_mistakes", show_mistakes))

        # Регистрация обработчиков callback'ов
        application.add_handler(CallbackQueryHandler(handle_answer_selection, pattern="^select_"))
        application.add_handler(CallbackQueryHandler(handle_answer_submission, pattern="^submit_answers$"))
        application.add_handler(CallbackQueryHandler(next_question, pattern="^next_question$"))
        application.add_handler(CallbackQueryHandler(finish_test_now, pattern="^finish_test_now$"))
        application.add_handler(CallbackQueryHandler(finish_mistakes_practice, pattern="^finish_mistakes_practice$"))
        application.add_handler(CallbackQueryHandler(handle_end_test, pattern="^end_test$"))
        application.add_handler(CallbackQueryHandler(confirm_end_test, pattern="^confirm_end_test$"))
        application.add_handler(CallbackQueryHandler(continue_test, pattern="^continue_test$"))
        application.add_handler(CallbackQueryHandler(handle_mistakes_actions,
                                                     pattern="^(view_mistakes|restart_test|practice_mistakes|end_mistakes_session)$"))

        # Запуск бота
        logger.info("Бот успешно запущен и ожидает сообщений...")
        application.run_polling()

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
    finally:
        logger.info("Бот остановлен")


if __name__ == '__main__':
    main()