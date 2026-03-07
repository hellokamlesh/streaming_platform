# ============================================
# TorStream - Video Processor
# ============================================

import os
import subprocess
import logging
import json
import secrets  # ← ADDED for generate_filename
from pathlib import Path
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Video processing with FFmpeg."""
    
    ALLOWED_MIME_TYPES = {
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'video/ogg': '.ogv',
        'video/x-matroska': '.mkv',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/x-flv': '.flv',
    }
    
    # Extended signatures for MP4 and other formats
    ALLOWED_SIGNATURES = {
        b'\x00\x00\x00\x18ftypmp41': 'video/mp4',
        b'\x00\x00\x00\x18ftypmp42': 'video/mp4',
        b'\x00\x00\x00\x14ftypisom': 'video/mp4',
        b'\x00\x00\x00\x1cftypisom': 'video/mp4',
        b'\x00\x00\x00\x20ftypisom': 'video/mp4',
        b'\x00\x00\x00\x18ftypMSNV': 'video/mp4',
        b'\x00\x00\x00\x18ftypavc1': 'video/mp4',
        b'\x00\x00\x00\x18ftyp3gp4': 'video/mp4',
        b'\x00\x00\x00\x18ftyp3gp5': 'video/mp4',
        b'\x1aE\xdf\xa3': 'video/webm',
        b'OggS': 'video/ogg',
        b'\x1aE\xdf\xa3\x01\x00\x00\x00': 'video/x-matroska',
        b'\x00\x00\x00 ftyp': 'video/mp4',
        b'ftyp': 'video/mp4',
        b'RIFF': 'video/avi',
        b'FLV': 'video/x-flv',
    }
    
    def __init__(self):
        self.storage_path = Path(settings.VIDEO_STORAGE_PATH)
        self.preview_path = Path(settings.PREVIEW_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.preview_path.mkdir(parents=True, exist_ok=True)
    
    def verify_file_signature(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Verify file signature matches allowed types."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            # Try to match signatures
            for signature, mime_type in self.ALLOWED_SIGNATURES.items():
                if header.startswith(signature):
                    logger.info(f"File signature matched: {mime_type}")
                    return True, mime_type
            
            # If no signature match, try ffprobe as fallback
            logger.info("No signature match, trying ffprobe validation")
            return self.verify_with_ffprobe(file_path)
            
        except Exception as e:
            logger.error(f"File signature verification error: {e}")
            return False, None
    
    def verify_with_ffprobe(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Use ffprobe to verify file is a valid video."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Check if there's a video stream
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        # Determine mime type from file extension
                        ext = Path(file_path).suffix.lower()
                        mime_map = {
                            '.mp4': 'video/mp4',
                            '.webm': 'video/webm',
                            '.mkv': 'video/x-matroska',
                            '.mov': 'video/quicktime',
                            '.avi': 'video/x-msvideo',
                            '.flv': 'video/x-flv',
                            '.ogv': 'video/ogg',
                        }
                        mime_type = mime_map.get(ext, 'video/mp4')
                        logger.info(f"FFprobe validated video: {mime_type}")
                        return True, mime_type
                
                logger.warning("No video stream found in file")
                return False, None
            else:
                logger.warning(f"FFprobe failed: {result.stderr}")
                return False, None
                
        except Exception as e:
            logger.error(f"FFprobe validation error: {e}")
            return False, None
    
    def validate_mime_type(self, mime_type: str) -> bool:
        """Validate MIME type is allowed."""
        return mime_type in self.ALLOWED_MIME_TYPES
    
    def get_file_extension(self, mime_type: str) -> str:
        """Get file extension for MIME type."""
        return self.ALLOWED_MIME_TYPES.get(mime_type, '.mp4')
    
    # ===== ADDED generate_filename METHOD =====
    def generate_filename(self, original_filename: str, mime_type: str) -> str:
        """Generate secure random filename."""
        # Get extension from mime type
        ext = self.get_file_extension(mime_type)
        
        # If extension is still default .mp4, try to get from original filename
        if ext == '.mp4':
            original_ext = os.path.splitext(original_filename)[1].lower()
            if original_ext in ['.mp4', '.webm', '.mkv', '.mov', '.avi', '.flv', '.ogv']:
                ext = original_ext
        
        # Generate random name
        random_name = secrets.token_urlsafe(16)
        return f"{random_name}{ext}"
    # =========================================
    
    async def get_video_duration(self, file_path: str) -> Optional[int]:
        """Get video duration in seconds using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return int(duration)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return None
    
    async def generate_preview(
        self,
        input_path: str,
        output_filename: str,
        duration: int = 15
    ) -> Optional[str]:
        """
        Generate preview clip from video.
        Returns output filename or None on failure.
        """
        try:
            output_path = self.preview_path / output_filename
            
            # Get video duration
            video_duration = await self.get_video_duration(input_path)
            if not video_duration:
                logger.error("Could not determine video duration")
                return None
            
            # Calculate start time (start at 10% or 5 seconds, whichever is less)
            start_time = min(video_duration * 0.1, 5)
            
            # Ensure we don't exceed video length
            preview_duration = min(duration, video_duration - start_time)
            if preview_duration <= 0:
                preview_duration = min(15, video_duration)
                start_time = 0
            
            # Generate preview with FFmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-ss', str(start_time),
                '-t', str(preview_duration),
                '-i', input_path,
                '-vf', 'scale=480:-2',  # Scale to 480px width, maintain aspect
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '28',  # Quality (lower is better)
                '-c:a', 'aac',
                '-b:a', '96k',
                '-movflags', '+faststart',
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"Preview generated: {output_filename}")
                return output_filename
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Preview generation timed out")
            return None
        except Exception as e:
            logger.error(f"Preview generation error: {e}")
            return None
    
    async def generate_thumbnail(
        self,
        input_path: str,
        output_filename: str,
        time_offset: str = "00:00:05"
    ) -> Optional[str]:
        """
        Generate thumbnail from video.
        Returns output filename or None on failure.
        """
        try:
            output_path = self.preview_path / output_filename
            
            cmd = [
                'ffmpeg',
                '-y',
                '-ss', time_offset,
                '-i', input_path,
                '-vframes', '1',
                '-vf', 'scale=320:-2',
                '-q:v', '2',
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Thumbnail generated: {output_filename}")
                return output_filename
            else:
                logger.error(f"FFmpeg thumbnail error: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Thumbnail generation error: {e}")
            return None
    
    async def strip_metadata(self, input_path: str, output_path: str) -> bool:
        """Strip metadata from video file."""
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-map_metadata', '-1',  # Remove metadata
                '-c:v', 'copy',
                '-c:a', 'copy',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Metadata stripping error: {e}")
            return False
    
    async def optimize_for_streaming(self, input_path: str, output_path: str) -> bool:
        """Optimize video for streaming (faststart, appropriate bitrate)."""
        try:
            cmd = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-maxrate', '2M',
                '-bufsize', '4M',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Streaming optimization error: {e}")
            return False


# Global video processor instance
video_processor = VideoProcessor()