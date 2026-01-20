import os
import logging
import re
from typing import AsyncGenerator, List, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response
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


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for HTTP headers by removing problematic Unicode characters"""
    if not filename:
        return "file"
    
    # Remove zero-width characters and other problematic Unicode
    sanitized = re.sub(r'[\u200b-\u200f\u2028-\u202f\u205f-\u206f\ufeff]', '', filename)
    
    # Replace remaining non-ASCII characters with underscores
    sanitized = re.sub(r'[^\x00-\x7F]', '_', sanitized)
    
    # Remove any remaining problematic characters for HTTP headers
    sanitized = re.sub(r'["\r\n\t]', '_', sanitized)
    
    return sanitized if sanitized else "file"

# Environment variables
API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
SESSION_STRING = os.getenv("TG_SESSION_STRING")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Your channel ID or @username
PORT = int(os.getenv("PORT", 8000))

# External TG File Streamer URL (deploy to free host for better performance)
STREAMER_URL = os.getenv("STREAMER_URL")  # e.g., "https://your-app.onrender.com"

# Validate environment variables
if not all([API_ID, API_HASH, SESSION_STRING]):
    raise ValueError("Missing required environment variables: TG_API_ID, TG_API_HASH, TG_SESSION_STRING")

# Initialize Pyrogram Client (UserBot mode) with better session handling
client = Client(
    name="streaming_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
    no_updates=True,  # Disable updates to prevent conflicts
    takeout=False     # Disable takeout mode
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events"""
    # Startup
    try:
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
    except Exception as e:
        logger.error(f"Failed to start Pyrogram client: {e}")
        # Don't raise here, let the app start anyway
    
    yield
    
    # Shutdown
    try:
        await client.stop()
        logger.info("Pyrogram client stopped")
    except Exception as e:
        logger.warning(f"Error stopping client: {e}")

# Initialize FastAPI with lifespan
app = FastAPI(title="Telegram File Browser", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")


@app.get("/cache-test", response_class=HTMLResponse)
async def cache_test(request: Request):
    """Cache test page"""
    return templates.TemplateResponse("cache_test.html", {"request": request})


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
        
        # Add timestamp for cache busting
        import time
        timestamp = str(int(time.time()))
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "files": files,
            "channel_id": channel_id,
            "total_files": len(files),
            "timestamp": timestamp
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


@app.get("/test-stream/{chat_id}/{message_id}")
async def test_stream(chat_id: str, message_id: int):
    """Test endpoint to check if streaming setup works"""
    try:
        logger.info(f"Testing stream: chat_id={chat_id}, message_id={message_id}")
        
        # Convert chat_id
        if isinstance(chat_id, str) and chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            try:
                actual_chat_id = int(chat_id)
            except (ValueError, TypeError):
                actual_chat_id = chat_id
        
        # Test message fetch
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message:
            return {"error": "Message not found", "chat_id": actual_chat_id, "message_id": message_id}
        
        if not message.media:
            return {"error": "No media in message", "chat_id": actual_chat_id, "message_id": message_id}
        
        # Get media info
        media_info = {}
        if message.video:
            media_info = {
                "type": "video",
                "file_name": message.video.file_name,
                "file_size": message.video.file_size,
                "mime_type": message.video.mime_type
            }
        elif message.audio:
            media_info = {
                "type": "audio", 
                "file_name": message.audio.file_name,
                "file_size": message.audio.file_size,
                "mime_type": message.audio.mime_type
            }
        elif message.document:
            media_info = {
                "type": "document",
                "file_name": message.document.file_name,
                "file_size": message.document.file_size,
                "mime_type": message.document.mime_type
            }
        elif message.photo:
            media_info = {
                "type": "photo",
                "file_size": message.photo.file_size
            }
        
        return {
            "success": True,
            "chat_id": actual_chat_id,
            "message_id": message_id,
            "media_info": media_info,
            "stream_url": f"/stream/{chat_id}/{message_id}"
        }
        
    except Exception as e:
        logger.error(f"Test stream error: {e}")
        return {"error": str(e), "chat_id": chat_id, "message_id": message_id}


@app.options("/stream/{chat_id}/{message_id}")
async def stream_options(chat_id: str, message_id: int):
    """Handle OPTIONS requests for CORS"""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.head("/stream/{chat_id}/{message_id}")
async def stream_head(chat_id: str, message_id: int):
    """Handle HEAD requests for streaming"""
    try:
        # Convert chat_id
        if isinstance(chat_id, str) and chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            try:
                actual_chat_id = int(chat_id)
            except (ValueError, TypeError):
                actual_chat_id = chat_id
        
        # Get message info
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get file info
        file_size = 0
        mime_type = "application/octet-stream"
        
        if message.video:
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
        elif message.audio:
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.photo:
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
        elif message.document:
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
        
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size) if file_size > 0 else "0",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Cache-Control": "public, max-age=3600"
        }
        
        return Response(headers=headers)
        
    except Exception as e:
        logger.error(f"HEAD request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/simple-stream/{chat_id}/{message_id}")
