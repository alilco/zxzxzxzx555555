
import telebot
import requests
import time
import logging
from telebot import types
from telebot.apihelper import ApiTelegramException # To catch specific exceptions like user not found

# --- Configuration ---
BOT_TOKEN = "7801620011:AAHRQ7jwV7axMTXl0BRn7RDt9AA4WyHyWao"
OWNER_ID = 5985152508
DEVELOPER_USERNAME = "@zzpp_p"
DEVELOPER_INFO = f"Bot Developer: {DEVELOPER_USERNAME}"
# --- Channel Subscription Configuration ---
CHANNEL_ID = "@aiiichat" # <<<< IMPORTANT: Your target channel username (e.g., @channelname) or ID (e.g., -100123456789)
# Ensure compatibility with older Python f-string parsing by pre-calculating the stripped ID
_channel_name_for_link = CHANNEL_ID.lstrip('@')
CHANNEL_LINK = f"https://t.me/{_channel_name_for_link}" # Auto-generated link for the user to join

# AI API Configuration
AI_API_URL = "https://pdf-ai-summarizer.toolzflow.app/api/chat/public"
AI_API_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
    'content-type': 'application/json',
    'origin': 'https://pdf-ai-summarizer.toolzflow.app',
    'priority': 'u=1, i',
    'referer': 'https://pdf-ai-summarizer.toolzflow.app/',
    'sec-ch-ua': '\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '\"Windows\"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-storage-access': 'active',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
}

# --- Usage Limit Configuration ---
MAX_MESSAGES_PER_HOUR = 10
HOUR_IN_SECONDS = 3600
user_usage_data = {}

# --- User Tracking ---
unique_user_ids = set()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot Initialization ---
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# --- Helper Functions ---
def is_owner(user_id: int) -> bool:
    """Checks if the user ID belongs to the owner."""
    return user_id == OWNER_ID

def add_user_to_stats(user_id: int):
    """Adds a user ID to the set of unique users if not already present."""
    if user_id not in unique_user_ids:
        unique_user_ids.add(user_id)
        logger.info(f"Added user {user_id} to stats. Total unique users: {len(unique_user_ids)}")

def check_channel_membership(user_id: int) -> bool:
    """Checks if a user is a member of the specified channel (CHANNEL_ID).
    
    IMPORTANT: The bot MUST be an administrator in the channel for this to work.
    Returns True if the user is a member, False otherwise (or on error).
    """
    try:
        # Get the user's status in the channel
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        # Check if the status indicates membership
        if member.status in ['member', 'administrator', 'creator']:
            logger.debug(f"User {user_id} is a member of {CHANNEL_ID} (status: {member.status}).")
            return True
        else:
            # User is not a member (e.g., status is 'left' or 'kicked')
            logger.warning(f"User {user_id} is NOT a member of {CHANNEL_ID} (status: {member.status}).")
            return False
    except ApiTelegramException as e:
        # Handle specific Telegram API errors
        if "user not found" in str(e):
            # User might have blocked the bot or deleted account, or never joined
            logger.warning(f"API Error checking membership for user {user_id} in {CHANNEL_ID}: User not found. Assuming not member.")
        elif "chat not found" in str(e) or "bot is not a member" in str(e) or "not enough rights" in str(e):
            # Common errors if bot isn't admin or CHANNEL_ID is wrong
            logger.error(f"CRITICAL API Error checking membership in {CHANNEL_ID}: {e}. Bot might not be admin or channel ID is incorrect. Membership check will fail.")
        else:
            # Log other unexpected API errors
            logger.exception(f"Unexpected API error checking membership for user {user_id} in {CHANNEL_ID}: {e}")
        return False # Assume not member on API error
    except Exception as e:
        # Catch any other unexpected errors during the check
        logger.exception(f"Generic error checking membership for user {user_id} in {CHANNEL_ID}: {e}")
        return False # Assume not member on generic error

