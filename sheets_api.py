from googleapiclient.discovery import build
from google.oauth2 import service_account
import re

def get_service():
    """Функция для создания сервиса Google Sheets"""
    # Используем сервисный аккаунт
    creds = service_account.Credentials.from_service_account_file(
        'service_account_key.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )

    service = build('sheets', 'v4', credentials=creds)
    return service

def split_into_pages(text, max_length=4000):
    """Разбивает текст на страницы с учетом абзацев и предложений"""
    pages = []
    current_page = []
    current_length = 0

    # Разбиваем на абзацы
    paragraphs = re.split(r'\n\s*\n', text.strip())

    for para in paragraphs:
        if len(para) > max_length:
            # Разбиваем длинные абзацы на предложения
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sent in sentences:
                if current_length + len(sent) + 1 > max_length:
                    pages.append('\n'.join(current_page))
                    current_page = []
                    current_length = 0
                current_page.append(sent.strip())
                current_length += len(sent.strip()) + 1
            if current_page:
                pages.append('\n'.join(current_page))
                current_page = []
                current_length = 0
        else:
            if current_length + len(para) + 1 > max_length:
                pages.append('\n'.join(current_page))
                current_page = []
                current_length = 0
            current_page.append(para.strip())
            current_length += len(para.strip()) + 1
    if current_page:
        pages.append('\n'.join(current_page))
    return pages

def read_sheet(service, spreadsheet_id, range_name):
    """Функция для чтения данных из таблицы"""
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                range=range_name).execute()
    values = result.get('values', [])
    return values

def add_guidelines_from_file(service, spreadsheet_id, sheet_name, topic, file_path):
    """Добавляет методическое указание из файла в таблицу"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pages = split_into_pages(content)
    rows = []
    for idx, page in enumerate(pages, 1):
        rows.append([topic, idx, page])

    body = {'values': rows}
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()
    print(f"Добавлено {len(rows)} страниц для темы '{topic}'")

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
    range_name = f"{sheet_name}!A:C"
    data = read_sheet(service, spreadsheet_id, range_name)

    guidelines = []
    for row in data:
        if len(row) >= 3 and row[0].strip() == topic:  # Проверяем, что строка содержит хотя бы 3 столбца и тема совпадает
            guidelines.append(row[2].strip())  # Добавляем текст методического указания

    return guidelines


def generate_tests(service, spreadsheet_id, guidelines_sheet, topic):
    """Генерирует тест на основе методических материалов"""
    guidelines = get_guidelines(service, spreadsheet_id, guidelines_sheet, topic)

    if not guidelines:
        return []

    full_text = ' '.join(guidelines)

    # обращение к апи модели для генераии теста
    # ...
    # ...

    tests = []
    for i in range(10):
        question = f'Вопрос {i+1}'
        options = ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"]
        tests.append({
            "question": question,
            "options": options,
            "answer": 1 # правильный ответ
        })

    return tests


def get_tests_for_topic(service, spreadsheet_id, sheet_name, topic):
    data = read_sheet(service, spreadsheet_id, sheet_name)
    topic_rows = [row for row in data if row and row[0] == topic]

    if not topic_rows:
        return None

    import random
    selected_row = random.choice(topic_rows)

    tests = []
    for i in range(1, len(selected_row), 3):
        if i + 2 >= len(selected_row):
            break
        question = selected_row[i]
        options = selected_row[i + 1].split('|') if selected_row[i + 1] else []
        answer = int(selected_row[i + 2]) if selected_row[i + 2].isdigit() else 0

        tests.append({
            "question": question,
            "options": options,
            "answer": answer
        })
    return tests
def write_tests_to_sheet(service, spreadsheet_id, test_sheet, topic, tests):
    row = [topic]
    for test in tests:
        row.append(test['question']+'\n'+", ".join(test['options']))
        row.append("|".join(test['options']))
        row.append(test['answer'])

    add_row_append(service, spreadsheet_id, test_sheet, row)

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
    row = [tg_id, topic, date, '|'.join(user_answers), score]
    add_row_append(service, spreadsheet_id, sheet_name, row)