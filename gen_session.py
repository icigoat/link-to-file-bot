from pyrogram import Client
import asyncio

# PASTE YOUR CREDENTIALS HERE
api_id = 39693321  # Replace with yours
api_hash = "7be8afb3ebde3a05a58323af198a64bf"

async def main():
    async with Client("my_session", api_id, api_hash, in_memory=True) as app:
        print("\n👇 COPY THIS STRING 👇\n")
        print(await app.export_session_string())
        print("\n👆 COPY THIS STRING 👆\n")

asyncio.run(main())