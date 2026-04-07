# 🌐 Доступ из локальной сети

## 🚀 Быстрый старт

### 1. Запусти сервер:

```bash
cd "/Users/egor/график работы екц"
./run_server.sh
```

Или вручную:

```bash
source .venv/bin/activate
uvicorn app.main_new:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Узнай свой IP:

```bash
ipconfig getifaddr en0
```

**Пример:** `192.168.1.100`

### 3. Открой с любого устройства:

```
http://192.168.1.100:8001
```

---

## 📱 Примеры устройств

### iPhone / iPad:

1. Подключись к тому же WiFi
2. Открой Safari
3. Введи: `http://<IP-Мака>:8001`
4. Готово! 🎉

### Android:

1. Подключись к тому же WiFi
2. Открой Chrome
3. Введи: `http://<IP-Мака>:8001`

### Другой Mac/PC:

1. Подключись к тому же WiFi
2. Открой любой браузер
3. Введи: `http://<IP-Мака>:8001`

---

## 🔧 Настройка брандмауэра

### Если не подключается:

**Mac OS:**

1.  → Системные настройки → Защита и безопасность
2. Вкладка "Брандмауэр"
3. Разблокируй (нажми на замок)
4. "Добавить приложение" → выбери Python
5. Разрешить входящие подключения

**Или через терминал:**

```bash
# Разрешить Python
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblock /usr/bin/python3
```

---

## 📊 Проверка подключения

### 1. Проверь что сервер слушает:

```bash
lsof -i :8001
```

Должно показать:

```
COMMAND   PID USER   TYPE   DEVICE
uvicorn  12345 egor   IPv4   TCP *:8001 (LISTEN)
```

### 2. Проверь IP:

```bash
ipconfig getifaddr en0
```

### 3. Протестируй с того же Mac:

```bash
curl http://127.0.0.1:8001
```

### 4. Протестируй с другого устройства:

```bash
# С телефона или другого компьютера
curl http://<IP-Мака>:8001
```

---

## 🎯 Сценарии использования

### Сценарий 1: Команда в офисе

**Ситуация:** 5 человек в офисе, нужно совместно работать с графиком

**Решение:**

1. Запускаешь сервер на одном Mac
2. Все открывают `http://<IP>:8001` со своих устройств
3. Работают одновременно!

**Преимущества:**

- ✅ Не нужен интернет
- ✅ Быстро (локальная сеть)
- ✅ Безопасно (только свои)

---

### Сценарий 2: Руководитель и сотрудники

**Ситуация:** Руководитель составляет график, сотрудники смотрят

**Решение:**

1. Руководитель запускает сервер
2. Скидывает ссылку в чат: `http://192.168.1.100:8001`
3. Сотрудники открывают с телефонов
4. Каждый видит свой график через `/my-schedule`

---

### Сценарий 3: Планерка

**Ситуация:** Обсуждение графика на встрече

**Решение:**

1. Подключаешь Mac к проектору
2. Запускаешь сервер
3. Все видят экран
4. Можно редактировать в реальном времени!

---

## ⚙️ Продвинутые настройки

### Сменить порт:

```bash
uvicorn app.main_new:app --host 0.0.0.0 --port 8080
```

Тогда открывай: `http://<IP>:8080`

### Запуск в фоне:

```bash
# Используем nohup
nohup uvicorn app.main_new:app --host 0.0.0.0 --port 8001 &

# Или screen
screen -S ekc-server
uvicorn app.main_new:app --host 0.0.0.0 --port 8001
# Ctrl+A, D чтобы отцепиться
```

### Автозапуск при старте Mac:

Создай LaunchAgent:

```bash
nano ~/Library/LaunchAgents/com.ekc.scheduler.plist
```

Вставь:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ekc.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/egor/график работы екц/run_server.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ekc.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ekc.err</string>
</dict>
</plist>
```

Сохрань (`Ctrl+O`, `Enter`, `Ctrl+X`):

```bash
launchctl load ~/Library/LaunchAgents/com.ekc.scheduler.plist
```

---

## 🔒 Безопасность

### Важно:

⚠️ **Сейчас нет аутентификации!** Любой в WiFi может зайти.

**Для офиса это ок** (своя сеть), но для публичных сетей:

### Вариант 1: Пароль через .htpasswd

```bash
# Установи apache2-utils
brew install apache2-utils

# Создай файл с паролем
htpasswd -c .htpasswd admin
# Введи пароль

# Добавь в main.py middleware
```

### Вариант 2: Только для своих IP

```python
from fastapi import Request, HTTPException

@app.middleware("http")
async def check_ip(request: Request, call_next):
    client_ip = request.client.host
    allowed_ips = ["192.168.1.", "10.0.0."]  # Твои подсети
    
    if not any(client_ip.startswith(ip) for ip in allowed_ips):
        raise HTTPException(status_code=403, detail="Access denied")
    
    response = await call_next(request)
    return response
```

### Вариант 3: HTTPS (SSL)

```bash
# Создай самоподписанный сертификат
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# Запусти с SSL
uvicorn app.main_new:app --host 0.0.0.0 --port 8001 --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

Тогда открывай: `https://<IP>:8001`

---

## 📈 Производительность

### Для команды 5-10 человек:

```bash
# Стандартный uvicorn отлично справится
uvicorn app.main_new:app --host 0.0.0.0 --port 8001
```

### Для 20+ человек:

```bash
# Используем gunicorn с workers
gunicorn app.main_new:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

---

## 🐛 Решение проблем

### "Connection refused"

**Причина:** Сервер не запущен или не на том IP

**Решение:**

```bash
# Проверь что сервер работает
ps aux | grep uvicorn

# Проверь IP
ipconfig getifaddr en0

# Перезапусти
./run_server.sh
```

### "Timeout"

**Причина:** Брандмауэр блокирует

**Решение:**

```bash
# Временно отключи брандмауэр для теста
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off

# Или разреши Python
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblock /usr/bin/python3
```

### "Device not found"

**Причина:** Устройство не в той WiFi сети

**Решение:**

- Проверь что оба устройства в одной сети
- Переподключись к WiFi
- Попробуй гостевую сеть (если есть)

---

## 📱 Тест с мобильного

### 1. Открой браузер на телефоне

### 2. Введи: `http://<IP-Мака>:8001`

### 3. Должно открыться:

```
┌─────────────────────────────┐
│   ЕКЦ График              │
│  Планировщик смен          │
├─────────────────────────────┤
│  🏠 Главная                │
│  👥 Сотрудники             │
│  📋 Ограничения            │
│  📅 Календарь              │
│  📊 График                 │
│  ⚙️ Настройки              │
└─────────────────────────────┘
```

### 4. Попробуй перейти в `/my-schedule`

---

## 🎯 Чек-лист готовности

- Сервер запущен с `--host 0.0.0.0`
- IP адрес известен
- Брандмауэр настроен
- Тест с того же Mac: ✅
- Тест с телефона: ✅
- Тест с другого компьютера: ✅

---

## 💡 Советы

1. **Запиши IP** — чтобы не искать каждый раз
2. **Используй статический IP** — в настройках роутера
3. **Создай ярлык** — на телефоне на главный экран
4. **QR-код** — сгенерируй для быстрого доступа

---

**Готово! Теперь приложение доступно всей команде!** 🎉