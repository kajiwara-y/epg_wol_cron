import subprocess
import socket
import platform


class PCMonitor:
    """PC状態監視ユーティリティ"""

    def __init__(self, ip_address, timeout=3):
        """
        PC監視初期化

        Args:
            ip_address: PCのIPアドレス
            timeout: タイムアウト（秒）
        """
        self.ip_address = ip_address
        self.timeout = timeout

    def is_pc_alive(self, method="ping"):
        """
        PCが起動しているか確認

        Args:
            method: 確認方法 ("ping" or "port")

        Returns:
            bool: PC起動中ならTrue
        """
        if method == "ping":
            return self._check_ping()
        elif method == "port":
            return self._check_port()
        else:
            return False

    def _check_ping(self):
        """pingコマンドでPC起動確認"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", str(self.timeout * 1000), self.ip_address],
                    capture_output=True,
                    timeout=self.timeout + 1
                )
            else:  # Linux, macOS
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", str(self.timeout * 1000), self.ip_address],
                    capture_output=True,
                    timeout=self.timeout + 1
                )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def _check_port(self, port=8888):
        """ポート接続でPC起動確認"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.ip_address, port))
            sock.close()
            return result == 0
        except Exception:
            return False
