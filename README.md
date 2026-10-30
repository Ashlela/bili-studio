# bili-studio

养鱼号（B 站）的视频流水线与本地工具。**私有仓库**：里面是干活用的脚本，不含账号凭据、不含素材。

从一条文案到一条能投稿的 1080p 成片，中间要做的事都在这里：配音、计时、中文字幕、合成、投稿。

## 现在有什么

| 脚本 | 干什么 | 状态 |
|---|---|---|
| `scripts/build_video.py` | 文案 → edge-tts 配音 → 每句计时 → ASS 字幕 → ffmpeg 合成 1080p | 本机实测通过（12 秒片，合成 ~8 秒） |
| `scripts/upload.py` | 预上传 + 分片 + 封面 + 提交稿件（默认只走到分片，不加 `--commit` 不会提交） | 逻辑已验证；实际投稿卡在账号实名 |

## 目录

```
bili-studio/
├── scripts/
│   ├── build_video.py     # 成片流水线
│   ├── upload.py          # B站投稿
│   └── requirements.txt
├── examples/
│   └── ep01.json          # 文案输入示例
└── .gitignore             # 凭据、产物、依赖全在里面
```

## 依赖

- **ffmpeg**：需要带 `libx264` 和 `libass`（烧字幕靠 libass，不是 drawtext）。本机在 `<repo>/../.tools/ffmpeg/node_modules/ffmpeg-static/ffmpeg`，7.0.2 版本齐全。换机器就用系统包，或 `FFMPEG_BIN` 指过去。
- **中文字体**：libass 需要一个中文字体文件，本机是 `NotoSansSC.ttf`。字体文件本身不入库（二进制 + 授权问题），README 里说清怎么放回来就行。
- **Python 3**（本机 3.13.5），两个包：

```bash
pip install --target ../.tools/py  -r scripts/requirements.txt   # 或者分别装
# edge-tts 和 bilibili_api 都在这台机器上是 --target 装的，
# 所以跑之前要把对应目录塞进 PYTHONPATH（见下面用法）
```

## 跑一遍

```bash
# 1) 出片（内置三行示例文案，产物落在 out/）
python3 scripts/build_video.py --out-dir out --name demo

# 2) 用自己的文案
python3 scripts/build_video.py --lines examples/ep01.json --out-dir out --name ep01

# 3) 投稿：先不加 --commit，只验证线路/分片/封面三步通不通
PYTHONPATH=../.tools/py2 python3 scripts/upload.py \
  --video out/ep01.mp4 --title "养鱼日报 第1期" --tid 122 --tags 日常,AI \
  --cover out/cover.png

# 4) 三步都 ok，再加 --commit 真提交
```

所有路径都能用环境变量覆盖，换机器不用改代码：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FFMPEG_BIN` | `<repo>/../.tools/ffmpeg/.../ffmpeg`，找不到则用 PATH | ffmpeg 可执行文件 |
| `FONT_FILE` | `<repo>/../.tools/fonts/NotoSansSC.ttf` | 中文字体 |
| `FONT_DIR` | `FONT_FILE` 所在目录 | 给 libass 的 `fontsdir` |
| `TTS_PYTHONPATH` | `<repo>/../.tools/py` | edge-tts 安装位置 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | 音色 |
| `BILI_CRED` | `~/.bili-ai/credentials.json` | 投稿凭据路径 |

## 凭据

投稿需要 `sessdata` / `bili_jct` / `buvid3`，放在仓库**外面**的 JSON 里：

```json
{"sessdata": "...", "bili_jct": "...", "buvid3": "..."}
```

`.gitignore` 已经从第一行起就挡住了 `credentials.json`、`.bili-ai/`、`.env`。三条铁律：

1. **先有 `.gitignore`，再 `git add`**，顺序反了就会把凭据写进历史，删了也还在。
2. 提交前扫一眼 `git status` 和 `git diff --cached --name-only`。
3. 真要泄了，先改密码/B 站退出所有设备，再考虑重写历史——不要只 `git rm`。

`sessdata` 等于登录态，拿到它就能操作账号，和密码同级。

## 什么不进仓库

凭据、视频/音频/字幕/封面（都可再生）、`node_modules`、`ffmpeg` 与字体二进制、抓取下来的 `play.json`/`view.json`/`opus.html`。

仓库里只放：**代码 + 文档 + 文案示例**。

## 已知坑

- **投稿风控 406/601**：提示「您上传视频过快」。不是网络也不是权限问题，是新号没投过稿、缺历史。实名之后先当普通用户养几天再说。
- **实名**：一个身份证只能认一个号，视频投稿必须实名。这条卡在账号层面，不是代码问题。
- **字幕字体**：`ass` 滤镜必须带 `fontsdir=`，否则中文全变方块；`Style` 里的字体名要和字体文件的实际 family 名对上（`Noto Sans SC`）。
- **`upload.py` 默认不提交**：默认只到「上传分片 + 封面」为止，加 `--commit` 才真投稿。这是故意的。

## 以后想加

- [ ] 竖屏 1080×1920 版本（同样的流水线，改 `W/H` 和字幕位置）
- [ ] 一张图 + 一句字幕的卡点模板（比纯色背景好看）
- [ ] 把 `out/` 里的产物自动推到 media-viewer 预览
