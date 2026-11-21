import os
import signal
import subprocess


class FFmpegTimeout(Exception):
    pass

class FFmpegFailed(Exception):
    pass

def run_ffmpeg(args: list[str], timeout: float) -> None:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True
    )

    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        raise FFmpegTimeout(f"FFmpeg process timed out after {timeout: .0f} seconds")
    
    if proc.returncode != 0:
        detail = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise FFmpegFailed(detail[-2000:] or f"ffmpeg exited {proc.returncode}")


def _kill_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try: 
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    proc.wait(timeout=5)
