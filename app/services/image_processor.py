import io
import os
from collections.abc import Callable
from PIL import Image, ImageOps
import warnings
from app.core.storage import BUCKET, s3_client

ProgressCallback = Callable[[str, int, str], None]

MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


SUPPORTED_FORMATS = {
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
}

def transform_image(
    input_key: str,
    output_key: str,
    width: int,
    height: int,
    output_format: str,
    on_progress: ProgressCallback | None = None,
):
    output_format = output_format.lower()

    if output_format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported output format")

    def report(status: str, progress: int, message: str) -> None:
        if on_progress is not None:
            on_progress(status, progress, message)

    # Download source
    report("downloading", 10, "Downloading source image")
    response = s3_client.get_object(
        Bucket=BUCKET,
        Key=input_key,
    )

    try:
        image_bytes = response["Body"].read()
    finally:
        response["Body"].close()

    # Process image
    report("processing", 40, "Processing image")
    with warnings.catch_warnings():
        warnings.simplefilter(
            "error",
            Image.DecompressionBombWarning,
        )

        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()

            image = ImageOps.exif_transpose(image)

            # Preserve aspect ratio
            image.thumbnail(
                (width, height),
                Image.Resampling.LANCZOS,
            )

            if output_format == "jpeg":
                image = image.convert("RGB")
            elif output_format == "png":
                if image.mode not in ("RGB", "RGBA", "L", "LA"):
                    image = image.convert("RGBA")
            elif output_format == "webp":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
            
            output = io.BytesIO()

            image.save(
                output,
                format=SUPPORTED_FORMATS[output_format],
                quality=85,
                optimize=True
            )

            output.seek(0)
            output_bytes = output.getvalue()

    # upload result
    report("uploading", 80, "Uploading result")
    s3_client.put_object(
        Bucket=BUCKET,
        Key=output_key,
        Body=output_bytes,
        ContentType=f"image/{output_format}"
    )

    return {
        "output_key": output_key,
        "output_size": len(output_bytes)
    }
