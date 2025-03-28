import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
import logging
from datetime import datetime, timedelta
from sheets_api import get_service, get_guidelines, write_tests_to_sheet, generate_tests, write_test_results, read_sheet, split_into_pages, get_tests_for_topic
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

dotenv_path = '.env'
load_dotenv(dotenv_path)
token = os.getenv('API_TOKEN')
spreadsheet = os.getenv('SPREADSHEET_ID')
logging.basicConfig(level=logging.INFO)
def bot_init():
    bot = Bot(token=token)
    dp = Dispatcher()
    service = get_service()
    def get_menu_type(menu_type: str, page:int=1):
        keyboard = InlineKeyboardBuilder()
        if menu_type == 'main':
            keyboard.add(
                InlineKeyboardButton(text='Тестирование', callback_data='menu_testing'),
                InlineKeyboardButton(text='Методические указания', callback_data='menu_guidelines'),
                InlineKeyboardButton(text='Генерация тестов', callback_data='menu_generate_tests')
            )
            keyboard.adjust(1)
        elif menu_type == 'testing' or menu_type == 'guidelines' or menu_type == 'generate_test':
            topics = [
                "Тема 1", "Тема 2", "Тема 3", "Тема 4",
                "Тема 5", "Тема 6", "Тема 7", "Тема 8"
            ]
            items_per_page = 4
            start = (page - 1) * items_per_page
            end = start + items_per_page
            page_topics = topics[start:end]

            for topic in page_topics:
                keyboard.add(InlineKeyboardButton(text=topic, callback_data=f'{menu_type}_topic:{topic}'))
                keyboard.adjust(2)
            # Добавляем кнопки управления страницами
            if page > 1:
                keyboard.add(InlineKeyboardButton(text='⬅️', callback_data=f'{menu_type}_page:{page - 1}'))
            if end < len(topics):
                keyboard.add(InlineKeyboardButton(text='➡️', callback_data=f'{menu_type}_page:{page + 1}'))
            keyboard.adjust(2)
            keyboard.add(InlineKeyboardButton(text='Назад', callback_data='back_previous'))

        elif menu_type == 'guideline_pages':
            keyboard.add(
                InlineKeyboardButton(text='⬅️', callback_data='guideline_prev'),
                InlineKeyboardButton(text='➡️', callback_data='guideline_next')
            )
            keyboard.add(InlineKeyboardButton(text='Назад', callback_data='back_previous'))
        return keyboard

    class MenuKeeper:
        def __init__(self):
            self.menu_message_id = None
            self.chat_ids = {}  # Для работы с несколькими чатами
            self.guideline_message_ids = {}
            self.test_sessions = {}
            self.current_menu = {}  # Текущее меню для каждого чата
            self.menu_history = {}
            self.saved_messages = {}

        async def refresh_menu(self, chat_id: int, text: str = 'Меню', menu_type: str = 'main', page: int=1, update_history: bool = True):
            try:
                if update_history:
                    if chat_id not in self.menu_history:
                        self.menu_history[chat_id] = []
                    if self.current_menu.get(chat_id) is not None:
                        self.menu_history[chat_id].append(self.current_menu[chat_id])

                # Получаем клавиатуру для меню
                keyboard = get_menu_type(menu_type, page)

                # Если меню уже существует и его ID совпадает с сохраненным
                if self.menu_message_id:
                    # Пробуем обновить текущее меню (если оно существует)
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.menu_message_id,
                            text=text,
                            reply_markup=keyboard.as_markup()
                        )
                        self.current_menu[chat_id] = menu_type
                        # Меню уже актуально, ничего не делаем
                        return
                    except Exception:
                        try:
                            await bot.delete_message(chat_id, self.menu_message_id)
                        except Exception:
                            pass

                msg = await bot.send_message(chat_id, text, reply_markup=keyboard.as_markup())
                self.menu_message_id = msg.message_id
                self.current_menu[chat_id] = menu_type
            except Exception as e:
                print(f"Ошибка при обновлении меню: {e}")

    menu_keeper = MenuKeeper()

    @dp.message(Command('start'))
    async def cmd_start(message: Message):
        await menu_keeper.refresh_menu(message.chat.id)

    def process_guideline_material(material):
        """
        Заглушка для обработки материала с помощью нейросети
        Args:
            material: материал (текст, ссылка на видео, изображение и т.п.)
        Returns:
            Обработанный материал (пока возвращаем как есть)
        """
        # Здесь можно добавить вызов нейросети для обработки материала
        return material

    async def show_question(chat_id,message_id):
        session = menu_keeper.test_sessions[chat_id]
        current_index = session["current_index"]
        question = session["questions"][current_index]

        # Генерация клавиатуры
        keyboard = InlineKeyboardBuilder()

        for i, option in enumerate(question["options"]):
            keyboard.add(InlineKeyboardButton(text=option, callback_data=f"answer:{i}"))
        keyboard.adjust(2)
        if current_index > 0:
            keyboard.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_question"))
        if current_index < len(session["questions"]) - 1:
            keyboard.add(InlineKeyboardButton(text="➡️ Далее", callback_data="next_question"))
        keyboard.adjust(2)
        if current_index == len(session["questions"]) - 1:
            keyboard.add(InlineKeyboardButton(text="Завершить", callback_data="finish_test"))

        # Добавляем кнопку для показа выбранного ответа
        if current_index < len(session["answers"]):
            current_answer = session["answers"][current_index]
            keyboard.add(InlineKeyboardButton(text=f"Ваш ответ: {current_answer}", callback_data="show_answer"))

        # Отправляем вопрос
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Вопрос {current_index + 1} из {len(session['questions'])}\n\n{question['question']}",
            reply_markup = keyboard.as_markup()
        )

    async def show_guidelines(chat_id,message_id):
        session = menu_keeper.guideline_message_ids[chat_id]
        current_index = session["current"]
        page = session["pages"][current_index]

        # Формируем текст с номером страницы
        text = f"Страница {current_index + 1}/{len(session['pages'])}\n\n{page}"

        # Создаем клавиатуру
        keyboard = InlineKeyboardBuilder()
        if current_index > 0:
            keyboard.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="guideline_prev"))
        if current_index < len(session["pages"]) - 1:
            keyboard.add(InlineKeyboardButton(text="➡️ Далее", callback_data="guideline_next"))
        keyboard.adjust(2)
        keyboard.add(InlineKeyboardButton(text="Назад к темам", callback_data="back_to_topics"))
        keyboard.adjust(2)

        # Отправляем/обновляем сообщение
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard.as_markup()
        )
    def has_user_passed_test(service, spreadsheet_id, sheet_name, tg_id, topic):
        """
        Проверяет, проходил ли пользователь тест по данной теме
        Args:
            service: сервис Google Sheets
            spreadsheet_id: ID таблицы
            sheet_name: имя листа
            tg_id: ID пользователя
            topic: тема теста
        Returns:
            True, если пользователь уже проходил тест, иначе False
        """
        range_name = f'{sheet_name}!A:E'  # Предполагаем, что данные хранятся в колонках A-E
        data = read_sheet(service, spreadsheet_id, range_name)

        for row in data:
            if len(row) > 1 and row[1] == topic and row[0] == str(tg_id):
                return True
        return False

    def can_user_retake_test(service, spreadsheet_id, sheet_name, tg_id, topic):
        """
        Проверяет, может ли пользователь перепройти тест
        Args:
            service: сервис Google Sheets
            spreadsheet_id: ID таблицы
            sheet_name: имя листа
            tg_id: ID пользователя
            topic: тема теста
        Returns:
            True, если прошло 24 часа с момента последнего прохождения, иначе False
        """
        range_name = f'{sheet_name}!A:E'  # Предполагаем, что данные хранятся в колонках A-E
        data = read_sheet(service, spreadsheet_id, range_name)

        for row in data:
            if len(row) > 1 and row[1] == topic and row[0] == str(tg_id):
                last_passed_date = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - last_passed_date < timedelta(hours=24):
                    return False
        return True

    @dp.callback_query(lambda c: c.data == 'menu_testing')
    async def menu_testing_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Выберите тему для тестирования', menu_type='testing', page=1, update_history=False)

    @dp.callback_query(lambda c: c.data == 'menu_guidelines')
    async def menu_guidelines_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Методические указания',menu_type='guidelines', page=1)

    @dp.callback_query(lambda c: c.data.startswith('testing_page'))
    async def testing_page_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        _, page = callback_query.data.split(':')
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Выберите тему для тестирования', menu_type='testing', page=int(page), update_history=False)

    @dp.callback_query(lambda c: c.data.startswith('guidelines_page'))
    async def guidelines_page_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        _, page = callback_query.data.split(':')
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Методические указания', menu_type='guidelines', page=int(page), update_history=False)

    @dp.callback_query(lambda c: c.data == 'back_previous')
    async def process_back_previous_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id

        # Удаляем сообщения МУ, если они есть
        if chat_id in menu_keeper.guideline_message_ids:
            for msg_id in menu_keeper.guideline_message_ids[chat_id]:
                try:
                    await bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass
            del menu_keeper.guideline_message_ids[chat_id]

        # Получаем последнее меню из истории
        if chat_id in menu_keeper.menu_history and menu_keeper.menu_history[chat_id]:
            previous_menu = menu_keeper.menu_history[chat_id].pop()  # Удаляем последний элемент из истории
        else:
            previous_menu = 'main'
        await menu_keeper.refresh_menu(chat_id, menu_type=previous_menu,update_history=False)

    @dp.callback_query(lambda c: c.data.startswith('guidelines_topic'))
    async def send_guidelines(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        topic = callback_query.data.split(':')[1]

        # Получаем методические указания
        guidelines = get_guidelines(service, spreadsheet, 'Лист1', topic)
        if not guidelines:
            await callback_query.message.answer("Методические указания отсутствуют")
            return

        # Разбиваем на страницы
        pages = []
        for guideline in guidelines:
            pages.extend(split_into_pages(guideline))  # Используем вашу функцию разбиения

        menu_keeper.guideline_message_ids[chat_id] = {
            'current': 0,
            'pages': pages,
            'topic': topic
        }

        await show_guidelines(chat_id, message_id)

    @dp.callback_query(lambda c: c.data in ['guideline_prev', 'guideline_next'])
    async def handle_pagination(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        direction = 1 if callback_query.data == 'guideline_next' else -1
        if direction>0:
            menu_keeper.guideline_message_ids[chat_id]["current"] += 1
        else:
            menu_keeper.guideline_message_ids[chat_id]["current"] -= 1
        await show_guidelines(chat_id, message_id)


    @dp.callback_query(lambda c: c.data == 'back_to_topics')
    async def back_to_topics(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id

        # Возвращаемся к меню тем
        await menu_keeper.refresh_menu(chat_id, menu_type='guidelines', page=1,update_history=False)

    @dp.callback_query(lambda c: c.data.startswith('testing_topic'))
    async def start_test(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        topic = callback_query.data.split(':')[1]

        #if has_user_passed_test(service, 'TEST_SPREADSHEET_ID', 'UserAnswers', chat_id, topic):
        #    await callback_query.message.answer(
        #        "Вы уже проходили этот тест. Повторное прохождение будет доступно через 24 часа.")
        #    return

            # Проверяем, может ли пользователь перепройти тест
        #if not can_user_retake_test(service, 'TEST_SPREADSHEET_ID', 'UserAnswers', chat_id, topic):
        #    await callback_query.message.answer(
        #        "Вы уже проходили этот тест. Повторное прохождение будет доступно через 24 часа.")
        #    return

        tests = get_tests_for_topic(service, spreadsheet, 'Лист2', topic)

        if not tests:
            await callback_query.message.answer("Тесты по данной теме отсутствуют")
            return

        menu_keeper.test_sessions[chat_id] = {
            "topic": topic,
            "questions": tests,
            "current_index": 0,
            "answers": []
        }

        await show_question(chat_id,message_id)

    @dp.callback_query(lambda c: c.data == "prev_question")
    async def previous_question(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        menu_keeper.test_sessions[chat_id]["current_index"] -= 1
        await show_question(chat_id,message_id)

    @dp.callback_query(lambda c: c.data == "next_question")
    async def next_question(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id

        session = menu_keeper.test_sessions[chat_id]
        current_index = session["current_index"]
        if len(session["answers"])<=current_index:
            session["answers"].append(0)
        menu_keeper.test_sessions[chat_id]["current_index"] += 1
        await show_question(chat_id,message_id)

    @dp.callback_query(lambda c: c.data == "show_answer")
    async def show_answer(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        session = menu_keeper.test_sessions[chat_id]
        current_index = session["current_index"]

        # Получаем текущий ответ пользователя
        if current_index < len(session["answers"]):
            answer = session["answers"][current_index]
        else:
            answer = "Ответ не выбран."

        # Отправляем сообщение с ответом
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Вопрос {current_index + 1} из {len(session['questions'])}\n\n"
                 f"{session['questions'][current_index]['question']}\n\n"
                 f"Ваш текущий ответ: {answer}",
            reply_markup=callback_query.message.reply_markup
        )

    @dp.callback_query(lambda c: c.data.startswith('answer:'))
    async def process_answer(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        answer_index = int(callback_query.data.split(':')[1])  # Получаем индекс ответа

        # Получаем текущую сессию теста
        session = menu_keeper.test_sessions[chat_id]
        current_index = session["current_index"]

        # Сохраняем ответ пользователя
        if current_index < len(session["answers"]):
            session["answers"][current_index] = answer_index + 1
        else:
            session["answers"].append(answer_index + 1)

        # Обновляем сообщение с вопросом, чтобы показать выбранный ответ
        await show_question(chat_id, message_id)

    @dp.callback_query(lambda c: c.data == "finish_test")
    async def finish_test(callback_query: CallbackQuery):
        await callback_query.answer()
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        session = menu_keeper.test_sessions[chat_id]

        if not session:
            await callback_query.message.answer("Ошибка тестирования")
            return

        # Подсчёт баллов
        correct = 0
        answers = []
        for i, q in enumerate(session["questions"]):
            user_answer = session["answers"][i] if i < len(session["answers"]) else None
            answers.append(user_answer)
            if user_answer == q["answer"]:
                correct += 1

        # Показываем результат
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="К темам", callback_data="menu_testing"))
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Ваш результат: {correct} из {len(session['questions'])}",
            reply_markup=keyboard.as_markup()
        )

        del menu_keeper.test_sessions[chat_id]

    @dp.callback_query(lambda c: c.data == 'menu_generate_tests')
    async def menu_generate_tests_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Сгенерировать тест по теме',menu_type='generate_test', page=1)

    @dp.callback_query(lambda c: c.data.startswith('generate_test_page'))
    async def generate_test_page_callback(callback_query: CallbackQuery):
        await callback_query.answer()
        _, page = callback_query.data.split(':')
        await menu_keeper.refresh_menu(callback_query.message.chat.id, text='Сгенерировать тест по теме', menu_type='generate_test', page=int(page),
                                       update_history=False)


    @dp.callback_query(lambda c: c.data.startswith('generate_test_topic'))
    async def generate_and_send_tests(callback_query: CallbackQuery):
        await callback_query.answer()
        topic = callback_query.data.split(':')[1]

        # Генерация тестов (заглушка)
        tests = generate_tests(service, spreadsheet, 'Лист1', topic)

        # Запись тестов в таблицу
        write_tests_to_sheet(service, spreadsheet, 'Лист2', topic, tests)

        await callback_query.message.answer(f"Тесты по теме '{topic}' сгенерированы и записаны в таблицу.")

    return bot, dp


async def start(bot:Bot,dp:Dispatcher):
    await bot.delete_webhook()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()