import sqlite3
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
import os
import random

# Environment variables for better security
ADMIN_ID = int(os.getenv("ADMIN_ID", "7848732022"))  # Replace with your admin's Telegram user ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "7105963496:AAGKKFdjMEC1ZlrhcirxnfFau9NzoxNmu40")  # Replace with your bot token
BTC_ADDRESS = "1P8uUSDniB4Dc9YfPzX3wHp5BZwg6cJMiU"
USDT_ADDRESS = "TPcbm4bMSm4nJDu65Skg4QF7xNFNWfUzqts"

# SQLite database setup
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        tokens INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Define stages in the conversation
ASK_USERNAME, VALIDATE_PAYMENT = range(2)

# Snapchat username validation class
class SnapUsernameValidator:
    def __init__(self, username):
        self.username = username
        self.url = f"https://www.snapchat.com/add/{self.username}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }

    def validate_username(self):
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            if response.status_code == 200 and 'Profile Not Found' not in response.text:
                return True, f"Username '{self.username}' exists."
            return False, f"Username '{self.username}' does not exist."
        except requests.exceptions.RequestException as e:
            return False, f"An error occurred: {e}"

# Helper functions for SQLite operations
def get_user_tokens(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tokens FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_tokens(user_id, tokens):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, tokens) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET tokens = ? WHERE user_id = ?", (tokens, user_id))
    conn.commit()
    conn.close()

# Generate keyboards
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Validate Username", callback_data="validate_username")],
        [InlineKeyboardButton("Make Payment", callback_data="make_payment")],
        [InlineKeyboardButton("Check Token Balance", callback_data="check_balance")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_validate_username_keyboard():
    keyboard = [
        [InlineKeyboardButton("Validate Another Username", callback_data="validate_username")],
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_continue_keyboard():
    keyboard = [
        [InlineKeyboardButton("Continue", callback_data="perform_security_scan")],
        [InlineKeyboardButton("Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    tokens = get_user_tokens(user_id)
    
    await update.message.reply_text(
        f"Welcome! You have {tokens} tokens." if tokens > 0 else 
        f"Welcome! You have no tokens. Please make a payment to purchase tokens.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

# Handle payment validation
async def receive_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    if not update.message.photo:
        await update.message.reply_text("Please upload a valid image.")
        return

    photo = update.message.photo[-1].file_id
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=f"Payment screenshot from User ID: {user_id}")
        await update.message.reply_text("Your payment screenshot has been sent for validation. Please wait.")
    except Exception as e:
        print(f"Error while sending photo: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

    return ConversationHandler.END

# Admin validates payment
async def validate_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Access denied. Only the admin can use this command.")
        return

    try:
        _, user_id, tokens = update.message.text.split()
        user_id = int(user_id)
        tokens = int(tokens)
        update_user_tokens(user_id, tokens)
        await context.bot.send_message(chat_id=user_id, text=f"Your payment has been validated. {tokens} tokens have been added to your account.", reply_markup=get_main_menu_keyboard())
        await update.message.reply_text(f"Added {tokens} tokens to User ID: {user_id}.")
    except Exception as e:
        print(f"Error during validation: {e}")
        await update.message.reply_text("Invalid format. Use /validate <user_id> <tokens>.")

# Admin declines payment
async def decline_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Access denied. Only the admin can use this command.")
        return

    try:
        _, user_id = update.message.text.split()
        user_id = int(user_id)
        await context.bot.send_message(chat_id=user_id, text="Your payment has been declined. Please contact support.")
        await update.message.reply_text(f"Notification sent to User ID: {user_id}.")
    except Exception as e:
        print(f"Error during decline: {e}")
        await update.message.reply_text("Invalid format. Use /decline <user_id>.")

# Callback for menu actions
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat_id

    if query.data == "validate_username":
        tokens = get_user_tokens(user_id)
        if tokens <= 0:
            await query.answer()
            await query.message.reply_text(
                f"You have no tokens. Please make a payment to purchase more tokens:\nBTC: {BTC_ADDRESS}\nUSDT: {USDT_ADDRESS}\nThen send a payment screenshot for validation.",
                reply_markup=get_main_menu_keyboard()
            )
            return

        await query.answer()
        await query.message.reply_text("Please enter the Snapchat username to validate:")
        context.user_data['waiting_for_username'] = True

    elif query.data == "check_balance":
        tokens = get_user_tokens(user_id)
        await query.answer()
        await query.message.reply_text(f"You currently have {tokens} tokens.", reply_markup=get_main_menu_keyboard())

    elif query.data == "make_payment":
        await query.answer()
        await query.message.reply_text(
            f"Please make a payment to the following addresses:\nBTC: {BTC_ADDRESS}\nUSDT: {USDT_ADDRESS}\nThen send a payment screenshot for validation."
        )
        context.user_data['waiting_for_payment'] = True

    elif query.data == "main_menu":
        await query.answer()
        await query.message.reply_text("Returning to main menu.", reply_markup=get_main_menu_keyboard())

    elif query.data == "perform_security_scan":
        await query.answer()
        await query.message.reply_text("Please wait while we work on this...")
        await asyncio.sleep(random.randint(7, 10))
        await query.message.reply_text(
            "Snapchat Security Features:\n- Two-Factor Authentication\n- Login Notifications\n- Secure Sharing\n- Privacy Controls\n- Device Management.",
            reply_markup=get_main_menu_keyboard()
        )

# Handle payment after Make Payment button
async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_payment', False):
        return

    user_id = update.message.chat_id
    if not update.message.photo:
        await update.message.reply_text("Please upload a valid payment screenshot.")
        return

    photo = update.message.photo[-1].file_id
    try:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=f"Payment screenshot from User ID: {user_id}")
        await update.message.reply_text("Your payment screenshot has been sent for validation. Please wait.", reply_markup=get_main_menu_keyboard())
    except Exception as e:
        print(f"Error while sending photo: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

    context.user_data['waiting_for_payment'] = False

# Handle Snapchat username validation
async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_username', False):
        return

    user_id = update.message.chat_id
    tokens = get_user_tokens(user_id)
    username = update.message.text

    validator = SnapUsernameValidator(username)
    valid, message = validator.validate_username()
    if valid:
        update_user_tokens(user_id, tokens - 1)
        remaining_tokens = get_user_tokens(user_id)
        await update.message.reply_text(
            f"{message}\n1 token has been deducted. Remaining tokens: {remaining_tokens}.",
            reply_markup=get_continue_keyboard()
        )
    else:
        await update.message.reply_text(message, reply_markup=get_validate_username_keyboard())

    context.user_data['waiting_for_username'] = False

# Main function
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            VALIDATE_PAYMENT: [MessageHandler(filters.PHOTO, receive_payment)],
        },
        fallbacks=[MessageHandler(filters.ALL, lambda u, c: u.message.reply_text("Invalid command."))],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("validate", validate_payment))
    application.add_handler(CommandHandler("decline", decline_payment))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
    application.add_handler(MessageHandler(filters.PHOTO, handle_payment))

    application.run_polling()

if __name__ == "__main__":
    main()
