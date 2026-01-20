#!/usr/bin/env python3
"""
Fix Telegram Session Issues
This script helps resolve AUTH_KEY_DUPLICATED errors by generating a new session.
"""

import os
from pyrogram import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")

if not API_ID or not API_HASH:
    print("❌ Missing TG_API_ID or TG_API_HASH in .env file")
    exit(1)

print("🔧 Telegram Session Fix Tool")
print("=" * 40)
print()

print("This will help you fix the AUTH_KEY_DUPLICATED error.")
print("You have two options:")
print()
print("1. 🆕 Generate a completely new session")
print("2. 🔄 Try to reuse existing session with different settings")
print()

choice = input("Choose option (1 or 2): ").strip()

if choice == "1":
    print("\n🆕 Generating new session...")
    print("⚠️  You'll need to log in again with your phone number")
    print()
    
    # Create new session
    with Client("new_session", api_id=int(API_ID), api_hash=API_HASH) as app:
        session_string = app.export_session_string()
        
    print("✅ New session generated!")
    print()
    print("📝 Update your .env file with this new session:")
    print(f"TG_SESSION_STRING={session_string}")
    print()
    print("🗑️  You can delete the old 'streaming_bot.session' file if it exists")

elif choice == "2":
    print("\n🔄 Testing existing session with better settings...")
    
    current_session = os.getenv("TG_SESSION_STRING")
    if not current_session:
        print("❌ No TG_SESSION_STRING found in .env file")
        exit(1)
    
    try:
        # Test with no_updates and takeout disabled
        client = Client(
            "test_session",
            api_id=int(API_ID),
            api_hash=API_HASH,
            session_string=current_session,
            in_memory=True,
            no_updates=True,
            takeout=False
        )
        
        with client:
            me = client.get_me()
            print(f"✅ Session works! Logged in as: {me.first_name}")
            print("✅ The updated main.py should now work with your existing session")
            
    except Exception as e:
        print(f"❌ Session test failed: {e}")
        print("💡 Try option 1 to generate a new session")

else:
    print("❌ Invalid choice. Please run the script again and choose 1 or 2.")

print()
print("🚀 After updating your session, restart your app:")
print("   python main.py")