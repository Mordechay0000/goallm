import sqlite3
import hashlib
from io import BytesIO
import time
import os
import logging
import magic

from PIL import Image

from core.image_processing import simulated_image_analyzer
try:
    from core.image_processing.llm_image_analyzer import LLMImageAnalyzer
except ImportError:
    LLMImageAnalyzer = None  # Optional dependency
from core.image_processing.image_processing_queue import ImageProcessingQueue
from data.constants import IMAGE_STATUS_TABLE_NAME, BLOCK_IMAGE, CHECKING_IMAGE, ERROR_IMAGE

logger = logging.getLogger(__name__)

# Ensure .storage directory exists
os.makedirs(".storage", exist_ok=True)

db_connection = sqlite3.connect(".storage/image_status.db", check_same_thread=False)
db_connection.execute("PRAGMA journal_mode=WAL;")
db_connection.execute("PRAGMA synchronous=NORMAL;")

# Initialize/update table schema
def init_db_schema():
    """Initialize or update database schema with required columns."""
    logger.info("Initializing database schema...")
    logger.debug(f"Table name: {IMAGE_STATUS_TABLE_NAME}")
    
    db_connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {IMAGE_STATUS_TABLE_NAME} (
            image_hash TEXT PRIMARY KEY,
            image_url TEXT,
            status TEXT,
            mime_type TEXT,
            width INTEGER,
            height INTEGER,
            female_visible_9_plus INTEGER,
            female_3_to_9_partial_clothing INTEGER,
            female_under_3_minimal_clothing INTEGER,
            boys_teens_men_exposed_or_bathing INTEGER,
            any_visible_body_exposure INTEGER,
            updated_at INTEGER
        )
    """)
    logger.debug("Created table if not exists")
    
    # Add new columns if they don't exist (for existing databases)
    try:
        db_connection.execute(f"ALTER TABLE {IMAGE_STATUS_TABLE_NAME} ADD COLUMN mime_type TEXT")
        logger.debug("Added mime_type column")
    except sqlite3.OperationalError:
        logger.debug("mime_type column already exists")
    
    try:
        db_connection.execute(f"ALTER TABLE {IMAGE_STATUS_TABLE_NAME} ADD COLUMN width INTEGER")
        logger.debug("Added width column")
    except sqlite3.OperationalError:
        logger.debug("width column already exists")
    
    try:
        db_connection.execute(f"ALTER TABLE {IMAGE_STATUS_TABLE_NAME} ADD COLUMN height INTEGER")
        logger.debug("Added height column")
    except sqlite3.OperationalError:
        logger.debug("height column already exists")
    
    db_connection.commit()
    logger.info("Database schema initialized successfully")

# Initialize schema on import
init_db_schema()


def save_analysis_result(image_hash: str, result: dict, image_url: str | None = None, mime_type: str | None = None, width: int | None = None, height: int | None = None):
    logger.info(f"Saving analysis result for image hash: {image_hash[:8]}...")
    logger.debug(f"Image URL: {image_url}, MIME: {mime_type}, Size: {width}x{height}")
    logger.debug(f"Analysis result: {result}")
    
    blocked = any(v == "Yes" for v in result.values())
    logger.info(f"Image blocked status: {blocked}")

    db_connection.execute(
        f"""
        INSERT INTO {IMAGE_STATUS_TABLE_NAME} (
            image_hash,
            image_url,
            status,
            mime_type,
            width,
            height,
            female_visible_9_plus,
            female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing,
            boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            image_url = COALESCE(excluded.image_url, image_url),
            status = excluded.status,
            mime_type = COALESCE(excluded.mime_type, mime_type),
            width = COALESCE(excluded.width, width),
            height = COALESCE(excluded.height, height),
            female_visible_9_plus = excluded.female_visible_9_plus,
            female_3_to_9_partial_clothing = excluded.female_3_to_9_partial_clothing,
            female_under_3_minimal_clothing = excluded.female_under_3_minimal_clothing,
            boys_teens_men_exposed_or_bathing = excluded.boys_teens_men_exposed_or_bathing,
            any_visible_body_exposure = excluded.any_visible_body_exposure,
            updated_at = excluded.updated_at
        """,
        (
            image_hash,
            image_url,
            "blocked" if blocked else "allowed",
            mime_type,
            width,
            height,
            result.get("female_visible_9_plus") == "Yes",
            result.get("female_3_to_9_partial_clothing") == "Yes",
            result.get("female_under_3_minimal_clothing") == "Yes",
            result.get("boys_teens_men_exposed_or_bathing") == "Yes",
            result.get("any_visible_body_exposure") == "Yes",
            int(time.time()),
        ),
    )
    db_connection.commit()


def on_image_analysis_complete(task_id, status, result: dict, image_details: dict, error: str | None):
    """Callback כאשר משימת עיבוד תמונה מסתיימת."""
    # Convert status to string if it's a TaskStatus enum
    status_str = status.value if hasattr(status, 'value') else str(status)
    image_hash = image_details.get('image_hash', 'unknown')
    
    logger.info(f"Image analysis complete - Task ID: {task_id}, Hash: {image_hash[:8]}..., Status: {status_str}")
    logger.debug(f"Task details - URL: {image_details.get('image_url')}, MIME: {image_details.get('mime_type')}, "
                 f"Size: {image_details.get('width')}x{image_details.get('height')}")
    
    if error:
        logger.warning(f"Analysis completed with error for hash {image_hash[:8]}...: {error}")
    
    # Only save result if analysis was successful (result is not None)
    if result is not None:
        logger.debug(f"Analysis result received: {result}")
        save_analysis_result(
            image_details['image_hash'], 
            result, 
            image_details.get('image_url'),
            image_details.get('mime_type'),
            image_details.get('width'),
            image_details.get('height')
        )
        logger.info(f"Successfully processed analysis for hash {image_hash[:8]}...")
    else:
        # Mark as error in database if analysis failed
        logger.error(f"Image analysis failed for hash {image_hash[:8]}...: {error}")
        logger.debug(f"Task ID: {task_id}, Image details: {image_details}")
        # Optionally, you could update the status to 'error' in the database here

def get_image_status(image_hash: str):
    logger.debug(f"Checking image status for hash: {image_hash[:8]}...")
    cur = db_connection.execute(f"SELECT status, mime_type, width, height FROM {IMAGE_STATUS_TABLE_NAME} WHERE image_hash = ?", (image_hash,))
    row = cur.fetchone()
    if row:
        status_info = {
            'status': row[0],
            'mime_type': row[1],
            'width': row[2],
            'height': row[3]
        }
        logger.debug(f"Found status in DB for hash {image_hash[:8]}...: {status_info}")
        return status_info
    logger.debug(f"No status found in DB for hash {image_hash[:8]}...")
    return None

image_processing_queue = ImageProcessingQueue(
    image_analyzer=simulated_image_analyzer.SimulatedImageAnalyzer(), 
    on_task_done=on_image_analysis_complete
)


def mark_pending(image_hash: str, image_url: str | None = None, mime_type: str | None = None, width: int | None = None, height: int | None = None):
    logger.info(f"Marking image as pending - Hash: {image_hash[:8]}..., URL: {image_url}, MIME: {mime_type}, Size: {width}x{height}")
    db_connection.execute(
        f"""
        INSERT INTO {IMAGE_STATUS_TABLE_NAME} (
            image_hash,
            status,
            image_url,
            mime_type,
            width,
            height,
            updated_at
        ) VALUES (?, 'pending', ?, ?, ?, ?, ?)
        ON CONFLICT(image_hash) DO UPDATE SET
            status = 'pending',
            image_url = COALESCE(excluded.image_url, image_url),
            mime_type = COALESCE(excluded.mime_type, mime_type),
            width = COALESCE(excluded.width, width),
            height = COALESCE(excluded.height, height),
            updated_at = excluded.updated_at
        """,
        (
            image_hash,
            image_url,
            mime_type,
            width,
            height,
            int(time.time()),
        ),
    )
    db_connection.commit()


def create_image_content(svg_content: str, mime_type: str, size: tuple | None = None) -> bytes:
    """
    Convert SVG content to image in specified format and size.
    
    Args:
        svg_content: SVG string content
        mime_type: Target mime type (e.g., 'image/png', 'image/jpeg', 'image/webp')
        size: Optional (width, height) tuple. If None, uses default size (800, 600)
        
    Returns:
        Image bytes in specified format
    """
    logger.debug(f"Creating image content - MIME: {mime_type}, Size: {size}")
    try:
        import cairosvg
    except ImportError:
        logger.error("cairosvg not found - required for SVG conversion")
        raise ImportError("cairosvg is required for SVG conversion. Install with: pip install cairosvg")
    
    if size is None:
        logger.warning(
            f"create_image_content called without size parameter (MIME: {mime_type}). "
            f"Using default size (800, 600)."
        )
        size = (800, 600)  # Default size
    logger.debug(f"Using size: {size} for image conversion")
    
    # Convert mime type to format
    mime_to_format = {
        'image/png': 'png',
        'image/jpeg': 'jpeg',
        'image/jpg': 'jpeg',
        'image/webp': 'webp',
        'image/bmp': 'bmp'
    }
    
    format_name = mime_to_format.get(mime_type, 'png')
    logger.debug(f"Target format: {format_name} (from MIME: {mime_type})")
    
    # Create BytesIO buffer
    output = BytesIO()
    
    # Prepare SVG content - ensure it fills the entire size
    width, height = size
    svg_str = svg_content if isinstance(svg_content, str) else svg_content.decode('utf-8')
    
    import re
    # Set preserveAspectRatio to "none" to fill entire area
    if 'preserveAspectRatio=' in svg_str:
        svg_str = re.sub(r'preserveAspectRatio="[^"]*"', 'preserveAspectRatio="none"', svg_str)
    else:
        svg_str = re.sub(r'(<svg[^>]*)>', r'\1 preserveAspectRatio="none">', svg_str, count=1)
    
    svg_bytes = svg_str.encode('utf-8')
    
    # cairosvg handles SVG scaling automatically using viewBox and output dimensions
    # Render SVG at the exact size requested - cairosvg will scale it properly
    cairosvg.svg2png(
        bytestring=svg_bytes,
        write_to=output,
        output_width=width,
        output_height=height
    )
    
    # Verify and fix the output size to match exactly what we requested
    output.seek(0)
    verify_img = Image.open(output)
    if verify_img.size != size:
        logger.debug(f"Image size mismatch: got {verify_img.size}, expected {size}. Resizing...")
        # If size doesn't match, resize it to exact size
        verify_img = verify_img.resize(size, Image.Resampling.LANCZOS)
        output = BytesIO()
        verify_img.save(output, format='PNG')
        output.seek(0)
    
    # If format is not PNG, convert using PIL
    if format_name != 'png':
        output.seek(0)
        img = Image.open(output)
        
        # Ensure the image is exactly the requested size
        if img.size != size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        
        # Convert to appropriate mode for the target format
        if format_name == 'jpeg':
            # JPEG doesn't support alpha channel, convert RGBA to RGB
            if img.mode == 'RGBA':
                # Create white background and composite
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
        elif format_name == 'bmp':
            # BMP supports RGB/RGBA, but convert RGBA to RGB for compatibility
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
        elif format_name == 'webp':
            # WebP supports RGBA, so we can keep it as is
            pass
        else:
            # For other formats, convert to RGB if needed
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
        
        final_output = BytesIO()
        img.save(final_output, format=format_name.upper())
        result_bytes = final_output.getvalue()
        logger.debug(f"Successfully created {format_name.upper()} image, size: {len(result_bytes)} bytes")
        return result_bytes
    
    result_bytes = output.getvalue()
    logger.debug(f"Successfully created PNG image, size: {len(result_bytes)} bytes")
    return result_bytes


def get_image_with_status(image_data, image_url, referer_url, image_mime_type) -> tuple:
    """
    Get image with status check. Returns (image_data, flow_response).
    """
    logger.info(f"Processing image request - URL: {image_url}, MIME: {image_mime_type}, Referer: {referer_url}")
    logger.debug(f"Image data size: {len(image_data)} bytes")
    
    image_hash = hashlib.sha256(image_data).hexdigest()
    logger.debug(f"Image hash: {image_hash[:8]}...")
    
    status_info = get_image_status(image_hash)

    mime_type = None
    width = None
    height = None

    if status_info is None or status_info['width'] is None or status_info['height'] is None:
        # Get image dimensions
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            detected_format = img.format
            logger.debug(f"Image dimensions detected: {width}x{height}, format: {detected_format}")
        except Exception as e:
            width, height = None, None
            logger.warning(
                f"Failed to get image dimensions for hash {image_hash[:8]}... "
                f"(URL: {image_url}, MIME: {image_mime_type}, Error: {str(e)}). "
                f"Will use default size."
            )
            
    if status_info is None:
        logger.info(f"New image detected (hash: {image_hash[:8]}...), enqueueing for analysis")
        
        # If no status exists, enqueue for processing
        logger.info(f"Enqueueing image for analysis - Hash: {image_hash[:8]}..., URL: {image_url}")
        task_id = image_processing_queue.enqueue(
            image_content=image_data,
            image_details={
                'image_hash': image_hash, 
                'image_url': image_url,
                'mime_type': image_mime_type,
                'width': width,
                'height': height
            },
            image_mime_type=image_mime_type
        )
        logger.debug(f"Image enqueued with task ID: {task_id}")
        mark_pending(image_hash, image_url, image_mime_type, width, height)
        # Return checking image in original format and size
        if width and height:
            logger.info(f"Returning CHECKING image for new image (hash: {image_hash[:8]}...), size: {width}x{height}")
            return create_image_content(CHECKING_IMAGE, image_mime_type, (width, height)), None
        else:
            logger.warning(
                f"Image dimensions not available for hash {image_hash[:8]}... "
                f"(URL: {image_url}). Using default size for CHECKING image."
            )
            logger.info(f"Returning CHECKING image with default size for hash {image_hash[:8]}...")
            return create_image_content(CHECKING_IMAGE, image_mime_type), None
    
    status = status_info['status']
    stored_mime_type = status_info.get('mime_type') or image_mime_type
    stored_width = status_info.get('width')
    stored_height = status_info.get('height')
    
    logger.info(f"Image status found: {status} for hash {image_hash[:8]}... (stored size: {stored_width}x{stored_height}, MIME: {stored_mime_type})")

    if status == "blocked":
        logger.info(f"Returning BLOCKED image for hash {image_hash[:8]}...")
        # Return blocked image in original format and size
        if stored_width and stored_height:
            logger.debug(f"Using stored dimensions: {stored_width}x{stored_height}")
            return create_image_content(BLOCK_IMAGE, stored_mime_type, (stored_width, stored_height)), None
        else:
            logger.warning(
                f"Image dimensions not available for blocked image hash {image_hash[:8]}... "
                f"(URL: {image_url}). Using default size for BLOCKED image."
            )
            return create_image_content(BLOCK_IMAGE, stored_mime_type), None
    elif status == "allowed":
        logger.info(f"Image allowed - returning original image for hash {image_hash[:8]}...")
        return image_data, None
    elif status == "pending":
        logger.info(f"Image still pending analysis - returning CHECKING image for hash {image_hash[:8]}...")
        # Return checking image in original format and size
        if stored_width and stored_height:
            logger.debug(f"Using stored dimensions: {stored_width}x{stored_height}")
            return create_image_content(CHECKING_IMAGE, stored_mime_type, (stored_width, stored_height)), None
        else:
            logger.warning(
                f"Image dimensions not available for pending image hash {image_hash[:8]}... "
                f"(URL: {image_url}). Using default size for CHECKING image."
            )
            return create_image_content(CHECKING_IMAGE, stored_mime_type), None
    
    # Error case
    logger.warning(f"Unknown status '{status}' for hash {image_hash[:8]}..., returning ERROR image")
    if stored_width and stored_height:
        return create_image_content(ERROR_IMAGE, stored_mime_type, (stored_width, stored_height)), None
    logger.warning(
        f"Image dimensions not available for error case hash {image_hash[:8]}... "
        f"(URL: {image_url}). Using default size for ERROR image."
    )
    return create_image_content(ERROR_IMAGE, stored_mime_type), None
