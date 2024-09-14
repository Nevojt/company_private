# Використовуємо офіційний образ Python
FROM python:3.10-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файли залежностей
COPY requirements.txt .

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код додатку
COPY . .

# Відкриваємо порт, якщо потрібно
EXPOSE 8080

# Запускаємо додаток
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
