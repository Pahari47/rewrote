
import os
import tempfile
from app.core.storage import BUCKET, s3_client
from app.services.ffmpeg_runner import run_ffmpeg
from app.services.image_processor import ProgressCallback


VIDEO_FORMATS = {"mp4", "webm"}
AUDIO_FORMATS = {"mp3", "aac", "wav"}

CONTENT_TYPES = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mp3": "audio/mpeg",
    "aac": "audio/aac",
    "wav": "audio/wav",
}

def transcode_media(
    input_key: str,
    output_key: str,
    output_format: str,
    width: int,
    height: int,
    timeout: float,
    on_progress: ProgressCallback | None = None,
):
    output_format = output_format.lower()
    if output_format not in CONTENT_TYPES:
        raise ValueError(f"Unsupported output format: {output_format}")

    def report(status: str, progress: int, message: str) -> None:
        if on_progress is not None:
            on_progress(status, progress, message)
    
    with tempfile.TemporaryDirectory(prefix="av-") as tmp:
        input_path = os.path.join(tmp, "input")
        output_path = os.path.join(tmp, f"output.{output_format}")

        report("downloading", 10, "Download source media")
        s3_client.download_file(BUCKET, input_key, input_path)

        report("processing", 40, "transcoding with ffmpeg")
        run_ffmpeg(
            _ffmpeg_args(input_path, output_path, output_format, width, height),
            timeout,
        )

        output_size = os.path.getsize(output_path)
        report("uploading", 80, "Upload transcoded media")
        s3_client.upload_file(
            output_path,
            BUCKET,
            output_key,
            ExtraArgs={"ContentType": CONTENT_TYPES[output_format]}
        )
    
    return {"output_key": output_key, "output_size": output_size}

def _ffmpeg_args(input_path, output_path, output_format, width, height) -> list[str]:
    cmd = [
        os.getenv("FFMPEG_BIN", "ffmpeg"),
        "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_path,
    ]

    if output_format in VIDEO_FORMATS:
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
        if width > 0 and height > 0:
            cmd += ["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"]
        if output_format == "mp4":
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart"]
        else:
            cmd += ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "1M", "-c:a", "libopus"]

    elif output_format in AUDIO_FORMATS:
        cmd += ["-vn", "-map", "0:a:0"]
        if output_format == "mp3":
            cmd += ["-c:a", "libmp3lame"]
        elif output_format == "aac":
            cmd += ["-c:a", "aac"]
        else:
            cmd += ["-c:a", "pcm_s16le"]

    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    cmd.append(output_path)
    return cmd