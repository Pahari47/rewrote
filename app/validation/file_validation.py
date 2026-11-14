from dataclasses import dataclass

@dataclass
class DetectedFile:
    extension: str
    content_type: str


SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
    (b"%PDF-", "pdf", "application/pdf"),
    (b"ID3", "mp3", "audio/mpeg"),
    (b"OggS", "ogg", "audio/ogg"),
    (b"fLaC", "flac", "audio/flac"),
]


def detect_file_type(data: bytes) -> DetectedFile | None:
    if not data:
        return None

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return DetectedFile("webp", "image/webp")

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return DetectedFile("wav", "audio/wav")

    if len(data) >= 8 and data[4:8] == b"ftyp":
        return DetectedFile("mp4", "video/mp4")

    for signature, extension, mime_type in SIGNATURES:
        if data.startswith(signature):
            return DetectedFile(extension, mime_type)

    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return DetectedFile("mp3", "audio/mpeg")

    return None
