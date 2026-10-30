#!/usr/bin/env python3
"""B站视频投稿：默认 --dry-run 只上传分片不提交，确认通过后再加 --commit 真的提交。

凭据默认读 ~/.bili-ai/credentials.json（可用 BILI_CRED 覆盖），该文件绝不入库。
bilibili_api 不在系统 PATH 里时用 PYTHONPATH 指过去，例如：
  PYTHONPATH=<repo>/../.tools/py2 python3 upload.py --video a.mp4 --title 标题 \
      --cover cover.png --tags 日常 --tid 122 --dry-run

分区 tid 常用: 122 生活-日常, 21 生活-其他, 138 搞笑, 181 影视-影视杂谈,
               17 知识-科技, 208 知识-财经商业, 27 动画-综合
"""
import argparse
import asyncio
import json
import os
import sys

from bilibili_api import video_uploader as VU, Credential

CRED_PATH = os.environ.get("BILI_CRED") or os.path.expanduser("~/.bili-ai/credentials.json")


def load_cred() -> Credential:
    if not os.path.exists(CRED_PATH):
        raise SystemExit(f"找不到凭据文件: {CRED_PATH}（用 BILI_CRED 指定路径）")
    c = json.load(open(CRED_PATH))
    return Credential(
        sessdata=c["sessdata"].strip(),
        bili_jct=c["bili_jct"].strip(),
        buvid3=c.get("buvid3", "").strip(),
    )


async def run(args) -> None:
    page = VU.VideoUploaderPage(path=args.video, title=args.title, description=args.desc or "")
    meta = VU.VideoMeta(
        title=args.title, tid=args.tid, cover=args.cover,
        tags=[t for t in args.tags.split(",") if t], desc=args.desc or "",
    )
    up = VU.VideoUploader(pages=[page], meta=meta, credential=load_cred())

    # 选线路：这一步通了说明 CDN 可达
    up.line = await VU._choose_line(None)
    print(f"[1/4] 线路 ok: os={up.line.get('os')} upcdn={up.line.get('upcdn')}")

    # 上传分片（预上传 + 分块），失败基本都卡在这里的风控
    data = await up._upload_page(page)
    print(f"[2/4] 分片上传 ok: filename={data.get('filename')} cid={data.get('cid')}")

    cover_url = await up._upload_cover()
    print(f"[3/4] 封面 ok: {cover_url[:80]}")

    if not args.commit:
        print("[4/4] 未加 --commit：到此为止，未提交稿件。")
        return

    videos = [{"title": page.title, "desc": page.description,
               "filename": data["filename"], "cid": data["cid"]}]
    result = await up._submit(videos, cover_url)
    print(f"[4/4] 已提交：{json.dumps(result, ensure_ascii=False)}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--tid", type=int, default=122)
    p.add_argument("--tags", default="")
    p.add_argument("--cover", required=True)
    p.add_argument("--desc", default="")
    p.add_argument("--commit", action="store_true", help="真正提交稿件；不加则只走到上传分片")
    args = p.parse_args()
    try:
        asyncio.run(run(args))
    except SystemExit:
        raise
    except Exception as e:
        msg = str(e)[:300]
        print(f"失败: {type(e).__name__}: {msg}", file=sys.stderr)
        if "406" in msg or "601" in msg:
            print("提示: 406/601 = B站风控「您上传视频过快」，需要先有稿件历史或过验证码；"
                  "不是网络或权限问题。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
