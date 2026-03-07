# ============================================
# TorStream - Captcha Generator
# ============================================

import io
import base64
import random
import string
import secrets
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from app.services.redis import redis_service
import logging

logger = logging.getLogger(__name__)


class CaptchaGenerator:
    """Image-based captcha generator with Redis storage."""
    
    def __init__(
        self,
        width: int = 200,
        height: int = 70,
        length: int = 6,
        expiry_seconds: int = 300
    ):
        self.width = width
        self.height = height
        self.length = length
        self.expiry_seconds = expiry_seconds
        
        # Try to load a font, fallback to default
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        except:
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 36)
            except:
                self.font = ImageFont.load_default()
    
    def _generate_code(self) -> str:
        """Generate random alphanumeric code."""
        # Use alphanumeric characters, excluding confusing ones
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(chars) for _ in range(self.length))
    
    def _generate_math_problem(self) -> Tuple[str, str]:
        """Generate simple math problem as fallback."""
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        operator = random.choice(["+", "-"])
        
        if operator == "+":
            answer = a + b
        else:
            # Ensure positive result
            if a < b:
                a, b = b, a
            answer = a - b
        
        problem = f"{a} {operator} {b} = ?"
        return problem, str(answer)
    
    def _create_image(self, text: str) -> Image.Image:
        """Create captcha image with distortion."""
        # Create background with gradient
        image = Image.new('RGB', (self.width, self.height), color='#f0f0f0')
        draw = ImageDraw.Draw(image)
        
        # Add random background noise
        for _ in range(1000):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            color = random.randint(200, 255)
            draw.point((x, y), fill=(color, color, color))
        
        # Add random lines
        for _ in range(5):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            color = random.randint(100, 200)
            draw.line([(x1, y1), (x2, y2)], fill=(color, color, color), width=2)
        
        # Calculate text position for centering
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2 - 5
        
        # Draw text with slight distortion
        for i, char in enumerate(text):
            char_x = x + (i * text_width // len(text))
            char_y = y + random.randint(-3, 3)
            
            # Random color for each character
            color = (
                random.randint(0, 100),
                random.randint(0, 100),
                random.randint(0, 100)
            )
            
            draw.text((char_x, char_y), char, font=self.font, fill=color)
        
        # Add more random lines over text
        for _ in range(3):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            color = random.randint(150, 220)
            draw.line([(x1, y1), (x2, y2)], fill=(color, color, color), width=1)
        
        # Apply slight blur
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        return image
    
    async def generate(self) -> Optional[Tuple[str, str]]:
        """
        Generate captcha and store in Redis.
        Returns (token, base64_image) or None if Redis unavailable.
        """
        # Check Redis availability
        if not redis_service.is_available:
            logger.warning("Redis unavailable, cannot generate captcha")
            return None
        
        try:
            # Generate code and token
            code = self._generate_code()
            token = secrets.token_urlsafe(32)
            
            # Create image
            image = self._create_image(code)
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Store in Redis (lowercase for case-insensitive comparison)
            await redis_service.set(
                f"captcha:{token}",
                code.lower(),
                expire=self.expiry_seconds
            )
            
            return token, image_base64
            
        except Exception as e:
            logger.error(f"Captcha generation error: {e}")
            return None
    
    async def generate_math_fallback(self) -> Optional[Tuple[str, str, str]]:
        """
        Generate math captcha as fallback.
        Returns (token, problem_text, answer).
        """
        if not redis_service.is_available:
            return None
        
        try:
            problem, answer = self._generate_math_problem()
            token = secrets.token_urlsafe(32)
            
            # Store answer
            await redis_service.set(
                f"captcha:{token}",
                answer,
                expire=self.expiry_seconds
            )
            
            return token, problem, answer
            
        except Exception as e:
            logger.error(f"Math captcha generation error: {e}")
            return None
    
    async def verify(self, token: str, code: str) -> bool:
        """Verify captcha code."""
        if not token or not code:
            return False
        
        if not redis_service.is_available:
            logger.warning("Redis unavailable, cannot verify captcha")
            return False
        
        try:
            # Get stored code
            stored_code = await redis_service.get_str(f"captcha:{token}")
            
            if not stored_code:
                return False
            
            # Verify (case-insensitive)
            valid = stored_code.lower() == code.lower().strip()
            
            # Delete token after use (one-time)
            await redis_service.delete(f"captcha:{token}")
            
            return valid
            
        except Exception as e:
            logger.error(f"Captcha verification error: {e}")
            return False
    
    async def refresh(self, old_token: str) -> Optional[Tuple[str, str]]:
        """Refresh captcha (invalidate old, generate new)."""
        if old_token:
            await redis_service.delete(f"captcha:{old_token}")
        
        return await self.generate()


# Global captcha generator instance
captcha_generator = CaptchaGenerator()


async def get_captcha_generator() -> CaptchaGenerator:
    """Get captcha generator instance."""
    return captcha_generator
