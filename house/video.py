# /// script
# dependencies = ["imageio-ffmpeg"]
# ///
"""Encode a clip for a house deck: H.264 mp4 sized for a slide, plus its poster.

    uv run house/video.py SRC OUT.mp4 [--width 1920] [--crf 26] [--fps 30]
        [--start S] [--duration S] [--speed X] [--poster-at S]

Writes OUT.mp4 (no audio, yuv420p, faststart) and OUT.jpg, the poster frame
the build requires beside every <video>. The build inlines both, so watch the
size it prints: aim for a few MB per clip.
"""
import argparse, os, subprocess, imageio_ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--width", type=int, default=1920)
ap.add_argument("--crf", type=int, default=26)
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--start", type=float, default=0)
ap.add_argument("--duration", type=float)
ap.add_argument("--speed", type=float, default=1.0, help="playback speed-up factor")
ap.add_argument("--poster-at", type=float, default=0.0, help="seconds into the output clip")
a = ap.parse_args()
ff = imageio_ffmpeg.get_ffmpeg_exe()

cut = ["-ss", str(a.start)] + (["-t", str(a.duration)] if a.duration else [])
vf = f"setpts=PTS/{a.speed},fps={a.fps},scale={a.width}:-2:flags=lanczos,format=yuv420p"
subprocess.run([ff, "-y", "-loglevel", "error", *cut, "-i", a.src, "-an", "-vf", vf,
                "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-profile:v", "high",
                "-movflags", "+faststart", a.out], check=True)
poster = os.path.splitext(a.out)[0] + ".jpg"
subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(a.poster_at), "-i", a.out,
                "-frames:v", "1", "-q:v", "3", poster], check=True)
print(f"{a.out}: {os.path.getsize(a.out) / 1e6:.1f} MB; poster {poster}")
