# ログローテーション設定ガイド

このドキュメントはRaspberry Pi上での`logrotate`を使用したログローテーション設定について説明します。

## 概要

ログファイルが無限に増え続けることを防ぐため、`logrotate`を使用して自動的にログを管理します。

ログローテーション設定は `config/config.json` で管理され、`setup/install.sh` により自動生成されます。

## 設定内容

ログローテーション設定は `config/config.json` で管理されます。

### config.json の logging.rotation セクション

```json
{
  "logging": {
    "level": "INFO",
    "dir": "/var/log/epgstation-wol",
    "rotation": {
      "frequency": "daily",        // ローテーション周期
      "rotate": 7,                 // 保持世代数
      "compress": true,            // gzip圧縮を有効
      "delaycompress": true,       // 次回まで圧縮を遅延
      "notifempty": true,          // 空ファイルはローテーション対象外
      "missingok": true            // ファイル欠落時はエラーなし
    }
  }
}
```

### 生成されるlogrotate設定例

```
/var/log/epgstation-wol/*.log {
    daily              # 日次でローテーション
    compress           # 古いログをgzip圧縮
    delaycompress      # 次のローテーションまで圧縮を遅延
    notifempty         # 空ファイルはローテーションしない
    missingok          # ファイルがない場合はエラーを無視
    rotate 7           # 7世代まで保持
    create 0644 root root  # ローテーション後に新ファイルを作成
}
```

### 効果

| 項目 | 説明 |
|------|------|
| **ローテーション頻度** | 毎日（深夜0時） |
| **保持期間** | 7日間 |
| **圧縮** | gzipで自動圧縮 |
| **ディスク容量節約** | 約70～80%削減 |

### ファイル例

```
update.log                 # 当日のログ（記録中）
update.log.1               # 1日前のログ
update.log.2.gz            # 2日前のログ（圧縮済み）
update.log.3.gz            # 3日前のログ（圧縮済み）
...
update.log.7.gz            # 7日前のログ（圧縮済み）
```

## セットアップ手順

### 1. セットアップスクリプトを実行

```bash
cd ~/epgstation-wol
sudo bash setup/install.sh
```

このスクリプトが行うこと：
- ログディレクトリ `/var/log/epgstation-wol` を作成
- logrotate設定を `/etc/logrotate.d/epgstation-wol` にインストール
- スクリプトのパーミッションを設定
- 設定をテスト

### 2. crontabを設定

スクリプトの案内に従い、cronタスクを登録します。

```bash
crontab -e
```

以下を追加：

```bash
# EPG Station WOL Cron
# 予約情報キャッシュ更新 (10分間隔)
*/10 * * * * /home/pi/epgstation-wol/scripts/update_cache.py

# WOL送信判定 (5分間隔)
*/5 * * * * /home/pi/epgstation-wol/scripts/check_and_wol.py
```

**注意**: ログはスクリプト内の logger により自動的に `/var/log/epgstation-wol/` に記録されるため、リダイレクトは不要です。

### 3. 設定確認

```bash
# ログディレクトリの確認
ls -la /var/log/epgstation-wol

# logrotate設定の確認
sudo cat /etc/logrotate.d/epgstation-wol

# logrotateの動作テスト
sudo logrotate -d /etc/logrotate.d/epgstation-wol
```

## 動作確認

### ログローテーション前

```bash
$ ls -lh /var/log/epgstation-wol/
total 1.2M
-rw-r--r-- 1 root root 1.1M Feb 14 10:30 update.log
-rw-r--r-- 1 root root  150K Feb 14 10:31 wol.log
```

### ログローテーション後（次の日）

```bash
$ ls -lh /var/log/epgstation-wol/
total 320K
-rw-r--r-- 1 root root   50K Feb 15 00:05 update.log
-rw-r--r-- 1 root root    8K Feb 15 00:05 wol.log
-rw-r--r-- 1 root root  150K Feb 14 23:59 update.log.1
-rw-r--r-- 1 root root   12K Feb 14 23:59 wol.log.1
-rw-r--r-- 1 root root   85K Feb 13 23:59 update.log.2.gz
-rw-r--r-- 1 root root    5K Feb 13 23:59 wol.log.2.gz
```

## トラブルシューティング

### ログローテーションが実行されない

**原因1: cron.dailyが実行されていない**

```bash
# cron.dailyの実行スケジュール確認
sudo systemctl status cron

# 手動で実行テスト
sudo /usr/sbin/logrotate /etc/logrotate.d/epgstation-wol
```

**原因2: パーミッション不足**

```bash
# logrotate設定のパーミッション確認
ls -la /etc/logrotate.d/epgstation-wol

# ログディレクトリのパーミッション確認
ls -la /var/log/epgstation-wol/
```

### 圧縮ファイルが展開できない

```bash
# gzipで展開
gunzip /var/log/epgstation-wol/update.log.2.gz

# または確認のみ
zcat /var/log/epgstation-wol/update.log.2.gz | head -20
```

### ログが多すぎて保持期間を変更したい

`/etc/logrotate.d/epgstation-wol` を編集：

```bash
sudo nano /etc/logrotate.d/epgstation-wol
```

```diff
- rotate 7   # 7日間保持
+ rotate 14  # 14日間保持
```

## logrotateのスケジュール確認

### Raspberry Pi OS の場合

```bash
# cron.daily の実行スケジュール確認
cat /etc/crontab | grep daily
```

通常は `6:25` か `25 6` に実行されます。

### 実行スケジュール変更

```bash
# cron.daily の実行時刻を変更
sudo nano /etc/crontab
```

例：毎日午前2時に実行

```
2 2 * * * root run-parts --report /etc/cron.daily
```

## ログ圧縮によるディスク容量削減

### 圧縮率の目安

- テキストログ：約70～80%削減
- 例：1.1MBのログ → 200～300KBに圧縮

### 容量計算例

毎日100KBのログが生成される場合：

```
圧縮前: 100KB × 7日 = 700KB
圧縮後: 20～30KB × 7日 = 140～210KB
削減量: 約500～560KB
```

## 参考資料

- [logrotate マニュアル](https://linux.die.net/man/8/logrotate)
- [Debian/Ubuntu logrotate](https://manpages.debian.org/bullseye/logrotate/logrotate.8)
