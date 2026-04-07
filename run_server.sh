#!/bin/bash

# ЕКЦ График - Запуск сервера для локальной сети

echo "🚀 ЕКЦ График - Запуск сервера"
echo "================================"
echo ""

# Активируем виртуальное окружение
source .venv/bin/activate

# Получаем локальный IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")

echo "📡 Твой локальный IP: $LOCAL_IP"
echo ""
echo "🌐 Приложение будет доступно по адресам:"
echo "   • На этом компьютере: http://127.0.0.1:8001"
echo "   • В локальной сети:   http://$LOCAL_IP:8001"
echo ""
echo "📱 Открой с телефона/планшета:"
echo "   http://$LOCAL_IP:8001"
echo ""
echo "⏹️  Для остановки нажми: Ctrl+C"
echo "================================"
echo ""

# Запускаем сервер
uvicorn app.main_new:app --host 0.0.0.0 --port 8001 --reload
