"""
Helper script to get channel IDs and message IDs from your Telegram account
"""
import asyncio
from pyrogram import Client
from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_STRING = os.getenv("TG_SESSION_STRING")

async def main():
    async with Client("helper", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True) as app:
        print("\n=== YOUR CHANNELS/CHATS ===\n")
        
        # Get dialogs (chats/channels)
        async for dialog in app.get_dialogs(limit=20):
            chat = dialog.chat
            print(f"📁 {chat.title or chat.first_name or 'Unknown'}")
            print(f"   ID: {chat.id}")
            print(f"   Type: {chat.type}")
            if chat.username:
                print(f"   Username: @{chat.username}")
            print()
        
        # Ask user for a channel to explore
        print("\n" + "="*50)
        channel_input = input("\nEnter channel ID or @username to see recent messages (or press Enter to skip): ").strip()
        
        if channel_input:
            try:
                # Convert to proper format
                if channel_input.startswith("@"):
                    chat_id = channel_input
                else:
                    chat_id = int(channel_input)
                
                print(f"\n=== RECENT MESSAGES FROM {channel_input} ===\n")
                
                count = 0
                async for message in app.get_chat_history(chat_id, limit=20):
                    if message.media:
                        file_name = "Unknown"
                        if message.document:
                            file_name = message.document.file_name or "Document"
                        elif message.video:
                            file_name = message.video.file_name or "Video"
                        elif message.audio:
                            file_name = message.audio.file_name or "Audio"
                        elif message.photo:
                            file_name = "Photo"
                        
                        print(f"📎 Message ID: {message.id}")
                        print(f"   File: {file_name}")
                        print(f"   Date: {message.date}")
                        
                        # Generate download URL
                        if isinstance(chat_id, str):
                            url = f"http://localhost:8000/dl/{chat_id}/{message.id}"
                        else:
                            url = f"http://localhost:8000/dl/{chat_id}/{message.id}"
                        print(f"   URL: {url}")
                        print()
                        
                        count += 1
                        if count >= 10:
                            break
                
                if count == 0:
                    print("No media messages found in recent history.")
                    
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
