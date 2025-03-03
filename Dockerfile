# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код проекта
COPY . .

# Указываем переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда для запуска бота
CMD ["python", "main.py"]