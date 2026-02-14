#!/usr/bin/env python3
"""
キャッシュ確認・WOL送信スクリプト

保存された予約情報キャッシュから予約をチェックし、
条件に合致した場合WOLパケットを送信します

実行: cron定期実行（常時実行）
タイミング: 25-30分前と0-5分前に検出したら送信
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from utils.logger import Logger
from utils.pc_monitor import PCMonitor


class WOLChecker:
    """WOL送信判定・実行クラス"""

    def __init__(self, config_path, cache_path, log_dir):
        """
        初期化

        Args:
            config_path: 設定ファイルパス
            cache_path: キャッシュファイルパス
            log_dir: ログディレクトリ
        """
        self.config = self._load_config(config_path)
        self.cache_path = cache_path
        self.logger = Logger(log_dir, "wol", level="INFO")
        self.pc_monitor = PCMonitor(
            self.config["desktop_pc"]["ip_address"],
            self.config["monitoring"]["pc_check_timeout"]
        )

    def _load_config(self, config_path):
        """設定ファイルを読み込み"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"設定ファイルが見つかりません: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"設定ファイルのJSON形式が無効です: {config_path}")
            sys.exit(1)

    def check_and_send(self):
        """
        予約をチェックしてWOLを送信

        Returns:
            bool: 処理成功ならTrue
        """
        try:
            # PCが起動している場合はスキップ
            if self.pc_monitor.is_pc_alive(self.config["monitoring"]["pc_check_method"]):
                self.logger.info("PCが起動中のため、WOL送信をスキップ")
                return True

            # キャッシュから予約情報を読み込み
            cache_data = self._load_cache()
            if not cache_data:
                self.logger.warning("キャッシュが見つかりません")
                return False

            # キャッシュの鮮度をチェック
            if not self._check_cache_freshness(cache_data):
                self.logger.warning("キャッシュが古すぎます")
                return False

            # 予約情報から条件に合致するものを検索
            reserve_to_send = self._find_reserve_to_send(cache_data["reserves"])

            if reserve_to_send:
                self.logger.info(f"予約検出: {reserve_to_send['program_name']}")
                return self._send_wol(cache_data)
            else:
                self.logger.debug("送信対象の予約なし")
                return True

        except Exception as e:
            self.logger.error(f"WOL送信チェック中にエラー: {e}")
            return False

    def _load_cache(self):
        """
        キャッシュを読み込み

        Returns:
            dict: キャッシュデータ、読み込み失敗の場合はNone
        """
        try:
            if not os.path.exists(self.cache_path):
                return None

            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.error("キャッシュのJSON解析失敗")
            return None

    def _check_cache_freshness(self, cache_data):
        """
        キャッシュの鮮度をチェック

        Args:
            cache_data: キャッシュデータ

        Returns:
            bool: 十分に新鮮ならTrue
        """
        max_age = self.config["cache"]["max_age_hours"]
        last_updated = datetime.fromisoformat(cache_data["last_updated"])
        age = datetime.now() - last_updated

        if age > timedelta(hours=max_age):
            self.logger.warning(
                f"キャッシュが古い: {age}時間前に更新 (最大: {max_age}時間)"
            )
            return False

        return True

    def _find_reserve_to_send(self, reserves):
        """
        WOL送信対象の予約を検索

        条件:
        - 30分前～25分前のタイミング、または
        - 5分前～0分前のタイミング
        - まだWOL送信済みフラグが立っていない

        Args:
            reserves: 予約情報リスト

        Returns:
            dict: 送信対象の予約、ない場合はNone
        """
        now = datetime.now()
        first_minutes = self.config["wol_timing"]["first_minutes"]
        second_minutes = self.config["wol_timing"]["second_minutes"]

        for reserve in reserves:
            try:
                start_time = datetime.fromisoformat(reserve["start_time"])
                time_until_start = (start_time - now).total_seconds() / 60

                # 第1タイミング: first_minutes分前（±2分範囲）
                if (first_minutes - 5) <= time_until_start <= (first_minutes + 2):
                    if not reserve.get("wol_sent_first", False):
                        return reserve

                # 第2タイミング: second_minutes分前（±2分範囲）
                if (second_minutes - 2) <= time_until_start <= (second_minutes + 2):
                    if not reserve.get("wol_sent_second", False):
                        return reserve

            except (ValueError, KeyError) as e:
                self.logger.debug(f"予約情報の解析エラー: {e}")
                continue

        return None

    def _send_wol(self, cache_data):
        """
        WOLパケットを送信し、キャッシュを更新

        Args:
            cache_data: キャッシュデータ

        Returns:
            bool: 送信成功ならTrue
        """
        try:
            mac_address = self.config["desktop_pc"]["mac_address"]

            # send_wol.pyを実行
            send_wol_script = os.path.join(os.path.dirname(__file__), "send_wol.py")
            result = subprocess.run(
                [sys.executable, send_wol_script, mac_address],
                capture_output=True,
                timeout=5
            )

            if result.returncode != 0:
                self.logger.error(f"WOL送信失敗: {result.stderr.decode()}")
                return False

            # キャッシュの送信済みフラグを更新
            self._mark_wol_sent(cache_data)

            self.logger.info(f"WOL送信成功 (MAC: {mac_address})")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("WOL送信タイムアウト")
            return False
        except Exception as e:
            self.logger.error(f"WOL送信エラー: {e}")
            return False

    def _mark_wol_sent(self, cache_data):
        """
        キャッシュの送信済みフラグを更新

        Args:
            cache_data: キャッシュデータ
        """
        try:
            now = datetime.now()
            first_minutes = self.config["wol_timing"]["first_minutes"]
            second_minutes = self.config["wol_timing"]["second_minutes"]

            for reserve in cache_data["reserves"]:
                try:
                    start_time = datetime.fromisoformat(reserve["start_time"])
                    time_until_start = (start_time - now).total_seconds() / 60

                    # 第1タイミングで送信の場合
                    if (first_minutes - 5) <= time_until_start <= (first_minutes + 2):
                        reserve["wol_sent_first"] = True

                    # 第2タイミングで送信の場合
                    if (second_minutes - 2) <= time_until_start <= (second_minutes + 2):
                        reserve["wol_sent_second"] = True

                except (ValueError, KeyError):
                    continue

            # キャッシュを保存
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"キャッシュ更新エラー: {e}")


def main():
    """メイン処理"""
    # パスの設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    config_path = os.path.join(project_dir, "config", "config.json")
    cache_path = os.path.join(project_dir, "cache", "reserves.json")
    log_dir = os.path.join(project_dir, "logs")

    # WOLチェック・送信実行
    checker = WOLChecker(config_path, cache_path, log_dir)
    success = checker.check_and_send()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
