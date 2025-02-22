"""Message templates for the Telegram bot"""

MESSAGES = {
    "en": {
        "welcome": """👋 Welcome! I'm your Business Assistant Bot.

I'm here to help you create an AI assistant for your business that can answer customer questions accurately and professionally.

Please tell me about your business. Include details such as:
- Main products or services you offer
- Working hours and schedule
- Location and contact methods
- Pricing information
- Special features or unique selling points
- Any policies customers should know about

The more details you provide, the better I'll be able to assist your customers! 🎯""",
        "description_accepted": """✨ Perfect! I've recorded your business details.

You can now chat with me as if you were a customer. I'll respond based on the information you provided.

Feel free to ask any questions about your business, and I'll do my best to help! 🚀""",
        "error": "I apologize, but an error occurred. Please try again or contact support if the issue persists."
    },
    "ru": {
        "welcome": """👋 Добро пожаловать! Я ваш бизнес-ассистент.

Я помогу создать AI-ассистента для вашего бизнеса, который сможет профессионально отвечать на вопросы клиентов.

Пожалуйста, опишите ваш бизнес. Укажите:
- Основные товары/услуги
- График работы
- Контактные данные и местоположение
- Ценовую политику
- Уникальные особенности вашего бизнеса
- Важные правила и условия

Чем больше деталей вы предоставите, тем лучше я смогу помогать вашим клиентам! 🎯""",
        "description_accepted": """✨ Отлично! Я записал информацию о вашем бизнесе.

Теперь вы можете общаться со мной как клиент. Я буду отвечать на основе предоставленной вами информации.

Не стесняйтесь задавать любые вопросы о вашем бизнесе, и я сделаю все возможное, чтобы помочь! 🚀""",
        "error": "Извините, произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь в поддержку, если проблема не устранена."
    },
    "he": {
        "welcome": """👋 ברוך הבא! אני הבוט העסקי שלך.

אני כאן כדי לעזור לך ליצור עוזר AI לעסק שלך שיוכל לענות על שאלות לקוחות בצורה מדויקת ומקצועית.

אנא ספר לי על העסק שלך. כלול פרטים כמו:
- המוצרים או השירותים העיקריים שאתה מציע
- שעות עבודה ולוח זמנים
- מיקום ושיטות יצירת קשר
- מידע על תמחור
- מאפיינים מיוחדים או נקודות מכירה ייחודיות
- כל מדיניות שלקוחות צריכים לדעת עליה

ככל שתספק יותר פרטים, כך אוכל לעזור ללקוחות שלך טוב יותר! 🎯""",
        "description_accepted": """✨ מושלם! רשמתי את פרטי העסק שלך.

כעת אתה יכול לשוחח איתי כאילו היית לקוח. אני אגיב בהתבסס על המידע שסיפקת.

אל תהסס לשאול כל שאלה על העסק שלך, ואני אעשה כמיטב יכולתי לעזור! 🚀""",
        "error": "אני מתנצל, אך אירעה שגיאה. אנא נסה שוב או פנה לתמיכה אם הבעיה נמשכת."
    }
}

def get_message(message_key: str, language_code: str = "en") -> str:
    """Get a message in the specified language.
    
    Args:
        message_key: The key of the message to retrieve (e.g., 'welcome', 'description_accepted')
        language_code: The language code (e.g., 'en', 'ru', 'he'). Defaults to 'en'.
        
    Returns:
        str: The message in the specified language, falling back to English if the language
             or message key is not available.
    """
    # Map language codes to our supported languages
    language_mapping = {
        "ru": "ru",
        "he": "he",
        "iw": "he",  # Handle both modern (he) and legacy (iw) Hebrew codes
    }
    
    # Get the mapped language code or default to English
    lang = language_mapping.get(language_code.lower(), "en")
    
    # Try to get the message in the requested language, fall back to English if not found
    try:
        return MESSAGES[lang][message_key]
    except KeyError:
        return MESSAGES["en"][message_key]  # Fallback to English