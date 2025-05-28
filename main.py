import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ChatJoinRequestHandler,
)
from pymongo import MongoClient

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

# Convert ADMIN_ID safely to int
admin_id_raw = os.getenv("ADMIN_ID")
try:
    ADMIN_ID = int(admin_id_raw)
    print(f"✅ Loaded ADMIN_ID: {ADMIN_ID}")
except:
    print(f"❌ Invalid ADMIN_ID: {admin_id_raw}")
    ADMIN_ID = None

# --- MongoDB Setup ---
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["my_bot_db"]       # You can rename this database
users_col = db["users"]        # Collection to store users


# --- Helper functions for MongoDB users ---

async def is_user_in_db(user_id: int) -> bool:
    return users_col.find_one({"user_id": user_id}) is not None

async def add_user_to_db(user_id: int):
    if not await is_user_in_db(user_id):
        users_col.insert_one({"user_id": user_id})


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await add_user_to_db(user_id)

    if LOG_CHANNEL_ID:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"🆕 New user: {user_id}")

    await update.message.reply_text(
        "Welcome Bro , Just Add me to your channel / Group and i will accept the join requests For you!"
    )


# Auto-approve join requests
async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.chat_join_request.chat.id
    user_id = update.chat_join_request.from_user.id
    await context.bot.approve_chat_join_request(chat_id, user_id)

    if LOG_CHANNEL_ID:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"✅ Approved: {user_id}")


# /broadcast command (admin only)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if sender_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    success, fail = 0, 0
    sent_type = "text"

    # Get all user IDs from MongoDB
    all_users = users_col.find({}, {"user_id": 1})
    user_ids = [user["user_id"] for user in all_users]

    # Reply-to broadcast
    if update.message.reply_to_message:
        original = update.message.reply_to_message
        for user_id in user_ids:
            try:
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=original.message_id,
                )
                success += 1
            except:
                fail += 1
        sent_type = "forward"

    # Direct text broadcast
    else:
        message = " ".join(context.args)
        if not message:
            await update.message.reply_text(
                "⚠️ Usage: reply to a message with /broadcast OR use /broadcast <text>"
            )
            return
        for user_id in user_ids:
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
                success += 1
            except:
                fail += 1

    result_msg = f"📢 Broadcast ({sent_type}) done:\n✅ Sent: {success}\n❌ Failed: {fail}"
    await update.message.reply_text(result_msg)

    if LOG_CHANNEL_ID:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID, text=f"📢 Broadcast ({sent_type}) by {sender_id}\n{result_msg}"
        )


# /stats command (admin only)
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    print(f"/stats used by: {sender_id}, ADMIN_ID is {ADMIN_ID}")  # For debugging

    if sender_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    total_users = users_col.count_documents({})
    await update.message.reply_text(f"📊 Total users: {total_users}")

    if LOG_CHANNEL_ID:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=f"📈 Stats requested by {sender_id}: {total_users} users.",
        )


# /users command (admin only)
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if sender_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    user_cursor = users_col.find({}, {"user_id": 1})
    user_ids = [str(user["user_id"]) for user in user_cursor]

    if not user_ids:
        await update.message.reply_text("No users found.")
        return

    user_list = "\n".join(user_ids)
    response = f"👥 Total users: {len(user_ids)}\n\n{user_list}"

    if len(response) > 4000:
        with open("user_ids.txt", "w") as f:
            f.write(user_list)
        await update.message.reply_document(document=open("user_ids.txt", "rb"), filename="user_ids.txt")
    else:
        await update.message.reply_text(response)

    if LOG_CHANNEL_ID:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"📤 /users command used by {sender_id}")


# Run the bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ChatJoinRequestHandler(join_request))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users_list))

    # Log bot start
    async def on_startup(app):
        print("🚀 Bot started successfully!")
        if LOG_CHANNEL_ID:
            try:
                await app.bot.send_message(chat_id=LOG_CHANNEL_ID, text="✅ Bot started successfully!")
            except Exception as e:
                print(f"❌ Could not send log start message: {e}")

    app.post_init = on_startup
    app.run_polling()
