from googleapiclient.discovery import build
from google.oauth2 import service_account

def get_service():
    """Функция для создания сервиса Google Sheets"""
    # Используем сервисный аккаунт
    creds = service_account.Credentials.from_service_account_file(
        'service_account_key.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )

    service = build('sheets', 'v4', credentials=creds)
    return service

def read_sheet(service, spreadsheet_id, range_name):
    """Функция для чтения данных из таблицы"""
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                range=range_name).execute()
    values = result.get('values', [])
    return values


def write_to_sheet(service, spreadsheet_id, range_name, values):
    """Функция для записи данных в таблицу"""
    body = {
        'values': values
    }
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body=body).execute()
    print(f'{result.get("updatedCells")} ячеек обновлено.')


def add_row_append(service, spreadsheet_id, range_name, values):
    """
    Добавление строки в конец таблицы

    Args:
        service: сервис Google Sheets
        spreadsheet_id: ID таблицы
        range_name: имя листа (например, 'Лист1')
        values: список значений для добавления
    """
    body = {
        'values': [values]
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body=body).execute()
    print(f'Добавлено {len(values)} значений в строку {result.get("updates").get("updatedRows")}')


def add_row_update(service, spreadsheet_id, range_name, values):
    """
    Обновление строки в указанной позиции

    Args:
        service: сервис Google Sheets
        spreadsheet_id: ID таблицы
        range_name: диапазон ячеек (например, 'Лист1!A2:B2') *обязательно диапазон = количество элементов для добавления
        values: список значений для добавления
    """
    body = {
        'values': [values]
    }
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body=body).execute()
    print(f'Обновлено {len(values)} значений в позиции {range_name}')


def get_guidelines(service, spreadsheet_id, sheet_name, topic):
    """
    Получение методических указаний из Google Sheets по теме
    Args:
        service: сервис Google Sheets
        spreadsheet_id: ID таблицы
        sheet_name: имя листа
        topic: тема для фильтрации

    Returns:
        Список материалов по теме (ссылки, тексты и т.п.)
    """
    range_name = f'{sheet_name}!A:B'  # Предполагаем, что в колонке A хранятся темы, а в B материалы
    data = read_sheet(service, spreadsheet_id, range_name)

    guidelines = [row[1] for row in data if len(row) > 1 and row[0].strip() == topic]
    return guidelines


def generate_tests(topic):
    """
    Генерация тестов по теме (заглушка)
    Args:
        topic: тема для теста

    Returns:
        Список сгенерированных вопросов (временно 10)
    """
    return [
        {"question": f"Вопрос {i + 1} по теме {topic}",
         "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
         "answer": "Вариант 1"} for i in range(10)
    ]

def write_tests_to_sheet(service, spreadsheet_id, sheet_name, topic, tests):
    """
    Запись тестов в таблицу Google Sheets
    Args:
        service: сервис Google Sheets
        spreadsheet_id: ID таблицы
        sheet_name: имя листа
        topic: тема тестов
        tests: список тестов
    """
    rows = [[
        topic,
        f"Вопрос: {test['question']}, Варианты: {', '.join(test['options'])}, Ответ: {test['answer']}"
    ] for test in tests]

    add_row_append(service, spreadsheet_id, sheet_name, rows)

def write_test_results(service, spreadsheet_id, sheet_name, tg_id, topic, date, user_answers, score):
    """
    Запись результата прохождения теста
    Args:
        service: сервис Google Sheets
        spreadsheet_id: ID таблицы
        sheet_name: имя листа
        tg_id: ID пользователя
        topic: тема теста
        date: дата прохождения
        user_answers: ответы пользователя
        score: количество баллов
    """
    row = [tg_id, topic, date, ', '.join(user_answers), score]
    add_row_append(service, spreadsheet_id, sheet_name, row)