import logging
import os
from datetime import datetime


class Logger:
    """ログ管理ユーティリティ"""

    def __init__(self, log_dir, log_name, level=logging.INFO):
        """
        ロガー初期化

        Args:
            log_dir: ログディレクトリパス
            log_name: ログファイル名（拡張子なし）
            level: ログレベル
        """
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"{log_name}.log")

        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(level)

        # ファイルハンドラ
        fh = logging.FileHandler(self.log_path, encoding="utf-8")
        fh.setLevel(level)

        # ログフォーマット
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(formatter)

        self.logger.addHandler(fh)

    def info(self, message):
        """情報ログ"""
        self.logger.info(message)

    def warning(self, message):
        """警告ログ"""
        self.logger.warning(message)

    def error(self, message):
        """エラーログ"""
        self.logger.error(message)

    def debug(self, message):
        """デバッグログ"""
        self.logger.debug(message)
