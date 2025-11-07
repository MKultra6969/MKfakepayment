import logging
import hmac
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import PreCheckoutQuery, Message, LabeledPrice
import asyncio
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = ""
PROVIDER_TOKEN = "" # должно быть пустое, не трогай

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SECRET_KEY = "СУУУУПЕР_СЕКРЕТНЫЙ_КЛЮЧ" #для теста можно не менять

pending_payments = {}


def generate_signature(user_id: int, timestamp: int, amount: int) -> str:
    """Генерирует HMAC подпись для защищенного платежа"""
    data = f"{user_id}:{timestamp}:{amount}"
    return hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_signature(payload: str, user_id: int, amount: int) -> bool:
    """Проверяет HMAC подпись"""
    try:
        parts = payload.split("_")
        if len(parts) != 4 or parts[0] != "secure":
            return False

        stored_user = int(parts[1])
        timestamp = int(parts[2])
        stored_sig = parts[3]

        if stored_user != user_id:
            logger.warning(f"❌ User ID mismatch: expected {stored_user}, got {user_id}")
            return False

        expected_sig = generate_signature(user_id, timestamp, amount)
        return hmac.compare_digest(stored_sig, expected_sig)

    except (ValueError, IndexError) as e:
        logger.error(f"Signature verification error: {e}")
        return False


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🌟 <b>Демонстрация защиты от фейковых платежей</b>\n\n"
        "💳 /simple_payment - <b>ДЫРЯВЫЙ метод</b>\n"
        "   └ Обходится плагином MK_FuckPayments\n\n"
        "🔒 /secure_payment - <b>ЗАЩИЩЁННЫЙ метод</b>\n"
        "   └ Защищен от плагина достаточными проверками\n\n"
        "Цена: 10 ⭐\n\n"
        "ℹ️ После pre-checkout проверьте чат - там появится информация!"
        "By @mkultra6969 & @MKextera",
        parse_mode="HTML"
    )


# ==================== УЯЗВИМЫЙ МЕТОД ====================

@dp.message(Command("simple_payment"))
async def cmd_simple_payment(message: Message):
    """
    УЯЗВИМЫЙ метод - обходится плагином!

    Проблемы:
    1. Простой payload без подписи
    2. Нет проверки telegram_payment_charge_id
    3. Выдает товар только по pre-checkout (плагин это использует!)
    """
    prices = [LabeledPrice(label="⭐ Простая покупка", amount=10)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="💳 Простой метод (УЯЗВИМ)",
        description="Этот метод обходится плагином",
        payload="simple_payment",  # ⚠️ Простой payload
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=prices
    )
    logger.info("💳 [SIMPLE] Инвойс отправлен (уязвимый метод)")


