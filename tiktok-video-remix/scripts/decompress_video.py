#!/usr/bin/env python3
"""
视频拆解预处理器：抽帧 + 音轨转写。
当视觉模型无法直接读视频时，把视频转成"关键帧图片 + 带时间戳口播文本"，
供 Agent 逐帧读图 + 按台词定位说服目的。

依赖（按需安装）：
    pip install imageio-ffmpeg        # 提供 ffmpeg 可执行文件
    pip install faster-whisper         # 音轨转写（首次会下载模型）

用法：
    python3 decompress_video.py <视频路径> [--out 输出目录] [--fps 每N秒一帧] [--skip-audio]

产出：
    <out>/frames/f_001.jpg ...        关键帧
    <out>/transcript.txt              带时间戳的口播文本
    <out>/meta.json                   视频元信息
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_ffmpeg():
    """优先用系统 ffmpeg，否则用 imageio-ffmpeg 自带的。"""
    from shutil import which
    exe = which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit(
            "[错误] 未找到 ffmpeg。请安装其一：\n"
            "  - 系统安装: brew install ffmpeg\n"
            "  - 或 Python: pip install imageio-ffmpeg"
        )


def probe_duration(ffmpeg, video):
    """用 ffprobe 或 ffmpeg 获取时长（秒）。"""
    from shutil import which
    ffprobe = which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.check_output(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                text=True,
            )
            return float(out.strip())
        except Exception:
            pass
    return None


def extract_frames(ffmpeg, video, frames_dir, every_n_sec):
    frames_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(frames_dir / "f_%03d.jpg")
    cmd = [
        ffmpeg, "-y", "-i", str(video),
        "-vf", f"fps=1/{every_n_sec},scale=720:-2",
        "-q:v", "3", pattern,
    ]
    print("[信息] 抽帧中...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frames = sorted(frames_dir.glob("f_*.jpg"))
    print(f"[完成] 抽取 {len(frames)} 帧 -> {frames_dir}")
    return len(frames)


def transcribe(video, out_file, language):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[警告] 未安装 faster-whisper，跳过音轨转写。"
              "安装: pip install faster-whisper")
        return False
    print("[信息] 音轨转写中（首次会下载模型，较慢）...")
    model = WhisperModel("small", compute_type="int8")
    segments, info = model.transcribe(str(video), language=language)
    lines = []
    for seg in segments:
        start = int(seg.start)
        end = int(seg.end)
        lines.append(f"[{start:03d}s-{end:03d}s] {seg.text.strip()}")
    out_file.write_text(
        f"# 音轨转写\n语言: {info.language} | 时长: {int(info.duration)}s\n\n"
        + "\n".join(lines),
        encoding="utf-8",
    )
    print(f"[完成] 转写 {len(lines)} 段 -> {out_file}")
    return True


def main():
    ap = argparse.ArgumentParser(description="视频拆解预处理：抽帧 + 转写")
    ap.add_argument("video", help="视频文件路径")
    ap.add_argument("--out", default=None, help="输出目录，默认与视频同名的目录")
    ap.add_argument("--fps", type=int, default=3, help="每 N 秒抽一帧，默认 3")
    ap.add_argument("--skip-audio", action="store_true", help="跳过音轨转写")
    ap.add_argument("--lang", default=None, help="转写语言，如 en / zh，默认自动检测")
    args = ap.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        sys.exit(f"[错误] 视频不存在: {video}")

    out = Path(args.out).expanduser().resolve() if args.out else video.with_suffix("")
    out.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg()
    duration = probe_duration(ffmpeg, video)

    n_frames = extract_frames(ffmpeg, video, out / "frames", args.fps)

    transcribed = False
    if not args.skip_audio:
        transcribed = transcribe(video, out / "transcript.txt", args.lang)

    meta = {
        "video": str(video),
        "duration_sec": duration,
        "frame_interval_sec": args.fps,
        "frame_count": n_frames,
        "transcript_available": transcribed,
    }
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n[完成] 全部产出:")
    print(f"  关键帧: {out / 'frames'}")
    print(f"  转写:   {out / 'transcript.txt'}" if transcribed else "  转写:   未生成")
    print(f"  元信息: {out / 'meta.json'}")
    print("\n下一步：逐帧读图识别画面/节奏/CTA，配合 transcript.txt 定位说服目的。")


if __name__ == "__main__":
    main()
