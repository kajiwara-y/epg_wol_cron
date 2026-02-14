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
            self.logger.info("WOL送信チェック処理開始")

            # PCが起動している場合はスキップ
            pc_check_method = self.config["monitoring"]["pc_check_method"]
            self.logger.info(f"PC起動確認開始（方法: {pc_check_method}）")

            if self.pc_monitor.is_pc_alive(pc_check_method):
                self.logger.info("PCが起動中のため、WOL送信をスキップ")
                return True

            self.logger.info("PCが起動していません")

            # キャッシュから予約情報を読み込み
            self.logger.info(f"キャッシュファイル読み込み開始: {self.cache_path}")
            cache_data = self._load_cache()
            if not cache_data:
                self.logger.warning("キャッシュが見つかりません")
                return False

            self.logger.info("キャッシュ読み込み成功")

            # キャッシュの鮮度をチェック
            self.logger.info("キャッシュ鮮度チェック開始")
            if not self._check_cache_freshness(cache_data):
                self.logger.warning("キャッシュが古すぎます")
                return False

            self.logger.info("キャッシュは最新です")

            # 予約情報から条件に合致するものを検索
            self.logger.info(f"予約検索開始（保存済み予約数: {len(cache_data['reserves'])}件）")
            reserve_to_send = self._find_reserve_to_send(cache_data["reserves"])

            if reserve_to_send:
                self.logger.info(f"予約検出: {reserve_to_send['program_name']} (開始時刻: {reserve_to_send['start_time']})")
                self.logger.info("WOL送信実行")
                result = self._send_wol(cache_data)
                if result:
                    self.logger.info("WOL送信処理完了（成功）")
                else:
                    self.logger.error("WOL送信処理完了（失敗）")
                return result
            else:
                self.logger.info("送信対象の予約なし")
                return True

        except Exception as e:
            import traceback
            self.logger.error(f"WOL送信チェック中にエラー: {e}")
            self.logger.error(f"スタックトレース:\n{traceback.format_exc()}")
            return False

    def _load_cache(self):
        """
        キャッシュを読み込み

        Returns:
            dict: キャッシュデータ、読み込み失敗の場合はNone
        """
        try:
            if not os.path.exists(self.cache_path):
                self.logger.error(f"キャッシュファイルが存在しません: {self.cache_path}")
                return None

            self.logger.debug(f"キャッシュファイルを読み込み中: {self.cache_path}")
            with open(self.cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            self.logger.debug(f"キャッシュ読み込み完了（サイズ: {len(str(cache_data))}バイト）")
            return cache_data
        except json.JSONDecodeError as e:
            self.logger.error(f"キャッシュのJSON解析失敗: {e}")
            return None
        except Exception as e:
            self.logger.error(f"キャッシュ読み込みエラー: {e}")
            return None

    def _check_cache_freshness(self, cache_data):
        """
        キャッシュの鮮度をチェック

        Args:
            cache_data: キャッシュデータ

        Returns:
            bool: 十分に新鮮ならTrue
        """
        try:
            max_age_hours = self.config["cache"]["max_age_hours"]
            last_updated = datetime.fromisoformat(cache_data["last_updated"])
            age = datetime.now() - last_updated
            age_hours = age.total_seconds() / 3600

            self.logger.debug(f"キャッシュ最終更新: {last_updated.isoformat()}")
            self.logger.debug(f"キャッシュ経過時間: {age_hours:.2f}時間 (最大: {max_age_hours}時間)")

            if age > timedelta(hours=max_age_hours):
                self.logger.warning(
                    f"キャッシュが古すぎます: {age_hours:.2f}時間前に更新 (最大: {max_age_hours}時間)"
                )
                return False

            self.logger.debug("キャッシュ鮮度チェック: OK")
            return True
        except (ValueError, KeyError) as e:
            self.logger.error(f"キャッシュ鮮度チェック失敗: {e}")
            return False

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

        self.logger.debug(f"WOL送信タイミング設定: 第1={first_minutes}分前、第2={second_minutes}分前")
        self.logger.debug(f"予約検索対象: {len(reserves)}件")

        for i, reserve in enumerate(reserves):
            try:
                start_time = datetime.fromisoformat(reserve["start_time"])
                time_until_start = (start_time - now).total_seconds() / 60
                program_name = reserve.get("program_name", "不明")

                self.logger.debug(
                    f"予約{i+1}: {program_name} / 開始時刻: {start_time.isoformat()} / "
                    f"開始まで: {time_until_start:.1f}分"
                )

                # 第1タイミング: first_minutes分前（±2分範囲）
                if (first_minutes - 5) <= time_until_start <= (first_minutes + 2):
                    if not reserve.get("wol_sent_first", False):
                        self.logger.info(
                            f"WOL送信対象検出（第1タイミング）: {program_name} "
                            f"({time_until_start:.1f}分前)"
                        )
                        return reserve
                    else:
                        self.logger.debug(f"第1タイミングでの送信済み: {program_name}")

                # 第2タイミング: second_minutes分前（±2分範囲）
                if (second_minutes - 2) <= time_until_start <= (second_minutes + 2):
                    if not reserve.get("wol_sent_second", False):
                        self.logger.info(
                            f"WOL送信対象検出（第2タイミング）: {program_name} "
                            f"({time_until_start:.1f}分前)"
                        )
                        return reserve
                    else:
                        self.logger.debug(f"第2タイミングでの送信済み: {program_name}")

            except (ValueError, KeyError) as e:
                self.logger.debug(f"予約情報の解析エラー（予約{i+1}）: {e}")
                continue

        self.logger.debug("WOL送信対象なし")
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
            self.logger.info(f"WOLパケット送信開始 (MAC: {mac_address})")

            # send_wol.pyを実行
            send_wol_script = os.path.join(os.path.dirname(__file__), "send_wol.py")
            self.logger.debug(f"WOLスクリプト実行: {send_wol_script}")

            result = subprocess.run(
                [sys.executable, send_wol_script, mac_address],
                capture_output=True,
                timeout=5
            )

            self.logger.debug(f"WOLスクリプト終了コード: {result.returncode}")

            if result.returncode != 0:
                error_msg = result.stderr.decode()
                self.logger.error(f"WOL送信失敗: {error_msg}")
                return False

            self.logger.debug("WOLスクリプト実行成功")

            # キャッシュの送信済みフラグを更新
            self.logger.info("キャッシュ更新開始")
            self._mark_wol_sent(cache_data)

            self.logger.info(f"WOL送信完了成功 (MAC: {mac_address})")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("WOL送信タイムアウト (スクリプト実行時間超過)")
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

            self.logger.debug("送信済みフラグ更新処理開始")
            updated_count = 0

            for reserve in cache_data["reserves"]:
                try:
                    start_time = datetime.fromisoformat(reserve["start_time"])
                    time_until_start = (start_time - now).total_seconds() / 60
                    program_name = reserve.get("program_name", "不明")

                    # 第1タイミングで送信の場合
                    if (first_minutes - 5) <= time_until_start <= (first_minutes + 2):
                        if not reserve.get("wol_sent_first", False):
                            reserve["wol_sent_first"] = True
                            self.logger.debug(f"第1タイミング送信済みフラグ更新: {program_name}")
                            updated_count += 1

                    # 第2タイミングで送信の場合
                    if (second_minutes - 2) <= time_until_start <= (second_minutes + 2):
                        if not reserve.get("wol_sent_second", False):
                            reserve["wol_sent_second"] = True
                            self.logger.debug(f"第2タイミング送信済みフラグ更新: {program_name}")
                            updated_count += 1

                except (ValueError, KeyError) as e:
                    self.logger.debug(f"予約情報処理エラー: {e}")
                    continue

            # キャッシュを保存
            self.logger.info(f"キャッシュファイル保存開始（更新件数: {updated_count}件）")
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"キャッシュファイル保存完了: {self.cache_path}")

        except Exception as e:
            self.logger.error(f"キャッシュ更新エラー: {e}")


def main():
    """メイン処理"""
    # パスの設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    config_path = os.path.join(project_dir, "config", "config.json")
    cache_path = os.path.join(project_dir, "cache", "reserves.json")

    # 設定ファイルを読み込んでログディレクトリを取得
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        log_dir = config.get("logging", {}).get("dir", os.path.join(project_dir, "logs"))
        # チルダ展開に対応（~/... の場合）
        log_dir = os.path.expanduser(log_dir)
    except (FileNotFoundError, json.JSONDecodeError):
        # 設定ファイルが読み込めない場合はデフォルト値を使用
        log_dir = os.path.join(project_dir, "logs")

    # WOLチェック・送信実行
    try:
        checker = WOLChecker(config_path, cache_path, log_dir)
        success = checker.check_and_send()

        if success:
            exit_code = 0
        else:
            exit_code = 1

    except Exception as e:
        import traceback
        print(f"致命的エラー: {e}")
        print(f"スタックトレース:\n{traceback.format_exc()}")
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
