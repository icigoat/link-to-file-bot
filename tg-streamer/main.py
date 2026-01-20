#!/usr/bin/env python3
"""
TG File Streamer - Middleman Service for Fast Streaming
Deploy this to a free host like Railway, Render, or Vercel
"""

import os
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client
from pyrogram.errors import RPCError
import uvicorn
from dotenv import load_dotenv

# Load environment variables
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
    raise ValueError("Missing required environment variables")

# Initialize FastAPI
app = FastAPI(title="TG File Streamer", description="High-speed Telegram file streaming service")

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Pyrogram Client
client = Client(
    name="tg_streamer",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
    no_updates=True,
    takeout=False
)

@app.on_event("startup")
async def startup_event():
    """Start Pyrogram client"""
    await client.start()
    logger.info("TG Streamer started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop Pyrogram client"""
    await client.stop()
    logger.info("TG Streamer stopped")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "TG File Streamer",
        "status": "running",
        "version": "1.0.0",
        "features": ["range_requests", "cors_enabled", "high_speed_streaming"]
    }

@app.options("/stream/{chat_id}/{message_id}")
async def stream_options(chat_id: str, message_id: int):
    """Handle CORS preflight requests"""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.head("/stream/{chat_id}/{message_id}")
async def stream_head(chat_id: str, message_id: int):
    """Handle HEAD requests for media info"""
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
        file_size, mime_type, file_name = get_file_info(message, message_id)
        
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size) if file_size > 0 else "0",
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_name}"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Cache-Control": "public, max-age=3600"
        }
        
        return Response(headers=headers)
        
    except Exception as e:
        logger.error(f"HEAD request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{chat_id}/{message_id}")
async def stream_file(chat_id: str, message_id: int, request: Request):
    """
    High-speed streaming with optimized range requests
    This is the main endpoint that external players will use
    """
    try:
        logger.info(f"Stream request: {chat_id}/{message_id}")
        
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
        file_size, mime_type, file_name = get_file_info(message, message_id)
        
        # Handle range requests (critical for video seeking)
        range_header = request.headers.get("range")
        
        if range_header and file_size > 0:
            return await handle_range_request(message, range_header, file_size, mime_type, file_name)
        else:
            return await handle_full_request(message, file_size, mime_type, file_name)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_range_request(message, range_header: str, file_size: int, mime_type: str, file_name: str):
    """Handle HTTP 206 range requests for seeking"""
    try:
        # Parse range header
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
        
        # Validate range
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1
        
        logger.info(f"Range: {start}-{end}/{file_size} ({content_length} bytes)")
        
        # Optimized streaming generator
        async def stream_range():
            bytes_sent = 0
            chunk_size = min(1024 * 1024, content_length)  # 1MB chunks or remaining
            
            try:
                async for chunk in client.stream_media(message, offset=start, limit=content_length):
                    # Ensure we don't exceed the requested range
                    if bytes_sent + len(chunk) > content_length:
                        chunk = chunk[:content_length - bytes_sent]
                    
                    yield chunk
                    bytes_sent += len(chunk)
                    
                    if bytes_sent >= content_length:
                        break
                        
            except Exception as e:
                logger.error(f"Range streaming error: {e}")
                raise
        
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
            "Content-Disposition": f'inline; filename="{file_name}"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges",
            "Cache-Control": "public, max-age=3600",
            # Optimize for external players
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff"
        }
        
        return StreamingResponse(
            stream_range(),
            status_code=206,
            headers=headers,
            media_type=mime_type
        )
        
    except ValueError as e:
        logger.error(f"Invalid range: {range_header}")
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")

async def handle_full_request(message, file_size: int, mime_type: str, file_name: str):
    """Handle full file streaming"""
    async def stream_full():
        try:
            chunk_count = 0
            async for chunk in client.stream_media(message):
                chunk_count += 1
                # Log progress for large files
                if chunk_count % 1000 == 0:
                    logger.info(f"Streamed {chunk_count} chunks")
                yield chunk
        except Exception as e:
            logger.error(f"Full streaming error: {e}")
            raise
    
    headers = {
        "Content-Type": mime_type,
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Length, Accept-Ranges",
        "Cache-Control": "public, max-age=3600",
        "Connection": "keep-alive"
    }
    
    if file_size > 0:
        headers["Content-Length"] = str(file_size)
    
    return StreamingResponse(
        stream_full(),
        headers=headers,
        media_type=mime_type
    )

def get_file_info(message, message_id: int):
    """Extract file information from message"""
    file_size = 0
    mime_type = "application/octet-stream"
    file_name = f"file_{message_id}"
    
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
        
        # Better MIME type detection
        if mime_type == "application/octet-stream" and file_name:
            ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
            mime_map = {
                'mp4': 'video/mp4',
                'mkv': 'video/x-matroska',
                'avi': 'video/x-msvideo',
                'webm': 'video/webm',
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav',
                'ogg': 'audio/ogg'
            }
            mime_type = mime_map.get(ext, mime_type)
    
    return file_size, mime_type, file_name

@app.get("/info/{chat_id}/{message_id}")
async def get_file_info_endpoint(chat_id: str, message_id: int):
    """Get file information without streaming"""
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
        
        file_size, mime_type, file_name = get_file_info(message, message_id)
        
        return {
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "stream_url": f"/stream/{chat_id}/{message_id}",
            "supports_range": True,
            "optimized_for": ["vlc", "mx_player", "web_browsers"]
        }
        
    except Exception as e:
        logger.error(f"Info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)