@dp.pre_checkout_query(lambda q: q.invoice_payload == "simple_payment")
async def process_simple_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    ⚠️ КРИТИЧЕСКАЯ УЯЗВИМОСТЬ!

    Плагин подменяет ответ TL_payments_sendStarsForm на TL_payments_paymentResult.
    После ответа ok=True клиент ЗАКРЫВАЕТ форму оплаты, а плагин показывает success.

    НО! successful_payment НЕ ПРИХОДИТ в бота (плагин не может его сгенерировать).
    Поэтому УЯЗВИМОСТЬ - выдача товара ЗДЕСЬ, в pre_checkout!
    """
    logger.info("✅ [SIMPLE] Pre-checkout получен")
    logger.info(f"   User: {pre_checkout_query.from_user.id}")
    logger.info(f"   Amount: {pre_checkout_query.total_amount} {pre_checkout_query.currency}")

    await pre_checkout_query.answer(ok=True)

    # ⚠️⚠️⚠️ УЯЗВИМОСТЬ: Выдаём товар в pre-checkout! ⚠️⚠️⚠️
    # Плагин не может отправить successful_payment, поэтому
    # криворукие разработчики выдают товар ЗДЕСЬ
    user_id = pre_checkout_query.from_user.id

    await bot.send_message(
        chat_id=user_id,
        text=(
            "✅ <b>Платёж обработан (УЯЗВИМЫЙ метод)!</b>\n\n"
            "💳 Метод: <b>Простой</b>\n"
            f"💰 Сумма: {pre_checkout_query.total_amount} {pre_checkout_query.currency}\n\n"
            "⚠️ <b>ВНИМАНИЕ! Это ВОТ И ДЫРА!</b>\n"
            "Товар выдан в pre-checkout запросе.\n"
            "Плагин MK_FuckPayments обошёл оплату!\n\n"
            "❌ Реального successful_payment не будет\n"
            "❌ telegram_payment_charge_id не существует\n"
            "❌ Деньги НЕ списались\n\n"
            "🎁 Но товар всё равно выдан)))! да разраб?"
        ),
        parse_mode="HTML"
    )

    logger.warning("🎁 [SIMPLE] Товар выдан в pre-checkout (ДЫРА!)")


# ==================== ЗАЩИЩЁННЫЙ МЕТОД ====================

@dp.message(Command("secure_payment"))
async def cmd_secure_payment(message: Message):
    """
    ЗАЩИЩЁННЫЙ метод - плагин НЕ может обойти!

    Защита:
    1. HMAC-подпись в payload
    2. Таймстамп для предотвращения переиспользования
    3. НЕ выдаёт товар в pre-checkout
    4. Ожидает successful_payment с telegram_payment_charge_id
    """
    user_id = message.from_user.id
    timestamp = int(datetime.now().timestamp())
    amount = 10

    # Создаем подписанный payload
    signature = generate_signature(user_id, timestamp, amount)
    payment_id = f"secure_{user_id}_{timestamp}_{signature}"

    # Сохраняем данные платежа
    pending_payments[payment_id] = {
        "user_id": user_id,
        "amount": amount,
        "currency": "XTR",
        "created_at": datetime.now(),
        "pre_checkout_ok": False,
        "validated": False
    }

    prices = [LabeledPrice(label="🔒 Защищённая покупка", amount=amount)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="🔒 Защищённый метод",
        description="Защищён проверкой charge_id",
        payload=payment_id,  # 🛡️ Подписанный payload
        provider_token=PROVIDER_TOKEN,
        currency="XTR",
        prices=prices
    )
    logger.info(f"🔒 [SECURE] Инвойс отправлен")
    logger.info(f"   Payment ID: {payment_id[:50]}...")


@dp.pre_checkout_query(lambda q: q.invoice_payload.startswith("secure_"))
async def process_secure_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    ✅ ПРАВИЛЬНАЯ РЕАЛИЗАЦИЯ

    В pre-checkout делаем ТОЛЬКО валидацию, НЕ выдаём товар!
    Товар выдаётся только в successful_payment после проверки charge_id.
    """
    payload = pre_checkout_query.invoice_payload
    user_id = pre_checkout_query.from_user.id
    amount = pre_checkout_query.total_amount

    logger.info("🔍 [SECURE] Pre-checkout получен")
    logger.info(f"   User: {user_id}")
    logger.info(f"   Amount: {amount}")

    # ✅ ПРОВЕРКА 1: Платёж существует в базе
    if payload not in pending_payments:
        logger.warning("❌ [SECURE] Платёж не найден в pending_payments")
        await pre_checkout_query.answer(
            ok=False,
            error_message="❌ Платёж не найден или истёк срок"
        )
        return

    payment_data = pending_payments[payload]

    # ✅ ПРОВЕРКА 2: Таймаут (5 минут)
    time_diff = (datetime.now() - payment_data["created_at"]).total_seconds()
    if time_diff > 300:
        logger.warning(f"❌ [SECURE] Таймаут ({time_diff:.0f}s)")
        del pending_payments[payload]
        await pre_checkout_query.answer(
            ok=False,
            error_message="❌ Истёк срок действия счёта"
        )
        return

    # ✅ ПРОВЕРКА 3: Валюта и сумма совпадают
    if (pre_checkout_query.currency != payment_data["currency"] or
            amount != payment_data["amount"]):
        logger.warning("❌ [SECURE] Неверная валюта/сумма")
        await pre_checkout_query.answer(
            ok=False,
            error_message="❌ Неверные параметры платежа"
        )
        return

    # ✅ ПРОВЕРКА 4: HMAC подпись
    if not verify_signature(payload, user_id, amount):
        logger.warning("❌ [SECURE] НЕВЕРНАЯ ПОДПИСЬ")
        await pre_checkout_query.answer(
            ok=False,
            error_message="❌ Ошибка безопасности: неверная подпись"
        )
        return

    logger.info("✅ [SECURE] Все проверки pre-checkout пройдены")
    pending_payments[payload]["pre_checkout_ok"] = True

    # ✅ ДОВЕРЯЕМ, НО ПРОВЕРЯЕМ
    await pre_checkout_query.answer(ok=True)

    # ⏳ Отправляем уведомление о НАЧАЛЕ обработки
    await bot.send_message(
        chat_id=user_id,
        text=(
            "⏳ <b>Pre-checkout пройден!</b>\n\n"
            "🔍 Ожидаем подтверждение от Telegram...\n\n"
            "⚠️ <b>Товар будет выдан только после:</b>\n"
            "• Получения successful_payment\n"
            "• Проверки telegram_payment_charge_id\n\n"
            "🚫 Плагин не может подделать эти данные!"
            "• Следовательно это сообщение при оплате через MK_FuckPayments будет висеть вечно."
        ),
        parse_mode="HTML"
    )


