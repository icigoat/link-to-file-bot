import os
import logging
from typing import AsyncGenerator, List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.types import Message
import mimetypes
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
SESSION_STRING = os.getenv("TG_SESSION_STRING")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Your channel ID or @username
PORT = int(os.getenv("PORT", 8000))

# Validate environment variables
if not all([API_ID, API_HASH, SESSION_STRING]):
    raise ValueError("Missing required environment variables: TG_API_ID, TG_API_HASH, TG_SESSION_STRING")

# Initialize FastAPI
app = FastAPI(title="Telegram File Browser")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

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
    
    # Cache all dialogs to resolve peers
    try:
        logger.info("Caching dialogs...")
        count = 0
        async for dialog in client.get_dialogs(limit=100):
            count += 1
        logger.info(f"Cached {count} dialogs")
    except Exception as e:
        logger.warning(f"Could not cache dialogs: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop Pyrogram client on app shutdown"""
    await client.stop()
    logger.info("Pyrogram client stopped")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main page - shows file list from channel"""
    try:
        # Get channel ID from env or use default
        channel_id = CHANNEL_ID if CHANNEL_ID else None
        
        if not channel_id:
            return templates.TemplateResponse("setup.html", {"request": request})
        
        # Convert channel_id to int if it's a string number
        try:
            channel_id = int(channel_id)
        except (ValueError, TypeError):
            pass  # Keep as string if it's a username like @channel
        
        # Fetch messages with media from the channel directly
        # No need to resolve peer first, just iterate
        files = []
        try:
            async for message in client.get_chat_history(channel_id, limit=100):
                if message.media:
                    file_info = extract_file_info(message, channel_id)
                    if file_info:
                        files.append(file_info)
            
            logger.info(f"Found {len(files)} files in channel {channel_id}")
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"Cannot access channel/group. Make sure you're a member and have sent at least one message there. Error: {str(e)}"
            })
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "files": files,
            "channel_id": channel_id,
            "total_files": len(files)
        })
        
    except Exception as e:
        logger.error(f"Error loading files: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })


@app.get("/recent", response_class=HTMLResponse)
async def recent(request: Request):
    """Recent downloads page"""
    return templates.TemplateResponse("recent.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page"""
    channel_id = CHANNEL_ID if CHANNEL_ID else None
    total_files = 0
    
    if channel_id:
        try:
            channel_id = int(channel_id)
        except (ValueError, TypeError):
            pass
        
        try:
            async for message in client.get_chat_history(channel_id, limit=100):
                if message.media:
                    total_files += 1
        except:
            pass
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "total_files": total_files
    })


