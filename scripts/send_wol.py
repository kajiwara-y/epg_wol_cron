#!/usr/bin/env python3
"""
WOL（Wake-on-LAN）送信ユーティリティ

指定されたMACアドレスへWOLパケットを送信します
"""

import socket
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def send_wol(mac_address, broadcast_address="255.255.255.255", port=9):
    """
    WOLパケットを送信

    Args:
        mac_address (str): 対象デバイスのMACアドレス (XX:XX:XX:XX:XX:XX形式)
        broadcast_address (str): ブロードキャストアドレス
        port (int): ポート番号

    Returns:
        bool: 送信成功ならTrue

    Raises:
        ValueError: MACアドレス形式が無効の場合
    """
    # MACアドレス形式の検証と正規化
    mac_bytes = _parse_mac_address(mac_address)

    # WOLパケット構築
    # ヘッダ: 0xFFが6回繰り返される
    header = bytes([0xFF] * 6)
    # ペイロード: MACアドレスが16回繰り返される
    payload = mac_bytes * 16
    wol_packet = header + payload

    try:
        # ソケット作成（UDP）
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # パケット送信
        sock.sendto(wol_packet, (broadcast_address, port))
        sock.close()

        return True
    except Exception as e:
        print(f"WOL送信エラー: {e}", file=sys.stderr)
        return False


def _parse_mac_address(mac_address):
    """
    MACアドレス文字列をバイト列に変換

    Args:
        mac_address (str): MACアドレス文字列 (XX:XX:XX:XX:XX:XX or XXXXXXXXXXXX形式)

    Returns:
        bytes: MACアドレスのバイト列

    Raises:
        ValueError: MACアドレス形式が無効の場合
    """
    # コロンを削除
    mac = mac_address.replace(":", "").replace("-", "")

    # 形式の検証
    if len(mac) != 12 or not all(c in "0123456789abcdefABCDEF" for c in mac):
        raise ValueError(f"無効なMACアドレス形式: {mac_address}")

    # 16進数文字列をバイト列に変換
    return bytes.fromhex(mac)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用法: send_wol.py <MAC_ADDRESS> [BROADCAST_ADDRESS] [PORT]")
        print("  例: send_wol.py XX:XX:XX:XX:XX:XX")
        sys.exit(1)

    mac_addr = sys.argv[1]
    broadcast_addr = sys.argv[2] if len(sys.argv) > 2 else "255.255.255.255"
    wol_port = int(sys.argv[3]) if len(sys.argv) > 3 else 9

    success = send_wol(mac_addr, broadcast_addr, wol_port)
    sys.exit(0 if success else 1)