# ==================== ОБРАБОТКА SUCCESSFUL_PAYMENT ====================

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """
    Обработка подтверждения оплаты

    ЭТО СООБЩЕНИЕ НЕ ПРИДЁТ при использовании плагина!
    Плагин не может сгенерировать настоящий successful_payment.
    """
    payment = message.successful_payment
    payload = payment.invoice_payload

    logger.info("=" * 70)
    logger.info("🎉 SUCCESSFUL_PAYMENT ПОЛУЧЕН")
    logger.info(f"   Payload: {payload[:50]}...")
    logger.info(f"   User: {message.from_user.id}")
    logger.info(f"   Telegram Charge ID: {payment.telegram_payment_charge_id}")
    logger.info(f"   Provider Charge ID: {payment.provider_payment_charge_id}")
    logger.info("=" * 70)

    # ==================== УЯЗВИМЫЙ МЕТОД ====================
    if payload == "simple_payment":
        logger.info("✅ [SIMPLE] Получен РЕАЛЬНЫЙ successful_payment")

        await message.answer(
            "✅ <b>РЕАЛЬНЫЙ платёж обработан!</b>\n\n"
            "💳 Метод: <b>Простой</b>\n"
            f"💰 Сумма: {payment.total_amount} {payment.currency}\n"
            f"🆔 Charge ID: <code>{payment.telegram_payment_charge_id}</code>\n\n"
            "⚠️ Это сообщение появится ТОЛЬКО при реальной оплате!\n"
            "При использовании плагина его НЕ будет.",
            parse_mode="HTML"
        )
        return

    # ==================== ЗАЩИЩЁННЫЙ МЕТОД ====================
    if not payload.startswith("secure_"):
        logger.warning(f"⚠️ Неизвестный payload: {payload}")
        return

    logger.info("🔍 [SECURE] Начинаем финальную валидацию")

    try:
        # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА 1: Платёж в базе
        if payload not in pending_payments:
            logger.error("❌ [SECURE] ФЕЙКОВЫЙ ПЛАТЁЖ! Payload не найден в базе!")
            await message.answer(
                "❌ <b>ОШИБКА БЕЗОПАСНОСТИ</b>\n\n"
                "Платёж не найден в системе.\n"
                "🚨 <b>Это попытка обхода оплаты!</b>",
                parse_mode="HTML"
            )
            return

        payment_data = pending_payments[payload]

        # ✅ ПРОВЕРКА 2: User ID совпадает
        if message.from_user.id != payment_data["user_id"]:
            logger.error(f"❌ [SECURE] User ID mismatch!")
            await message.answer(
                "❌ <b>ОШИБКА БЕЗОПАСНОСТИ</b>\n\n"
                "ID пользователя не совпадает.",
                parse_mode="HTML"
            )
            return

        # ✅ ПРОВЕРКА 3: Pre-checkout был пройден
        if not payment_data.get("pre_checkout_ok"):
            logger.error("❌ [SECURE] Нет пройденного pre-checkout!")
            await message.answer(
                "❌ <b>ОШИБКА БЕЗОПАСНОСТИ</b>\n\n"
                "Получено подтверждение без предварительной проверки.",
                parse_mode="HTML"
            )
            return

        # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА 4: telegram_payment_charge_id существует
        charge_id = payment.telegram_payment_charge_id
        if not charge_id:
            logger.error("❌ [SECURE] ОТСУТСТВУЕТ telegram_payment_charge_id!")
            await message.answer(
                "❌ <b>ОШИБКА БЕЗОПАСНОСТИ</b>\n\n"
                "Отсутствует ID транзакции Telegram.\n"
                "🚨 <b>ЭТО ЯВНАЯ ПОПЫТКА ПОДДЕЛКИ!</b>",
                parse_mode="HTML"
            )
            return

        # ✅ ПРОВЕРКА 5: Повторная проверка суммы и валюты
        if (payment.currency != payment_data["currency"] or
                payment.total_amount != payment_data["amount"]):
            logger.error("❌ [SECURE] Несоответствие суммы/валюты")
            await message.answer(
                "❌ <b>ОШИБКА БЕЗОПАСНОСТИ</b>\n\n"
                "Параметры платежа были изменены.",
                parse_mode="HTML"
            )
            return

        # ✅ ПРОВЕРКА 6: Предотвращение повторной обработки
        if payment_data.get("validated"):
            logger.error("❌ [SECURE] Попытка повторного использования!")
            await message.answer(
                "❌ <b>ОШИБКА</b>\n\n"
                "Этот платёж уже был обработан.",
                parse_mode="HTML"
            )
            return

        # ============ ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ============
        pending_payments[payload]["validated"] = True
        logger.info("✅✅✅ [SECURE] РЕАЛЬНЫЙ ПЛАТЁЖ ПОДТВЕРЖДЁН!")

        # 🎁 Выдаём товар (только после всех проверок!)
        await message.answer(
            "✅ <b>Платёж успешно обработан!</b>\n\n"
            "💳 Метод: <b>Защищённый</b>\n"
            f"💰 Сумма: {payment.total_amount} {payment.currency}\n"
            f"🆔 ID транзакции:\n<code>{charge_id}</code>\n\n"
            "🛡️ <b>Все проверки безопасности пройдены:</b>\n"
            "✓ HMAC подпись\n"
            "✓ User ID verification\n"
            "✓ Pre-checkout validation\n"
            "✓ Telegram charge ID check\n"
            "✓ Amount & currency match\n\n"
            "🚫 Плагин MK_FuckPayments НЕ МОЖЕТ обойти эту защиту!\n\n"
            "🎁 <b>Товар выдан!</b>",
            parse_mode="HTML"
        )

        logger.info("🎁 [SECURE] Товар выдан (после полной проверки)")

    finally:
        # Удаляем платёж из временного хранилища
        if payload in pending_payments:
            del pending_payments[payload]
            logger.info(f"🧹 Платёж удалён из pending_payments")


async def cleanup_expired_payments():
    """Фоновая очистка истёкших платежей"""
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        expired_ids = [
            pid for pid, data in pending_payments.items()
            if now - data["created_at"] > timedelta(minutes=15)
        ]
        for pid in expired_ids:
            del pending_payments[pid]
            logger.info(f"🧹 Удалён истёкший платёж: {pid[:30]}...")


async def main():
    logger.info("=" * 70)
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info("💳 ДЫРЯВЫЙ метод: /simple_payment")
    logger.info("🔒 ЗАЩИЩЁННЫЙ метод: /secure_payment")
    logger.info("=" * 70)

    asyncio.create_task(cleanup_expired_payments())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
