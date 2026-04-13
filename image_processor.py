# image_processor.py
import requests
from PIL import Image, ImageOps
import io
from typing import Optional
from urllib.parse import urlparse
import logging


class ImageProcessor:
    """Advanced image processing for Telegram Autopost Bot"""

    def __init__(self, logger: logging.Logger, max_size: int = 1000, quality: int = 85):
        self.logger = logger
        self.max_size = max_size
        self.quality = quality
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AutopostBot/1.0)',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        })

    def process_image_from_url(self, url: str) -> Optional[bytes]:
        """
        Download, process, and convert image from URL

        Args:
            url: Image URL from Article.media_content

        Returns:
            Processed image as bytes (JPG format) or None if failed
        """
        try:
            self.logger.info(f"Processing image from URL: {url}")

            # Download image
            image_data = self._download_image(url)
            if not image_data:
                return None

            # Process image
            processed_image = self._process_image(image_data)
            if not processed_image:
                return None

            self.logger.info(f"Successfully processed image from {url}")
            return processed_image

        except Exception as e:
            self.logger.error(f"Error processing image from {url}: {str(e)}")
            return None

    def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL with proper error handling"""
        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                self.logger.error(f"Invalid URL format: {url}")
                return None

            # Download with timeout and size limits
            response = self.session.get(
                url,
                timeout=15,
                stream=True,
                headers={'Accept': 'image/*'}
            )
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                self.logger.warning(f"URL does not point to an image: {content_type}")
                return None

            # Check file size (max 20MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 40 * 1024 * 1024:
                self.logger.warning(f"Image too large: {content_length} bytes")
                return None

            # Download image data
            image_data = b''
            downloaded_size = 0
            max_download_size = 40 * 1024 * 1024  # 20MB limit

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    if downloaded_size > max_download_size:
                        self.logger.warning(f"Download size exceeded limit: {downloaded_size}")
                        return None
                    image_data += chunk

            if len(image_data) < 100:  # Minimum viable image size
                self.logger.warning(f"Downloaded image too small: {len(image_data)} bytes")
                return None

            self.logger.info(f"Downloaded image: {len(image_data)} bytes")
            return image_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading image from {url}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error downloading image: {str(e)}")
            return None

    def _process_image(self, image_data: bytes) -> Optional[bytes]:
        """Process image: resize, convert to JPG, optimize"""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (handles RGBA, P, etc.)
            if image.mode != 'RGB':
                # For RGBA images, create white background
                if image.mode == 'RGBA':
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                    image = rgb_image
                else:
                    image = image.convert('RGB')

            # Apply auto-orientation based on EXIF data
            image = ImageOps.exif_transpose(image)

            # Get original dimensions
            original_width, original_height = image.size
            self.logger.info(f"Original image size: {original_width}x{original_height}")

            # Resize if necessary
            if max(original_width, original_height) > self.max_size:
                image = self._resize_image(image, self.max_size)
                new_width, new_height = image.size
                self.logger.info(f"Resized image to: {new_width}x{new_height}")

            # Convert to JPG and optimize
            output_buffer = io.BytesIO()
            image.save(
                output_buffer,
                format='JPEG',
                quality=self.quality,
                optimize=True,
                progressive=True
            )

            processed_data = output_buffer.getvalue()
            output_buffer.close()

            # Log compression results
            original_size = len(image_data)
            processed_size = len(processed_data)
            compression_ratio = (1 - processed_size / original_size) * 100

            self.logger.info(
                f"Image processing complete: {original_size} bytes -> {processed_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )

            return processed_data

        except Exception as e:
            self.logger.error(f"Error processing image: {str(e)}")
            return None

    def _resize_image(self, image: Image.Image, max_size: int) -> Image.Image:
        """Resize image maintaining aspect ratio"""
        width, height = image.size

        # Calculate new dimensions
        if width > height:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            new_height = max_size
            new_width = int(width * max_size / height)

        # Use high-quality resampling
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def validate_image_url(self, url: str) -> bool:
        """Validate if URL points to a supported image"""
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return False

            # Check file extension
            path = parsed_url.path.lower()
            supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

            if any(path.endswith(ext) for ext in supported_extensions):
                return True

            # If no extension, try HEAD request to check content type
            try:
                response = self.session.head(url, timeout=5)
                content_type = response.headers.get('content-type', '').lower()
                return content_type.startswith('image/')
            except Exception:
                return False

        except Exception:
            return False




