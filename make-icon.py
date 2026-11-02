#!/usr/bin/env python3
"""生成 128×128 扩展图标，并把 icons 字段写回 manifest.json（可选步骤）。

为什么要这个脚本：
    原扩展的图标是原厂美术资源，本项目不再分发。Chromium 在 manifest 未声明
    icons 时不会报错（显示默认拼图图标），但如果你希望扩展列表里有个正经图标，
    跑这个脚本即可——图形由本脚本自行绘制，纯标准库，无第三方依赖。

用法：
    python make-icon.py                     # 生成 icon-128.png 并更新 manifest
    python make-icon.py --no-manifest       # 只生成图片，不改 manifest

幂等：重复执行结果一致。
"""

import argparse
import json
import os
import struct
import zlib

SIZE = 128
SS = 4  # 超采样倍数，抗锯齿

# 配色（深色底 + 浅色主体，无渐变）
ICON_BG = (15, 23, 42)
ICON_FG = (248, 250, 252)

EXT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- 几何判定（坐标均在 128 空间内） ----------

def in_rounded_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_rect(x, y, x0, y0, x1, y1):
    return x0 <= x <= x1 and y0 <= y <= y1


def in_ring(x, y, cx, cy, r_out, r_in):
    d2 = (x - cx) ** 2 + (y - cy) ** 2
    return r_in * r_in <= d2 <= r_out * r_out


def is_foreground(x, y):
    """钥匙图形：圆环 + 键杆 + 两个齿。"""
    if in_ring(x, y, 44, 50, 22, 12):
        return True
    if in_rect(x, y, 60, 44, 104, 56):
        return True
    if in_rect(x, y, 84, 56, 94, 70):
        return True
    if in_rect(x, y, 68, 56, 78, 66):
        return True
    return False


def render():
    """返回逐行 RGBA 字节。"""
    hi = SIZE * SS
    acc = [[[0, 0, 0, 0] for _ in range(SIZE)] for _ in range(SIZE)]

    for py in range(hi):
        y = (py + 0.5) / SS
        for px in range(hi):
            x = (px + 0.5) / SS
            if not in_rounded_rect(x, y, 0.5, 0.5, SIZE - 0.5, SIZE - 0.5, 28):
                continue
            r, g, b = ICON_FG if is_foreground(x, y) else ICON_BG
            cell = acc[py // SS][px // SS]
            cell[0] += r
            cell[1] += g
            cell[2] += b
            cell[3] += 255

    rows = []
    total = SS * SS
    for row in acc:
        out = bytearray()
        for cell in row:
            a = cell[3] // total
            if a == 0:
                out += b"\x00\x00\x00\x00"
            else:
                n = cell[3]
                out += bytes((cell[0] * 255 // n, cell[1] * 255 // n, cell[2] * 255 // n, a))
        rows.append(out)
    return rows, hi


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def patch_manifest():
    mpath = os.path.join(EXT_DIR, "manifest.json")
    if not os.path.exists(mpath):
        print("跳过：未找到 %s" % mpath)
        return
    with open(mpath, encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest.get("icons") == {"128": "icon-128.png"}:
        print("manifest 已包含 icons 字段，未改动")
        return

    manifest["icons"] = {"128": "icon-128.png"}
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("已写入 manifest.json 的 icons 字段")


def main():
    ap = argparse.ArgumentParser(description="生成 128x128 扩展图标")
    ap.add_argument("--no-manifest", action="store_true", help="只生成图片，不修改 manifest.json")
    args = ap.parse_args()

    if not os.path.isdir(EXT_DIR):
        print("错误：未找到 manifest.json（请在本仓库根目录下执行）")
        return 1

    rows, _ = render()
    out = os.path.join(EXT_DIR, "icon-128.png")
    write_png(out, SIZE, rows)
    print("已生成 %s（%d 字节）" % (out, os.path.getsize(out)))

    if not args.no_manifest:
        patch_manifest()

    print("完成。回到扩展管理页点一次「重新加载」即可看到图标。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
