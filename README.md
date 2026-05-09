# MK_FuckPay 🎁💸

Демонстрация **критической уязвимости** в Telegram-ботах с обработкой платежей через Звёзды (⭐).
Дыра которую допускают на удивление даже крупные боты!

Проект включает:
- **DemoOfVuln.py** — Aiogram бот с двумя методами оплаты (уязвимый и защищённый)
- **MK_FuckPayments.plugin** — Нашумевший плагин из первоисточника.

---

## 📖 Предистория

### Откуда всё началось

Чат поддержавших **exteraGram** — модифицированного Telegram-клиента — активно разрабатывали расширения для клиента. В один момент кто-то из чата создал плагин, который позволял визуально имитировать баланс в Звёздах, TON и Подарки.

### Первое открытие уязвимости

Один из пользователей чата саппортеров ([@muralovty](https://t.me/muralovty)) решил провести тест: использовать этот плагин при оплате в Звёздах. И вот тут все ахуели — **платёж прошёл успешно, и подписка была выдана без реальной оплаты**. Так была обнаружена **критическая уязвимость** в системе обработки платежей Telegram-ботов.

### Массовое распространение

На волне этого открытия я ([@mkultra6969](https://t.me/mkultra6969)) взял исходный плагин и начал изучать почему оно работает, вычистил его от лишнего и выложил упрощённую/немного измененную версию в своём канале [@MKplusULTRA](https://t.me/MKplusULTRA) под названием **MK_FuckPayments.plugin**.

После публикации пользователи активно начали **обчищать каждый попавшийся бот**, проверяя уязвимость. К счастью, оригинальные посты и плагин пришлось удалить в течение часа из-за всего этого пиздеца.

### Памятная дата

**🕯️06.11.2025** — день, когда эта уязвимость получила массовое распространение.

*Спасибо exteraGram Supporters⭐ и всем кто участвовал. Было весело, хоть и некрасиво.*


## 📌 Как работает уязвимость

### Проблема: Выдача товара в pre-checkout

**Уязвимые боты** отправляют товар/контент сразу после `pre_checkout_query.answer(ok=True)`, не дожидаясь реального `successful_payment` от серверов.

### Атака через плагин

Плагин **MK_FuckPayments** работает на уровне Telegram-клиента и перехватывает запрос оплаты:

1. **Перехват TL_payments_sendStarsForm** — плагин ловит запрос отправки платёжной формы
2. **Подмена ответа** — вместо реальной формы оплаты показывается фейковое окно `TL_payments_paymentResult`
3. **Фейковый success** — клиент закрывает форму и показывает пользователю сообщение об успехе
4. **Выдача товара** — уязвимый бот отправляет товар в `pre_checkout` обработчике (без реальной оплаты!)

### Результат

```
Пользователь:      Плагин:                    Бот:
  ✓ Видит success  ✓ Показывает success       ✗ Выдаёт товар (БЕЗ ОПЛАТЫ!)
  ✓ Получает товар ✓ Деньги не списались
```

---

## 🎯 Две реализации в коде

### 1️⃣ УЯЗВИМЫЙ метод: `/simple_payment`

```python
@dp.pre_checkout_query(lambda q: q.invoice_payload == "simple_payment")
async def process_simple_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)  # ✓ OK от плагина

    # ⚠️ ВЫДАЁМ ТОВАР ЗДЕСЬ (БЕЗ ПРОВЕРКИ)
    await bot.send_message(user_id, "Вот твой контент!")
```

**Проблемы:**
- ❌ Простой payload без подписи (`"simple_payment"`)
- ❌ Нет проверки `telegram_payment_charge_id`
- ❌ Товар выдаётся только по `pre_checkout` (дальше не ждёт!)
- ❌ Плагин это использует, т.к. `successful_payment` не может сгенерировать

---

### 2️⃣ ЗАЩИЩЁННЫЙ метод: `/secure_payment`

```python
async def cmd_secure_payment(message: Message):
    user_id = message.from_user.id
    timestamp = int(datetime.now().timestamp())

    # 🛡️ Подписываем payload HMAC-SHA256
    signature = generate_signature(user_id, timestamp, amount=10)
    payment_id = f"secure_{user_id}_{timestamp}_{signature}"

    # Сохраняем данные для проверки
    pending_payments[payment_id] = {
        "user_id": user_id,
        "amount": 10,
        "created_at": datetime.now(),
        "pre_checkout_ok": False,
        "validated": False  # ← Товар НЕ выдан!
    }

    await bot.send_invoice(..., payload=payment_id)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment_id = message.successful_payment.invoice_payload

    # ✓ Проверяем подпись
    # ✓ Проверяем telegram_payment_charge_id
    # ✓ ТОЛЬКО ПОТОМ реально выдаём товар
    if verify_signature_and_charge_id(payment_id, message.successful_payment):
        await bot.send_message(user_id, "Платёж подтвержден! Вот твой контент!")
```

**Защита:**
- ✅ HMAC-подпись в payload (`secure_user_1234_1699...`)
- ✅ Таймштамп для предотвращения переиспользования
- ✅ **НЕ выдаёт** товар в `pre_checkout`
- ✅ Ожидает реального `successful_payment` с `telegram_payment_charge_id`
- ✅ Плагин НЕ может обойти (не может сгенерировать валидную подпись)

---

## 🔐 Как защитить свой бот

### ✅ Правила безопасности

1. **Никогда** не выдавайте товар в `pre_checkout` обработчике
   ```python
   # ❌ НЕПРАВИЛЬНО
   @dp.pre_checkout_query(...)
   async def bad(query):
       await query.answer(ok=True)
       send_content()  # УЯЗВИМО!

   # ✅ ПРАВИЛЬНО
   @dp.pre_checkout_query(...)
   async def good(query):
       await query.answer(ok=True)  # Только подтверждение!
   ```

2. **Используйте HMAC-подписи** в payload
   ```python
   signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
   payload = f"secure_{user_id}_{timestamp}_{signature}"
   ```

3. **Проверяйте `telegram_payment_charge_id`**
   ```python
   @dp.message(F.successful_payment)
   async def on_payment(message: Message):
       charge_id = message.successful_payment.telegram_payment_charge_id
       # Плагин НЕ может подделать это поле!
       validate_payment(charge_id)
   ```

4. **Добавьте таймстамп** для предотвращения переиспользования
   ```python
   # Отклоняем платежи старше 5 минут
   if datetime.now() - payment_time > timedelta(minutes=5):
       return False
   ```

---

## 🛠️ Установка и использование

### Требования
```bash
pip install aiogram
```

### Запуск демо-бота
```bash
python DemoOfVuln.py
```

### Команды бота
- `/start` — Информация о методах
- `/simple_payment` — **УЯЗВИМЫЙ** метод (обходится плагином)
- `/secure_payment` — **ЗАЩИЩЁННЫЙ** метод (плагин НЕ может обойти)

---

## ⚠️ ВАЖНО

Этот проект — **образовательная демонстрация** уязвимости в платёжных системах Telegram-ботов.

**Используется в целях:**
- 🔍 Исследования безопасности
- 📚 Обучения разработчиков в первую очередь))))) 
- 🧪 Тестирования защиты

