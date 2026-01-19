import os
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pyrogram import Client
from pyrogram.errors import RPCError
import mimetypes
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
SESSION_STRING = os.getenv("TG_SESSION_STRING")
PORT = int(os.getenv("PORT", 8000))

# Validate environment variables
if not all([API_ID, API_HASH, SESSION_STRING]):
    raise ValueError("Missing required environment variables: TG_API_ID, TG_API_HASH, TG_SESSION_STRING")

# Initialize FastAPI
app = FastAPI(title="Telegram Streaming Proxy")

# Initialize Pyrogram Client (UserBot mode)
client = Client(
    name="streaming_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)


@app.on_event("startup")
async def startup_event():
    """Start Pyrogram client on app startup"""
    await client.start()
    logger.info("Pyrogram client started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop Pyrogram client on app shutdown"""
    await client.stop()
    logger.info("Pyrogram client stopped")


@app.get("/")
async def root():
    """Status endpoint"""
    return {
        "status": "online",
        "service": "Telegram Streaming Proxy",
        "usage": "/dl/{channel_id}/{message_id}"
    }


async def stream_file(chat_id: int, message_id: int) -> AsyncGenerator[bytes, None]:
    """
    Stream file chunks from Telegram with optimized chunk size for large files
    
    Args:
        chat_id: Telegram chat/channel ID
        message_id: Message ID containing the file
        
    Yields:
        bytes: File chunks
    """
    try:
        # Fetch the message
        message = await client.get_messages(chat_id, message_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check if message contains media
        if not message.media:
            raise HTTPException(status_code=400, detail="Message does not contain any media")
        
        # Stream the file in chunks (1MB chunks for better performance on large files)
        chunk_size = 1024 * 1024  # 1MB chunks
        async for chunk in client.stream_media(message, limit=chunk_size):
            yield chunk
            
    except RPCError as e:
        logger.error(f"Telegram API error: {e}")
        raise HTTPException(status_code=403, detail=f"Telegram API error: {str(e)}")
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")


@app.get("/dl/{chat_id}/{message_id}")
async def download_file(chat_id: int, message_id: int):
    """
    Stream a file from Telegram as HTTP download
    
    Args:
        chat_id: Telegram chat/channel ID (can be username or numeric ID)
        message_id: Message ID containing the file
        
    Returns:
        StreamingResponse: File stream with appropriate headers
    """
    try:
        # Fetch message metadata first
        message = await client.get_messages(chat_id, message_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        if not message.media:
            raise HTTPException(status_code=400, detail="Message does not contain any media")
        
        # Extract file metadata
        file_name = "file"
        file_size = 0
        mime_type = "application/octet-stream"
        
        if message.document:
            file_name = message.document.file_name or f"document_{message_id}"
            file_size = message.document.file_size
            mime_type = message.document.mime_type or mime_type
        elif message.video:
            file_name = message.video.file_name or f"video_{message_id}.mp4"
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
        elif message.audio:
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.photo:
            file_name = f"photo_{message_id}.jpg"
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
        elif message.voice:
            file_name = f"voice_{message_id}.ogg"
            file_size = message.voice.file_size
            mime_type = message.voice.mime_type or "audio/ogg"
        elif message.video_note:
            file_name = f"video_note_{message_id}.mp4"
            file_size = message.video_note.file_size
            mime_type = "video/mp4"
        elif message.animation:
            file_name = message.animation.file_name or f"animation_{message_id}.mp4"
            file_size = message.animation.file_size
            mime_type = message.animation.mime_type or "video/mp4"
        
        # Guess mime type from filename if not available
        if mime_type == "application/octet-stream":
            guessed_type = mimetypes.guess_type(file_name)[0]
            if guessed_type:
                mime_type = guessed_type
        
        logger.info(f"Streaming file: {file_name} ({file_size} bytes) from chat {chat_id}, message {message_id}")
        
        # Prepare headers
        headers = {
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Type": mime_type,
            "Accept-Ranges": "none"
        }
        
        # Add Content-Length if available
        if file_size > 0:
            headers["Content-Length"] = str(file_size)
        
        # Return streaming response
        return StreamingResponse(
            stream_file(chat_id, message_id),
            headers=headers,
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except RPCError as e:
        logger.error(f"Telegram API error: {e}")
        raise HTTPException(status_code=403, detail=f"Access denied or invalid chat/message: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Render provides PORT env variable, default to 8000 for local dev
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