def call_ai_api(user_message: str) -> str:
    """Calls the external AI API and returns the response text."""
    json_data = {
        'chatSettings': {
            'model': 'gpt-4.5-preview-2025-02-27',
            'temperature': 0.5,
            'includeProfileContext': True,
            'includeWorkspaceInstructions': True,
            'embeddingsProvider': 'openai',
        },
        'messages': [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': user_message,
                    },
                ],
            },
        ],
        'customModelId': '',
    }
    try:
        response = requests.post(AI_API_URL, headers=AI_API_HEADERS, json=json_data, timeout=45)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        logger.error("AI API request timed out.")
        return "عذراً، استغرق الرد وقتاً طويلاً جداً."
    except requests.exceptions.RequestException as e:
        logger.error(f"AI API request failed: {e}")
        return "عذراً، حدث خطأ أثناء الاتصال بخدمة الذكاء الاصطناعي."
    except Exception as e:
        logger.error(f"Error processing AI response: {e}")
        return "عذراً، حدث خطأ غير متوقع في معالجة رد الذكاء الاصطناعي."

# --- Pre-Handler Check Function (Decorator Style) ---
# This function checks membership before executing the actual handler
def membership_required(func):
    """Decorator to check channel membership before allowing command/message processing."""
    def wrapper(message: types.Message):
        user_id = message.from_user.id
        # Always allow the owner
        if is_owner(user_id):
            func(message)
            return
        
        # Check channel membership for others
        if check_channel_membership(user_id):
            func(message) # User is a member, proceed with the original function
        else:
            # User is not a member, send join message and stop
            bot.reply_to(message, f"⚠️ عذراً، يجب عليك الاشتراك في القناة أولاً لاستخدام البوت: {CHANNEL_LINK}\n\nبعد الاشتراك، حاول إرسال رسالتك أو الأمر مرة أخرى.")
            logger.info(f"Blocked access for non-member user {user_id}.")
    return wrapper

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
@membership_required # Apply membership check
def send_welcome(message: types.Message):
    """Handles the /start command after membership check."""
    user = message.from_user
    add_user_to_stats(user.id)
    bot.reply_to(message, f"أهلاً بك <a href='tg://user?id={user.id}'>{user.first_name}</a>! أنا بوت دردشة مدعوم بالذكاء الاصطناعي. يمكنك التحدث معي مباشرة.")
    commands = [
        types.BotCommand("start", "بدء المحادثة"),
        types.BotCommand("dev", "عرض معلومات المطور"),
    ]
    if is_owner(user.id):
        commands.append(types.BotCommand("ownerhelp", "عرض أوامر المالك"))
        commands.append(types.BotCommand("stats", "عرض إحصائيات المستخدمين"))
    try:
        bot.set_my_commands(commands)
    except Exception as e:
        logger.error(f"Failed to set commands: {e}")

@bot.message_handler(commands=['dev'])
@membership_required # Apply membership check
def send_dev_info(message: types.Message):
    """Handles the /dev command after membership check."""
    add_user_to_stats(message.from_user.id)
    bot.reply_to(message, DEVELOPER_INFO)

# Owner commands don't need the membership check decorator, as they already check is_owner()
@bot.message_handler(commands=['ownerhelp'])
def send_owner_help(message: types.Message):
    user_id = message.from_user.id
    add_user_to_stats(user_id)
    if not is_owner(user_id):
        bot.reply_to(message, "عذراً، هذا الأمر مخصص للمالك فقط.")
        return
    help_text = "<b>أوامر المالك:</b>\n"
    help_text += "/ownerhelp - عرض هذه الرسالة\n"
    help_text += "/stats - عرض عدد المستخدمين الفريدين\n"
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['stats'])
def send_stats(message: types.Message):
    user_id = message.from_user.id
    add_user_to_stats(user_id)
    if not is_owner(user_id):
        bot.reply_to(message, "عذراً، هذا الأمر مخصص للمالك فقط.")
        return
    bot.reply_to(message, f"📊 إجمالي عدد المستخدمين الفريدين الذين تفاعلوا مع البوت: {len(unique_user_ids)}")