async def simple_stream(chat_id: str, message_id: int):
    """Simple streaming endpoint with minimal processing"""
    try:
        logger.info(f"Simple stream: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="No media found")
        
        # Simple streaming
        async def stream_generator():
            async for chunk in client.stream_media(message):
                yield chunk
        
        # Basic headers
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache"
        }
        
        return StreamingResponse(stream_generator(), headers=headers)
        
    except Exception as e:
        logger.error(f"Simple stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/play/{chat_id}/{message_id}")
async def play_media(chat_id: str, message_id: int):
    """Direct file serving for media playback"""
    try:
        logger.info(f"Play request: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Download file to memory
        import io
        file_data = io.BytesIO()
        
        logger.info("Downloading file to memory...")
        await client.download_media(message, file=file_data)
        file_data.seek(0)
        
        # Get file info
        file_name = "file"
        mime_type = "application/octet-stream"
        
        if message.video:
            file_name = message.video.file_name or f"video_{message_id}.mp4"
            mime_type = message.video.mime_type or "video/mp4"
        elif message.audio:
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
            mime_type = message.audio.mime_type or "audio/mpeg"
        elif message.photo:
            file_name = f"photo_{message_id}.jpg"
            mime_type = "image/jpeg"
        elif message.document:
            file_name = message.document.file_name or f"document_{message_id}"
            mime_type = message.document.mime_type or "application/octet-stream"
        
        logger.info(f"Serving file: {file_name}, type: {mime_type}")
        
        # Return file data
        return StreamingResponse(
            io.BytesIO(file_data.getvalue()),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except Exception as e:
        logger.error(f"Play error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.head("/proxy/{chat_id}/{message_id}")
async def proxy_head(chat_id: str, message_id: int):
    """Handle HEAD requests for proxy endpoint"""
    try:
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get file info
        file_size = 0
        mime_type = "application/octet-stream"
        file_name = "file"
        
        if message.video:
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
        elif message.audio:
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
        elif message.photo:
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
            file_name = f"photo_{message_id}.jpg"
        elif message.document:
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
        
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size) if file_size > 0 else "0",
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Cache-Control": "public, max-age=3600"
        }
        
        return Response(headers=headers)
        
    except Exception as e:
        logger.error(f"Proxy HEAD request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test-proxy/{chat_id}/{message_id}")
async def test_proxy(chat_id: str, message_id: int):
    """Simple test endpoint to debug proxy issues"""
    try:
        logger.info(f"Test proxy: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message info only
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message:
            return {"error": "Message not found", "chat_id": actual_chat_id, "message_id": message_id}
        
        if not message.media:
            return {"error": "No media in message", "chat_id": actual_chat_id, "message_id": message_id}
        
        # Get basic info
        media_info = {"type": "unknown", "file_size": 0, "mime_type": "unknown"}
        
        if message.video:
            media_info = {
                "type": "video",
                "file_name": message.video.file_name,
                "file_size": message.video.file_size,
                "mime_type": message.video.mime_type
            }
        elif message.document:
            media_info = {
                "type": "document",
                "file_name": message.document.file_name,
                "file_size": message.document.file_size,
                "mime_type": message.document.mime_type
            }
        
        return {
            "success": True,
            "chat_id": actual_chat_id,
            "message_id": message_id,
            "media_info": media_info
        }
        
    except Exception as e:
        logger.error(f"Test proxy error: {e}")
        return {"error": str(e), "chat_id": chat_id, "message_id": message_id}


@app.get("/direct-stream/{chat_id}/{message_id}")
async def direct_stream_media(chat_id: str, message_id: int):
    """Direct streaming using Pyrogram's built-in download with streaming"""
    try:
        logger.info(f"Direct stream: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get basic file info
        mime_type = "application/octet-stream"
        file_name = "file"
        
        if message.video:
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
        elif message.document:
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
        elif message.audio:
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
        
        # Use a different streaming approach with smaller chunks
        async def direct_stream():
            try:
                # Use smaller chunk size for more reliable streaming
                chunk_size = 64 * 1024  # 64KB chunks
                offset = 0
                chunk_count = 0
                
                while True:
                    try:
                        # Download chunk by chunk
                        chunk_data = await client.download_media(
                            message, 
                            file_name=None,  # Don't save to file
                            in_memory=True,
                            progress=None,
                            progress_args=(),
                            offset=offset,
                            limit=chunk_size
                        )
                        
                        if not chunk_data or len(chunk_data) == 0:
                            break
                            
                        chunk_count += 1
                        offset += len(chunk_data)
                        
                        if chunk_count % 100 == 0:
                            logger.info(f"Direct stream: {chunk_count} chunks, {offset // (1024*1024)}MB")
                        
                        yield chunk_data
                        
                        # If we got less than requested, we're at the end
                        if len(chunk_data) < chunk_size:
                            break
                            
                    except Exception as chunk_error:
                        logger.error(f"Chunk download error: {chunk_error}")
                        break
                        
                logger.info(f"Direct stream completed: {chunk_count} chunks, {offset // (1024*1024)}MB")
                
            except Exception as e:
                logger.error(f"Direct stream error: {e}")
        
        return StreamingResponse(
            direct_stream(),
            media_type=mime_type,
            headers={
                "Content-Type": mime_type,
                "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except Exception as e:
        logger.error(f"Direct stream setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.head("/raw-stream/{chat_id}/{message_id}")
async def raw_stream_head(chat_id: str, message_id: int):
    """Handle HEAD requests for raw-stream endpoint - NO RANGE SUPPORT"""
    try:
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get file info
        file_size = 0
        mime_type = "application/octet-stream"
        file_name = "file"
        
        if message.video:
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
        elif message.audio:
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
        elif message.photo:
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
            file_name = f"photo_{message_id}.jpg"
        elif message.document:
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
        
        headers = {
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Cache-Control": "public, max-age=3600",
            # IMPORTANT: Do NOT set Accept-Ranges to prevent browser range requests
            "Accept-Ranges": "none"  # Explicitly disable range requests
        }
        
        # Do NOT add Content-Length to avoid mismatch errors
        
        return Response(headers=headers)
        
    except Exception as e:
        logger.error(f"Raw stream HEAD request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/raw-stream/{chat_id}/{message_id}")
async def raw_stream_media(chat_id: str, message_id: int, request: Request):
    """Optimized raw streaming - NO RANGE REQUESTS to avoid Telegram API issues"""
    try:
        logger.info(f"Raw stream: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get basic file info
        mime_type = "application/octet-stream"
        file_name = "file"
        file_size = 0
        
        if message.video:
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
            file_size = message.video.file_size
        elif message.document:
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
            file_size = message.document.file_size
        elif message.audio:
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
            file_size = message.audio.file_size
        
        # DISABLE range requests - they cause OFFSET_INVALID errors with Telegram API
        # Always stream the full file to avoid Telegram API offset issues
        logger.info(f"Streaming full file: {file_name} ({file_size} bytes)")
        
        # Optimized full file streaming with larger chunks
        async def raw_stream():
            try:
                chunk_count = 0
                total_bytes = 0
                # Use larger chunks for better performance (2MB)
                async for chunk in client.stream_media(message, limit=2 * 1024 * 1024):
                    chunk_count += 1
                    total_bytes += len(chunk)
                    if chunk_count % 25 == 0:  # Log every 50MB
                        logger.info(f"Raw stream: {chunk_count} chunks, {total_bytes // (1024*1024)}MB")
                    yield chunk
                logger.info(f"Raw stream completed: {chunk_count} chunks, {total_bytes // (1024*1024)}MB")
            except Exception as e:
                logger.error(f"Raw stream interrupted: {e}")
        
        headers = {
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
            # IMPORTANT: Do NOT set Accept-Ranges to prevent browser range requests
            # "Accept-Ranges": "none"  # Explicitly disable range requests
        }
        
        # Do NOT add Content-Length to use chunked encoding and avoid mismatch errors
        
        return StreamingResponse(
            raw_stream(),
            media_type=mime_type,
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"Raw stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simple-stream/{chat_id}/{message_id}")
async def simple_stream_media(chat_id: str, message_id: int):
    """Simple streaming without Content-Length for large files"""
    try:
        logger.info(f"Simple stream: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            actual_chat_id = int(chat_id)
        
        # Get message
        message = await client.get_messages(actual_chat_id, message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get basic file info
        mime_type = "application/octet-stream"
        file_name = "file"
        
        if message.video:
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
        elif message.document:
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
        elif message.audio:
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
        
        # Simple streaming without Content-Length
        async def simple_stream():
            try:
                async for chunk in client.stream_media(message):
                    yield chunk
            except Exception as e:
                logger.error(f"Simple stream error: {e}")
        
        headers = {
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600"
        }
        
        return StreamingResponse(simple_stream(), headers=headers, media_type=mime_type)
        
    except Exception as e:
        logger.error(f"Simple stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proxy/{chat_id}/{message_id}")
async def proxy_media(chat_id: str, message_id: int, request: Request):
    """Enhanced proxy with better range request support for external players"""
    try:
        logger.info(f"Proxy request: {chat_id}/{message_id}")
        
        # Convert chat_id
        if chat_id.startswith('@'):
            actual_chat_id = chat_id
        else:
            try:
                actual_chat_id = int(chat_id)
            except ValueError as e:
                logger.error(f"Invalid chat_id format: {chat_id}")
                raise HTTPException(status_code=400, detail=f"Invalid chat_id: {chat_id}")
        
        logger.info(f"Resolved chat_id: {actual_chat_id}")
        
        # Get message
        try:
            message = await client.get_messages(actual_chat_id, message_id)
        except Exception as e:
            logger.error(f"Failed to get message {message_id} from {actual_chat_id}: {e}")
            raise HTTPException(status_code=404, detail=f"Could not fetch message: {str(e)}")
        
        if not message or not message.media:
            logger.error(f"Message {message_id} has no media")
            raise HTTPException(status_code=404, detail="Media not found")
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        # Get file info
        file_size = 0
        mime_type = "application/octet-stream"
        file_name = "file"
        
        if message.video:
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
            file_name = message.video.file_name or f"video_{message_id}.mp4"
        elif message.audio:
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
        elif message.photo:
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
            file_name = f"photo_{message_id}.jpg"
        elif message.document:
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
            file_name = message.document.file_name or f"document_{message_id}"
        
        # Enhanced range request handling
        range_header = request.headers.get("range")
        
        if range_header and file_size > 0:
            # Parse range header
            try:
                range_match = range_header.replace("bytes=", "").split("-")
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
                
                # Ensure valid range
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
                content_length = end - start + 1
                
                logger.info(f"Range request: {start}-{end}/{file_size} ({content_length} bytes)")
                
                # For very large ranges, limit to prevent timeouts
                if content_length > 50 * 1024 * 1024:  # 50MB chunks max
                    end = start + (50 * 1024 * 1024) - 1
                    content_length = end - start + 1
                    logger.info(f"Limited range to: {start}-{end}/{file_size} ({content_length} bytes)")
                
                # Stream specific range with optimized chunk size
                async def stream_range():
                    try:
                        bytes_sent = 0
                        chunk_size = min(1024 * 1024, content_length)  # 1MB or remaining bytes
                        
                        async for chunk in client.stream_media(message, offset=start, limit=content_length):
                            if bytes_sent + len(chunk) > content_length:
                                # Trim last chunk to exact size
                                chunk = chunk[:content_length - bytes_sent]
                            
                            yield chunk
                            bytes_sent += len(chunk)
                            
                            if bytes_sent >= content_length:
                                break
                                
                    except Exception as e:
                        logger.error(f"Range stream error: {e}")
                        # Don't re-raise to avoid Content-Length mismatch
                
                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(content_length),
                    "Content-Type": mime_type,
                    "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Range, Content-Type",
                    "Access-Control-Expose-Headers": "Content-Range, Content-Length",
                    "Cache-Control": "public, max-age=3600"
                }
                
                return StreamingResponse(
                    stream_range(),
                    status_code=206,
                    headers=headers,
                    media_type=mime_type
                )
            except ValueError as e:
                logger.error(f"Invalid range header: {range_header}")
                # Fall through to full file stream
        
        # Full file stream with enhanced headers for external players
        async def stream_full():
            try:
                chunk_count = 0
                total_bytes = 0
                async for chunk in client.stream_media(message):
                    chunk_count += 1
                    total_bytes += len(chunk)
                    
                    # Log progress for large files every 100 chunks (roughly every 10MB)
                    if chunk_count % 100 == 0:
                        logger.info(f"Streamed {chunk_count} chunks ({total_bytes // (1024*1024)}MB)")
                    
                    yield chunk
                    
                logger.info(f"Stream completed. Total: {chunk_count} chunks, {total_bytes // (1024*1024)}MB")
            except Exception as e:
                logger.error(f"Full stream error: {e}")
                # Don't re-raise the exception, just log it and end the stream
                # This prevents the Content-Length mismatch error
        
        headers = {
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{sanitize_filename(file_name)}"',
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges",
            "Cache-Control": "public, max-age=3600",
            # Headers specifically for external players
            "X-Content-Type-Options": "nosniff",
            "Connection": "keep-alive"
        }
        
        # Only add Content-Length for smaller files to avoid mismatch issues
        if file_size > 0 and file_size < 50 * 1024 * 1024:  # Only for files < 50MB
            headers["Content-Length"] = str(file_size)
        
        return StreamingResponse(
            stream_full(),
            headers=headers,
            media_type=mime_type
        )
        
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream/{chat_id}/{message_id}")
async def stream_media(chat_id: str, message_id: int, request: Request):
    """Stream media with enhanced error handling and debugging"""
    try:
        logger.info(f"Stream request: chat_id={chat_id}, message_id={message_id}")
        
        # Convert chat_id to proper format
        if isinstance(chat_id, str) and chat_id.startswith('@'):
            # Keep username format
            actual_chat_id = chat_id
        else:
            try:
                actual_chat_id = int(chat_id)
            except (ValueError, TypeError):
                actual_chat_id = chat_id
        
        logger.info(f"Resolved chat_id: {actual_chat_id}")
        
        # Fetch the message with better error handling
        try:
            message = await client.get_messages(actual_chat_id, message_id)
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            raise HTTPException(status_code=404, detail=f"Could not fetch message: {str(e)}")
        
        if not message:
            logger.error("Message is None")
            raise HTTPException(status_code=404, detail="Message not found")
            
        if not message.media:
            logger.error("Message has no media")
            raise HTTPException(status_code=400, detail="Message does not contain any media")
        
        logger.info(f"Message found with media type: {type(message.media)}")
        
        # Get file info with better detection
        file_name = "file"
        file_size = 0
        mime_type = "application/octet-stream"
        
        if message.video:
            file_name = message.video.file_name or f"video_{message_id}.mp4"
            file_size = message.video.file_size
            mime_type = message.video.mime_type or "video/mp4"
            logger.info(f"Video file: {file_name}, size: {file_size}, type: {mime_type}")
        elif message.audio:
            file_name = message.audio.file_name or f"audio_{message_id}.mp3"
            file_size = message.audio.file_size
            mime_type = message.audio.mime_type or "audio/mpeg"
            logger.info(f"Audio file: {file_name}, size: {file_size}, type: {mime_type}")
        elif message.photo:
            file_name = f"photo_{message_id}.jpg"
            file_size = message.photo.file_size
            mime_type = "image/jpeg"
            logger.info(f"Photo file: {file_name}, size: {file_size}, type: {mime_type}")
        elif message.document:
            file_name = message.document.file_name or f"document_{message_id}"
            file_size = message.document.file_size
            mime_type = message.document.mime_type or "application/octet-stream"
            logger.info(f"Document file: {file_name}, size: {file_size}, type: {mime_type}")
        elif message.animation:
            file_name = message.animation.file_name or f"animation_{message_id}.mp4"
            file_size = message.animation.file_size
            mime_type = message.animation.mime_type or "video/mp4"
            logger.info(f"Animation file: {file_name}, size: {file_size}, type: {mime_type}")
        elif message.voice:
            file_name = f"voice_{message_id}.ogg"
            file_size = message.voice.file_size
            mime_type = message.voice.mime_type or "audio/ogg"
            logger.info(f"Voice file: {file_name}, size: {file_size}, type: {mime_type}")
        
        # Simple streaming without range requests for now
        logger.info("Starting stream...")
        
        headers = {
            "Content-Disposition": f'inline; filename="{file_name}"',
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range"
        }
        
        if file_size > 0:
            headers["Content-Length"] = str(file_size)
        
        # Create streaming generator
        async def generate_stream():
            try:
                logger.info("Starting media stream...")
                chunk_count = 0
                async for chunk in client.stream_media(message):
                    chunk_count += 1
                    if chunk_count % 100 == 0:  # Log every 100 chunks
                        logger.info(f"Streamed {chunk_count} chunks")
                    yield chunk
                logger.info(f"Stream completed. Total chunks: {chunk_count}")
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                raise
        
        return StreamingResponse(
            generate_stream(),
            headers=headers,
            media_type=mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")


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
    
    # H.264 MP4 is the gold standard for web streaming
    excellent_streaming_formats = [
        "video/mp4",  # H.264 MP4 - best for web
        "video/webm", # WebM - good for web
        "audio/mp4",  # AAC in MP4
        "audio/mpeg", # MP3
        "audio/wav",  # WAV
        "audio/ogg"   # OGG
    ]
    
    # These can work but aren't ideal
    okay_streaming_formats = [
        "video/avi",
        "audio/aac",
        "audio/webm"
    ]
    
    # These won't work in browsers
    non_streaming_formats = [
        "video/x-matroska",  # MKV
        "video/x-msvideo",   # AVI (sometimes)
        "video/quicktime",   # MOV (sometimes)
        "application/octet-stream"  # Unknown
    ]
    
    if message.document:
        mime_type = message.document.mime_type or "application/octet-stream"
        file_name = message.document.file_name or f"document_{message.id}"
        
        # Better detection based on file extension if mime type is generic
        if mime_type == "application/octet-stream" and file_name:
            ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
            if ext == 'mp4':
                mime_type = "video/mp4"
            elif ext == 'mkv':
                mime_type = "video/x-matroska"
            elif ext == 'webm':
                mime_type = "video/webm"
            elif ext == 'mp3':
                mime_type = "audio/mpeg"
        
        file_info.update({
            "name": file_name,
            "size": format_size(message.document.file_size),
            "size_bytes": message.document.file_size,
            "type": mime_type,
            "icon": get_file_icon(mime_type),
            "has_thumbnail": bool(message.document.thumbs),
            "can_stream": (
                mime_type in excellent_streaming_formats or 
                mime_type in okay_streaming_formats or
                mime_type.startswith("image/")
            ),
            "stream_quality": "excellent" if mime_type in excellent_streaming_formats else "okay" if mime_type in okay_streaming_formats else "poor"
        })
    elif message.video:
        mime_type = message.video.mime_type or "video/mp4"
        file_info.update({
            "name": message.video.file_name or f"video_{message.id}.mp4",
            "size": format_size(message.video.file_size),
            "size_bytes": message.video.file_size,
            "type": mime_type,
            "icon": "🎥",
            "has_thumbnail": bool(message.video.thumbs),
            "can_stream": mime_type in excellent_streaming_formats or mime_type in okay_streaming_formats,
            "stream_quality": "excellent" if mime_type in excellent_streaming_formats else "okay"
        })
    elif message.audio:
        mime_type = message.audio.mime_type or "audio/mpeg"
        file_info.update({
            "name": message.audio.file_name or f"audio_{message.id}.mp3",
            "size": format_size(message.audio.file_size),
            "size_bytes": message.audio.file_size,
            "type": mime_type,
            "icon": "🎵",
            "has_thumbnail": bool(message.audio.thumbs) if hasattr(message.audio, 'thumbs') else False,
            "can_stream": True,
            "stream_quality": "excellent"
        })
    elif message.photo:
        file_info.update({
            "name": f"photo_{message.id}.jpg",
            "size": format_size(message.photo.file_size),
            "size_bytes": message.photo.file_size,
            "type": "image/jpeg",
            "icon": "🖼️",
            "has_thumbnail": True,
            "can_stream": True,
            "stream_quality": "excellent"
        })
    elif message.voice:
        file_info.update({
            "name": f"voice_{message.id}.ogg",
            "size": format_size(message.voice.file_size),
            "size_bytes": message.voice.file_size,
            "type": "audio/ogg",
            "icon": "🎤",
            "has_thumbnail": False,
            "can_stream": True,
            "stream_quality": "excellent"
        })
    elif message.animation:
        file_info.update({
            "name": message.animation.file_name or f"animation_{message.id}.mp4",
            "size": format_size(message.animation.file_size),
            "size_bytes": message.animation.file_size,
            "type": "video/mp4",  # Animations are usually MP4
            "icon": "🎬",
            "has_thumbnail": bool(message.animation.thumbs),
            "can_stream": True,
            "stream_quality": "excellent"
        })
    else:
        return None
    
    # Generate URLs - use external streamer if available for better performance
    if STREAMER_URL:
        file_info["download_url"] = f"{STREAMER_URL}/stream/{channel_id}/{message.id}"
        file_info["stream_url"] = f"{STREAMER_URL}/stream/{channel_id}/{message.id}"
        file_info["external_streamer"] = True
        file_info["performance"] = "optimized"
    else:
        file_info["download_url"] = f"/dl/{channel_id}/{message.id}"
        file_info["stream_url"] = f"/raw-stream/{channel_id}/{message.id}"
        file_info["external_streamer"] = False
        file_info["performance"] = "basic"
    
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
