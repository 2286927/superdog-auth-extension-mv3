#!/usr/bin/env python3
"""解析 CRX2 / CRX3 安装包：验算扩展 ID、导出内部文件。

用途：
  1. 拿到原厂 .crx 后，验算它的扩展 ID，与本项目 manifest 的 key 是否一致；
  2. 导出原始文件，便于对照本仓库改了什么。

用法：
  python extract-crx.py path/to/extension.crx                # 列出内容 + 打印 ID
  python extract-crx.py path/to/extension.crx --id-only      # 只打印 ID
  python extract-crx.py path/to/extension.crx -o out_dir     # 解压到 out_dir

仅依赖标准库。
"""

import argparse
import base64
import hashlib
import io
import os
import struct
import sys
import zipfile

CRX_MAGIC = b"Cr24"


def parse_crx(data):
    """返回 (crx_version, public_key_bytes, zip_bytes)。"""
    if data[:4] != CRX_MAGIC:
        raise ValueError("不是 CRX 文件：缺少 Cr24 魔数")

    version = struct.unpack("<I", data[4:8])[0]

    if version == 2:
        # CRX2: 魔数(4) + 版本(4) + 公钥长度(4) + 签名长度(4) + 公钥 + 签名 + zip
        pk_len, sig_len = struct.unpack("<II", data[8:16])
        pubkey = data[16:16 + pk_len]
        zip_off = 16 + pk_len + sig_len
    elif version == 3:
        # CRX3: 魔数(4) + 版本(4) + 头长度(4) + 头(protobuf) + zip
        header_len = struct.unpack("<I", data[8:12])[0]
        pubkey = _extract_pubkey_from_crx3_header(data[12:12 + header_len])
        zip_off = 12 + header_len
    else:
        raise ValueError("未知的 CRX 版本：%d" % version)

    zip_bytes = data[zip_off:]
    if zip_bytes[:4] != b"PK\x03\x04":
        raise ValueError("负载不是 zip：未在偏移 %d 找到 PK\\x03\\x04" % zip_off)

    return version, pubkey, zip_bytes


def _extract_pubkey_from_crx3_header(buf):
    """从 CRX3 的 protobuf 头里取第一个 crx_file 的 public_key。

    简化实现：不引 protobuf 依赖，按键号扫描。
    CrxFileHeader 结构大致为:
      2: sha256_with_rsa (repeated message) -> 其中 1: public_key
      10000: signed_header_data
    从头部找不到时返回空 bytes（不影响解压，只是无法验算 ID）。
    """
    try:
        i = 0
        while i < len(buf):
            key, i = _read_varint(buf, i)
            field, wire = key >> 3, key & 7
            if wire == 2:
                length, i = _read_varint(buf, i)
                payload = buf[i:i + length]
                i += length
                if field == 2:
                    # 进入 sha256_with_rsa 子消息，取 field 1
                    j = 0
                    while j < len(payload):
                        k2, j = _read_varint(payload, j)
                        f2, w2 = k2 >> 3, k2 & 7
                        if w2 == 2:
                            l2, j = _read_varint(payload, j)
                            v2 = payload[j:j + l2]
                            j += l2
                            if f2 == 1:
                                return v2
                        elif w2 == 0:
                            _, j = _read_varint(payload, j)
                        else:
                            return b""
            elif wire == 0:
                _, i = _read_varint(buf, i)
            else:
                return b""
    except (IndexError, ValueError):
        return b""
    return b""


def _read_varint(buf, i):
    result = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def extension_id(pubkey):
    """扩展 ID = sha256(DER 公钥) 前 16 字节，十六进制逐位映射到 a-p。"""
    digest = hashlib.sha256(pubkey).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def main():
    ap = argparse.ArgumentParser(description="解析 CRX2/CRX3，验算扩展 ID 并导出文件")
    ap.add_argument("crx", help="CRX 文件路径")
    ap.add_argument("-o", "--out", help="解压目标目录")
    ap.add_argument("--id-only", action="store_true", help="只输出扩展 ID")
    args = ap.parse_args()

    with open(args.crx, "rb") as f:
        data = f.read()

    version, pubkey, zip_bytes = parse_crx(data)
    eid = extension_id(pubkey) if pubkey else None

    if args.id_only:
        if not eid:
            print("无法从该 CRX 中提取公钥，无法验算 ID", file=sys.stderr)
            return 1
        print(eid)
        return 0

    print("文件      : %s" % args.crx)
    print("大小      : %d 字节" % len(data))
    print("CRX 版本  : %d" % version)
    print("公钥长度  : %d 字节" % len(pubkey))
    if eid:
        print("扩展 ID   : %s" % eid)
        print("公钥 b64  : %s" % base64.b64encode(pubkey).decode())
    else:
        print("扩展 ID   : (未解析出公钥)")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        print("\n内部文件：")
        for info in z.infolist():
            print("  %8d  %s" % (info.file_size, info.filename))
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            z.extractall(args.out)
            print("\n已解压到：%s" % os.path.abspath(args.out))

    return 0


if __name__ == "__main__":
    sys.exit(main())