# --- Message Handlers ---
@bot.message_handler(func=lambda message: message.content_type == 'text' and not message.text.startswith('/'))
@membership_required # Apply membership check to regular messages
def handle_text_message(message: types.Message):
    """Handles regular text messages after membership check, applies usage limits, and interacts with AI."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_time = time.time()

    add_user_to_stats(user_id) # Track interaction (already passed membership check)

    # --- Usage Limit Check (Skip for Owner) ---
    # This check only runs if the user is not the owner (checked by decorator)
    # No need for another is_owner() check here.
    usage = user_usage_data.get(user_id)
    reset_usage = False
    if usage:
        time_since_start = current_time - usage['start_time']
        if time_since_start >= HOUR_IN_SECONDS:
            reset_usage = True
            logger.info(f"User {user_id} usage window expired ({time_since_start:.0f}s >= {HOUR_IN_SECONDS}s). Resetting.")
        else:
            if usage['count'] >= MAX_MESSAGES_PER_HOUR:
                remaining_wait = int(HOUR_IN_SECONDS - time_since_start)
                minutes, seconds = divmod(remaining_wait, 60)
                bot.reply_to(message, f"لقد استهلكت حدك البالغ {MAX_MESSAGES_PER_HOUR} رسائل لهذا الساعة. يرجى الانتظار لمدة {minutes} دقيقة و {seconds} ثانية للمحاولة مرة أخرى.")
                logger.warning(f"User {user_id} reached message limit ({usage['count']}/{MAX_MESSAGES_PER_HOUR}). Wait {remaining_wait} seconds.")
                return
            else:
                usage['count'] += 1
                user_usage_data[user_id] = usage
                logger.info(f"User {user_id} used message {usage['count']}/{MAX_MESSAGES_PER_HOUR} in current window (started {time_since_start:.0f}s ago).")
    else:
        reset_usage = True
    if reset_usage:
        user_usage_data[user_id] = {'count': 1, 'start_time': current_time}
        logger.info(f"User {user_id} starting new usage window (message 1/{MAX_MESSAGES_PER_HOUR}).")
    # --- End Usage Limit Check ---

    # --- Proceed with AI interaction ---
    user_message = message.text
    logger.info(f"User {user_id} in chat {chat_id} sent: {user_message[:50]}...")
    bot.send_chat_action(chat_id, 'typing')
    ai_response = call_ai_api(user_message)
    logger.info(f"AI response length: {len(ai_response)}")
    try:
        if len(ai_response) > 4096:
            for i in range(0, len(ai_response), 4096):
                bot.reply_to(message, ai_response[i:i+4096])
                time.sleep(0.5)
        else:
            bot.reply_to(message, ai_response)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        bot.reply_to(message, "حدث خطأ أثناء إرسال الرد.")

@bot.message_handler(content_types=['new_chat_members'])
def greet_new_member(message: types.Message):
    """Greets new users when they join the chat but does not add them to stats."""
    # No membership check needed here, just a greeting.
    if message.chat.type not in ['group', 'supergroup']:
        return
    for user in message.new_chat_members:
        if user.id == bot.get_me().id:
            continue
        logger.info(f"User {user.id} ({user.full_name}) joined chat {message.chat.id}")
        bot.send_message(message.chat.id, f"أهلاً بك <a href='tg://user?id={user.id}'>{user.first_name}</a> في المجموعة! 🎉")

# --- Main Execution ---
if __name__ == '__main__':
    logger.info("Starting bot v5 (f-string fix) with message limit, user stats, and channel subscription check...")
    try:
        bot.infinity_polling(logger_level=logging.INFO) # Use infinity_polling for continuous running
    except Exception as e:
        logger.critical(f"Bot polling failed critically: {e}")
    finally:
        logger.info("Bot stopped.")