**Не используйте для:**
- 💰 Мошенничества или краж - это реально плохо.
- 🎁 Выдачи контента без реальной оплаты
- 🚫 Нарушения правил Telegram

---

## 👨‍💻 Авторы

- **@mkultra6969** - Этот README, бот и форк плагина
- **@muralovty** - Первооткрыватель бага
- И еще кто-то но я не помню их @username

---

## 📖 Справка

### Поток платежа (нормальный)
```
Бот отправляет инвойс
    ↓
Пользователь жмёт "Купить"
    ↓
Telegram → pre_checkout_query
    ↓
Бот отвечает ok=True
    ↓
Пользователь вводит пароль / платит реально
    ↓
Telegram → successful_payment (+ charge_id)
    ↓
Бот отправляет товар
```

### Поток атаки (плагин)
```
Бот отправляет инвойс
    ↓
Плагин перехватывает TL_payments_sendStarsForm
    ↓
Плагин показывает фейковое окно TL_payments_paymentResult
    ↓
Бот получает pre_checkout_query
    ↓
Бот отвечает ok=True
    ↓
⚠️ УЯЗВИМЫЙ БОТ ВЫДАЁТ ТОВАР (БЕЗ ОПЛАТЫ!)
    ↓
Реального successful_payment не приходит
```

---

## 📝 Лицензия

WTFPL - Мне как всегда похуй кто и что будет с этим делать, уже хайпануло без меня.

---

**⭐ Поставь звезду умоляю.**
