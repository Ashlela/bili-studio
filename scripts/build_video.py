#!/usr/bin/env python3
"""成片流水线：文案 -> TTS -> 计时 -> ASS 字幕 -> ffmpeg 合成 1080p。

路径全部可用环境变量覆盖，方便换机器：
  FFMPEG_BIN        ffmpeg 可执行文件（默认找 <repo>/../.tools/ffmpeg/...，找不到则用 PATH 里的 ffmpeg）
  FONT_FILE         中文字体文件（默认 <repo>/../.tools/fonts/NotoSansSC.ttf）
  FONT_DIR          字体目录，供 libass 的 fontsdir 用（默认取 FONT_FILE 所在目录）
  TTS_PYTHONPATH    edge-tts 的安装位置（默认 <repo>/../.tools/py）
  TTS_VOICE         配音音色（默认 zh-CN-XiaoxiaoNeural）

用法:
  python3 build_video.py                          # 用内置的三行文案出一版
  python3 build_video.py --lines lines.json --name ep01 --out-dir ./out

lines.json 形如: [["标题", null], ["正文一行", null]] 或 [{"text": "正文", "sub": null}]
每个元素的第二项保留给「独立字幕文本」，暂时不用，传 null 即可。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(REPO), ".tools")


def _pick(env, *candidates):
    v = os.environ.get(env)
    if v:
        return v
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[-1] if candidates else ""


FF = _pick("FFMPEG_BIN", os.path.join(TOOLS, "ffmpeg/node_modules/ffmpeg-static/ffmpeg"),
           "ffmpeg")
FONT = os.environ.get("FONT_FILE") or os.path.join(TOOLS, "fonts/NotoSansSC.ttf")
FONTDIR = os.environ.get("FONT_DIR") or os.path.dirname(FONT)
TTS_PATH = os.environ.get("TTS_PYTHONPATH") or os.path.join(TOOLS, "py")
VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
GAP = 0.45
W, H, FPS = 1920, 1080, 30

DEFAULT_LINES = [
    ("养鱼日报", None),
    ("今天，这个号自己刷了 62 条视频，写了 2 条评论。", None),
    ("没有人替它决定看什么。它自己选。", None),
]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def dur(path):
    out = subprocess.run([FF, "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    for ln in out.splitlines():
        if "Duration:" in ln:
            h, m, s = ln.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError("拿不到时长: " + path)


def tts(idx, text, out_dir):
    out = os.path.join(out_dir, f"v{idx}.mp3")
    env = dict(os.environ)
    if os.path.isdir(TTS_PATH):
        env["PYTHONPATH"] = os.pathsep.join(
            [TTS_PATH] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    run([sys.executable, "-m", "edge_tts", "--text", text, "--voice", VOICE,
         "--write-media", out], env=env)
    return out


def ass_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def normalize(raw):
    lines = []
    for item in raw:
        if isinstance(item, dict):
            lines.append((item["text"], item.get("sub")))
        else:
            lines.append((item[0], item[1] if len(item) > 1 else None))
    return lines


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--lines", help="文案 JSON 文件，省略则用内置示例")
    p.add_argument("--out-dir", default="out")
    p.add_argument("--name", default="demo", help="输出文件名（不含扩展名）")
    args = p.parse_args(argv)

    lines = DEFAULT_LINES
    if args.lines:
        with open(args.lines, encoding="utf-8") as f:
            lines = normalize(json.load(f))

    os.makedirs(args.out_dir, exist_ok=True)

    clips, durs = [], []
    for i, (text, _) in enumerate(lines):
        path = tts(i, text, args.out_dir)
        clips.append(path)
        durs.append(dur(path))

    parts = [f"[{i}:a]aresample=44100,apad=pad_dur={GAP}[a{i}]" for i in range(len(clips))]
    filt = ";".join(parts)
    labels = "".join(f"[a{i}]" for i in range(len(clips)))
    filt += f";{labels}concat=n={len(clips)}:v=0:a=1[aout]"
    audio = os.path.join(args.out_dir, "voice.m4a")
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y"]
    for path in clips:
        cmd += ["-i", path]
    cmd += ["-filter_complex", filt, "-map", "[aout]", "-c:a", "aac", "-b:a", "128k", audio]
    run(cmd)

    total = min(sum(durs) + GAP * len(clips), dur(audio))

    events, t = [], 0.0
    for i, (text, _) in enumerate(lines):
        start = t
        end = min(t + durs[i] + GAP * 0.6, total)
        if i == 0:
            events.append((start, end, r"{\fs92\b1}养鱼日报{\fs64} · 第 1 期", "center"))
        else:
            events.append((start, end, r"{\fs44}" + text, "bottom"))
        t += durs[i] + GAP

    ass = os.path.join(args.out_dir, "sub.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: C,Noto Sans SC,64,&H00FFFFFF,&H000000FF,&H000A0C10,&H96000000,0,0,0,0,100,100,0,0,1,2,1,5,80,80,80,1
Style: B,Noto Sans SC,44,&H00E6E6E6,&H000000FF,&H000A0C10,&H96000000,0,0,0,0,100,100,1,0,1,2,1,2,120,120,96,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
        for start, end, text, pos in events:
            style = "C" if pos == "center" else "B"
            f.write(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}\n")

    out = os.path.join(args.out_dir, f"{args.name}.mp4")
    vf = ",".join([
        f"ass={ass}:fontsdir={FONTDIR}",
        "fade=t=in:st=0:d=0.6",
        f"fade=t=out:st={max(total - 0.7, 0):.2f}:d=0.7",
        "format=yuv420p",
    ])
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=0x0E1116:size={W}x{H}:rate={FPS}:duration={total:.2f}",
           "-i", audio,
           "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-shortest", "-movflags", "+faststart", out]
    run(cmd)
    print(json.dumps({"total": round(total, 2), "durs": [round(d, 2) for d in durs],
                      "out": out, "size": os.path.getsize(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