@app.get("/stream/{chat_id}/{message_id}")
async def stream_media(chat_id: int, message_id: int, request: Request):
    """Stream media with range request support for better performance"""
    try:
        # Convert chat_id to int if needed
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass
        
        # Fetch the message
        message = await client.get_messages(chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Message or media not found")
        
        # Get file info
        file_name = "file"
        file_size = 0
        mime_type = "application/octet-stream"
        
        if message.video:
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
        elif message.document:
            file_name = message.document.file_name or f"document_{message_id}"
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
        
        # Handle range requests for better streaming
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range header
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
            
            # Stream specific range
            async def stream_range():
                offset = start
                chunk_size = 1024 * 1024  # 1MB chunks
                async for chunk in client.stream_media(message, offset=offset, limit=end - start + 1):
                    yield chunk
            
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
                "Content-Type": mime_type,
                "Cache-Control": "public, max-age=3600"
            }
            
            return StreamingResponse(
                stream_range(),
                status_code=206,
                headers=headers,
                media_type=mime_type
            )
        else:
            # Stream entire file
            headers = {
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": mime_type,
                "Cache-Control": "public, max-age=3600"
            }
            
            return StreamingResponse(
                stream_file(chat_id, message_id),
                headers=headers,
                media_type=mime_type
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming media: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thumbnail/{chat_id}/{message_id}")
async def get_thumbnail(chat_id: int, message_id: int):
    """Get thumbnail for a message"""
    try:
        # Convert chat_id to int if needed
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass
        
        # Fetch the message
        message = await client.get_messages(chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Message or media not found")
        
        # Get thumbnail based on media type
        thumb_data = None
        mime_type = "image/jpeg"
        
        if message.photo:
            # For photos, download the smallest size (thumbnail)
            thumb_data = await client.download_media(message, in_memory=True)
        elif message.video and message.video.thumbs:
            # For videos, get the thumbnail
            thumb_data = await client.download_media(message.video.thumbs[0].file_id, in_memory=True)
        elif message.document and message.document.thumbs:
            # For documents with thumbnails
            thumb_data = await client.download_media(message.document.thumbs[0].file_id, in_memory=True)
        elif message.animation and message.animation.thumbs:
            # For animations/GIFs
            thumb_data = await client.download_media(message.animation.thumbs[0].file_id, in_memory=True)
        
        if thumb_data:
            return StreamingResponse(
                iter([thumb_data.getvalue()]),
                media_type=mime_type,
                headers={"Cache-Control": "public, max-age=86400"}
            )
        else:
            raise HTTPException(status_code=404, detail="No thumbnail available")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files")
async def list_files(channel: str = None):
    """API endpoint to list files from a channel"""
    try:
        channel_id = channel if channel else CHANNEL_ID
        if not channel_id:
            raise HTTPException(status_code=400, detail="Channel ID not provided")
        
        # Convert to int if needed
        try:
            channel_id = int(channel_id)
        except (ValueError, TypeError):
            pass
        
        files = []
        async for message in client.get_chat_history(channel_id, limit=100):
            if message.media:
                file_info = extract_file_info(message, channel_id)
                if file_info:
                    files.append(file_info)
        
        return {"files": files, "total": len(files)}
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def extract_file_info(message: Message, channel_id: str) -> Dict:
    """Extract file information from a message"""
    file_info = {
        "message_id": message.id,
        "channel_id": channel_id,
        "date": message.date.strftime("%Y-%m-%d %H:%M") if message.date else "Unknown",
        "caption": message.caption or "",
        "has_thumbnail": False,
        "can_stream": False,
    }
    
    if message.document:
        file_info.update({
            "name": message.document.file_name or f"document_{message.id}",
            "size": format_size(message.document.file_size),
            "size_bytes": message.document.file_size,
            "type": message.document.mime_type or "application/octet-stream",
            "icon": get_file_icon(message.document.mime_type),
            "has_thumbnail": bool(message.document.thumbs),
            "can_stream": message.document.mime_type and (
                message.document.mime_type.startswith("video/") or 
                message.document.mime_type.startswith("audio/")
            )
        })
    elif message.video:
        file_info.update({
            "name": message.video.file_name or f"video_{message.id}.mp4",
            "size": format_size(message.video.file_size),
            "size_bytes": message.video.file_size,
            "type": "video/mp4",
            "icon": "🎥",
            "has_thumbnail": bool(message.video.thumbs),
            "can_stream": True
        })
    elif message.audio:
        file_info.update({
            "name": message.audio.file_name or f"audio_{message.id}.mp3",
            "size": format_size(message.audio.file_size),
            "size_bytes": message.audio.file_size,
            "type": "audio/mpeg",
            "icon": "🎵",
            "has_thumbnail": bool(message.audio.thumbs) if hasattr(message.audio, 'thumbs') else False,
            "can_stream": True
        })
    elif message.photo:
        file_info.update({
            "name": f"photo_{message.id}.jpg",
            "size": format_size(message.photo.file_size),
            "size_bytes": message.photo.file_size,
            "type": "image/jpeg",
            "icon": "🖼️",
            "has_thumbnail": True,
            "can_stream": True
        })
    elif message.voice:
        file_info.update({
            "name": f"voice_{message.id}.ogg",
            "size": format_size(message.voice.file_size),
            "size_bytes": message.voice.file_size,
            "type": "audio/ogg",
            "icon": "🎤",
            "has_thumbnail": False,
            "can_stream": True
        })
    elif message.animation:
        file_info.update({
            "name": message.animation.file_name or f"animation_{message.id}.mp4",
            "size": format_size(message.animation.file_size),
            "size_bytes": message.animation.file_size,
            "type": "video/mp4",
            "icon": "🎬",
            "has_thumbnail": bool(message.animation.thumbs),
            "can_stream": True
        })
    else:
        return None
    
    # Generate URLs
    file_info["download_url"] = f"/dl/{channel_id}/{message.id}"
    file_info["stream_url"] = f"/stream/{channel_id}/{message.id}"
    
    # Generate thumbnail URL if available
    if file_info["has_thumbnail"]:
        file_info["thumbnail_url"] = f"/thumbnail/{channel_id}/{message.id}"
    
    return file_info


def format_size(bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"


def get_file_icon(mime_type: str) -> str:
    """Get emoji icon based on file type"""
    if not mime_type:
        return "📄"
    
    if mime_type.startswith("video"):
        return "🎥"
    elif mime_type.startswith("audio"):
        return "🎵"
    elif mime_type.startswith("image"):
        return "🖼️"
    elif "pdf" in mime_type:
        return "📕"
    elif "zip" in mime_type or "rar" in mime_type or "7z" in mime_type:
        return "📦"
    elif "word" in mime_type or "document" in mime_type:
        return "📝"
    elif "excel" in mime_type or "sheet" in mime_type:
        return "📊"
    else:
        return "📄"


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
