#!/usr/bin/env python3
"""
予約情報キャッシュ更新スクリプト

epg station REST APIから予約情報を取得し、
キャッシュをJSON形式で保存します

実行: cron定期実行（PCが起動している時のみ成功）
"""

import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from utils.logger import Logger


class CacheUpdater:
    """キャッシュ更新クラス"""

    def __init__(self, config_path, cache_path, log_dir, debug=False):
        """
        初期化

        Args:
            config_path: 設定ファイルパス
            cache_path: キャッシュファイルパス
            log_dir: ログディレクトリ
            debug: デバッグモード（Trueの場合、コンソールにも出力）
        """
        self.config = self._load_config(config_path)
        self.cache_path = cache_path
        self.logger = Logger(log_dir, "update", level="INFO", debug=debug)

        if debug:
            self.logger.info("デバッグモード有効: コンソール出力を表示します")

    def _load_config(self, config_path):
        """設定ファイルを読み込み"""
        print(f"[起動] 設定ファイル読込開始: {config_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"[起動] ✓ 設定ファイル読込成功")
            return config
        except FileNotFoundError:
            print(f"[起動] ✗ 設定ファイルが見つかりません: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"[起動] ✗ 設定ファイルのJSON形式が無効です: {config_path}")
            sys.exit(1)

    def update(self):
        """
        キャッシュを更新

        Returns:
            bool: 更新成功ならTrue
        """
        try:
            self.logger.info("キャッシュ更新処理開始")

            # EPG Station APIから予約情報を取得
            self.logger.info("EPG Station APIから予約情報を取得中...")
            reserves = self._fetch_reserves()
            if reserves is None:
                self.logger.error("予約情報取得失敗")
                return False

            self.logger.info(f"予約情報取得成功: {len(reserves)}件")

            # キャッシュデータを構築
            now = datetime.now().isoformat()
            cache_data = {
                "last_updated": now,
                "reserves": reserves
            }
            self.logger.info(f"キャッシュデータ構築完了（更新時刻: {now}）")

            # キャッシュを保存
            cache_dir = os.path.dirname(self.cache_path)
            os.makedirs(cache_dir, exist_ok=True)
            self.logger.info(f"キャッシュファイル保存開始: {self.cache_path}")

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"キャッシュ更新成功: {len(reserves)}件の予約を保存")
            return True

        except Exception as e:
            self.logger.error(f"キャッシュ更新中にエラー: {e}")
            return False

    def _fetch_reserves(self):
        """
        EPG Station APIから予約情報を取得

        Returns:
            list: 予約情報リスト、失敗の場合はNone
        """
        try:
            api_url = self.config["epgstation"]["api_url"]
            timeout = self.config["epgstation"]["timeout"]

            url = f"{api_url}/reserves"
            self.logger.info(f"API呼び出し: {url} (タイムアウト: {timeout}秒)")

            response = requests.get(url, timeout=timeout)
            self.logger.info(f"API応答ステータス: {response.status_code}")

            response.raise_for_status()

            # APIレスポンスが配列の場合、そのまま返す
            # オブジェクトの場合、中身の配列を抽出
            data = response.json()
            self.logger.info(f"API応答型: {type(data).__name__}")

            if isinstance(data, list):
                self.logger.info(f"APIレスポンス形式: 配列（{len(data)}件）")
                return data
            elif isinstance(data, dict) and "reserves" in data:
                reserves = data["reserves"]
                self.logger.info(f"APIレスポンス形式: オブジェクト内reserves（{len(reserves)}件）")
                return reserves
            else:
                # 期待しない形式のレスポンス
                self.logger.warning(f"予期しないAPI応答形式: {type(data)}")
                return data if isinstance(data, list) else []

        except requests.exceptions.Timeout:
            self.logger.error("API取得タイムアウト")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API取得エラー: {e}")
            return None
        except json.JSONDecodeError:
            self.logger.error("API応答のJSON解析失敗")
            return None


def main():
    """メイン処理"""
    # デバッグモード判定（--debug フラグで有効化）
    debug_mode = "--debug" in sys.argv

    if debug_mode:
        print("[起動] デバッグモード: コンソール出力が有効です")

    # パスの設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    config_path = os.path.join(project_dir, "config", "config.json")
    cache_path = os.path.join(project_dir, "cache", "reserves.json")
    log_dir = os.path.join(project_dir, "logs")

    if debug_mode:
        print(f"[起動] スクリプトディレクトリ: {script_dir}")
        print(f"[起動] プロジェクトディレクトリ: {project_dir}")
        print(f"[起動] 設定ファイル: {config_path}")
        print(f"[起動] キャッシュファイル: {cache_path}")
        print(f"[起動] ログディレクトリ: {log_dir}")

    # キャッシュ更新実行
    updater = CacheUpdater(config_path, cache_path, log_dir, debug=debug_mode)
    success = updater.update()

    if debug_mode:
        result = "成功" if success else "失敗"
        print(f"[終了] キャッシュ更新: {result}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
