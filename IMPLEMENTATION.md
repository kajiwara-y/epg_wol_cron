# logrotate実装ドキュメント

## 実装概要

Raspberry Pi環境でのログローテーション機能を`logrotate`を使用して実装しました。

ログローテーション設定は **config/config.json で一元管理** され、`setup/install.sh` により自動的に `/etc/logrotate.d/epgstation-wol` に生成されます。

## 作成したファイル

### 1. **setup/install.sh**
Raspberry Pi上でのセットアップスクリプト

**実行内容**:
1. 権限確認（sudo権限が必要）
2. 設定ファイル確認 (`config/config.json`)
3. config.json から logging 設定を読み込み
4. ログディレクトリ作成
5. logrotate設定を**動的に生成** （config.json の設定値を使用）
6. logrotate設定の動作テスト
7. スクリプトファイルのパーミッション設定
8. crontab設定の案内

**使用方法**:
```bash
sudo bash setup/install.sh
```

### 2. **setup/LOGROTATE.md**
ログローテーション設定の詳細ドキュメント

**内容**:
- ローテーション設定の説明
- セットアップ手順（詳細版）
- 動作確認方法
- トラブルシューティング
- ログ圧縮によるディスク容量削減の説明

## 更新したファイル

### 1. **config/config.example.json**
- `logging.rotation` セクションを追加
- ローテーション設定オプションを定義

### 2. **README.md**
- ログローテーション設定手順を追加
- ログ確認コマンドを更新（`/var/log/epgstation-wol/` パスに対応）
- `setup/LOGROTATE.md` への参照を追加

### 3. **.gitignore**
- ローカル環境とRaspberry Pi環境でのログディレクトリの相違について注記を追加

## ローテーション設定の詳細

### config.json での設定方法

ログローテーション設定は `config/config.json` の `logging.rotation` セクションで管理します：

```json
{
  "logging": {
    "level": "INFO",
    "dir": "/var/log/epgstation-wol",
    "rotation": {
      "frequency": "daily",        // ローテーション周期（daily, weekly, monthly など）
      "rotate": 7,                 // 保持世代数
      "compress": true,            // gzip圧縮を有効にするか
      "delaycompress": true,       // 次のローテーション時点で圧縮するか
      "notifempty": true,          // 空のファイルをローテーション対象外にするか
      "missingok": true            // ファイル欠落時にエラーを無視するか
    }
  }
}
```

### ローテーション対象

install.sh により自動生成される logrotate 設定：

```
{logging.dir}/*.log
```

デフォルト対象ファイル：
- `/var/log/epgstation-wol/update.log` - 予約情報キャッシュ更新ログ
- `/var/log/epgstation-wol/wol.log` - WOL送信ログ
- その他の `.log` ファイル

### ローテーション設定（デフォルト値）

| 項目 | 設定値 | 説明 |
|------|--------|------|
| 周期 | `daily` | 毎日実行 |
| 保持世代数 | `7` | 7世代保持 |
| 圧縮 | `true` | gzip圧縮有効 |
| 圧縮遅延 | `true` | 次のローテーション時に圧縮 |
| 空ファイル無視 | `true` | 空ファイルはスキップ |
| 欠落ファイル無視 | `true` | ファイル欠落時はエラーなし |

### ローテーション実行時刻

Raspberry Pi OSのデフォルト設定では、`logrotate`は以下の時刻に実行されます：

```bash
# 確認コマンド
cat /etc/crontab | grep daily
```

通常は午前6時25分（6:25）に実行されます。

### 設定変更方法

ログローテーション設定を変更する場合：

1. **config/config.json を編集**
   ```json
   {
     "logging": {
       "rotation": {
         "rotate": 14              // 例: 保持期間を14日に変更
       }
     }
   }
   ```

2. **セットアップスクリプトを再実行**
   ```bash
   sudo bash setup/install.sh
   ```

3. **logrotate設定が自動更新される**
   ```bash
   cat /etc/logrotate.d/epgstation-wol  # 確認
   ```

**重要**: `setup/install.sh` を実行すると、`config/config.json` の設定値で `/etc/logrotate.d/epgstation-wol` が上書きされます。

## ディスク容量の削減

### 圧縮率の目安

- テキストログ：約70～80%削減
- 1.1MB のログ → 200～300KB に圧縮

### 容量計算例

毎日100KBのログが生成される場合：

```
圧縮前: 100KB × 7日 = 700KB
圧縮後: 20～30KB × 7日 = 140～210KB
削減量: 約500～560KB
```

## セットアップから動作確認までのフロー

### 1. ローカル開発環境（Mac）

開発時はローカルの `logs/` ディレクトリにログが保存されます。

```bash
# ローカルでの開発・テスト
python scripts/update_cache.py
tail logs/update.log
```

### 2. Raspberry Pi 本番環境

```bash
# セットアップスクリプト実行（初回のみ）
cd ~/epgstation-wol
sudo bash setup/install.sh

# crontab設定
crontab -e

# 以下を追加
*/10 * * * * /home/pi/epgstation-wol/scripts/update_cache.py >> /var/log/epgstation-wol/update.log 2>&1
*/5 * * * * /home/pi/epgstation-wol/scripts/check_and_wol.py >> /var/log/epgstation-wol/wol.log 2>&1

# ログディレクトリを確認
ls -lh /var/log/epgstation-wol/

# logrotate設定を確認
sudo cat /etc/logrotate.d/epgstation-wol

# logrotateの動作をテスト
sudo logrotate -d /etc/logrotate.d/epgstation-wol
```

### 3. 動作確認（翌日以降）

```bash
# ローテーション後のログディレクトリ
ls -lh /var/log/epgstation-wol/

# 圧縮ログの確認
zcat /var/log/epgstation-wol/update.log.2.gz | head -20
```

## トラブルシューティング

### ログローテーションが実行されない場合

1. **cron.dailyの実行確認**
   ```bash
   sudo systemctl status cron
   ```

2. **logrotateを手動実行**
   ```bash
   sudo /usr/sbin/logrotate /etc/logrotate.d/epgstation-wol
   ```

3. **パーミッション確認**
   ```bash
   ls -la /etc/logrotate.d/epgstation-wol
   ls -la /var/log/epgstation-wol/
   ```

### 圧縮ファイルの確認

```bash
# gzip ファイルを展開
gunzip /var/log/epgstation-wol/update.log.2.gz

# または、展開せずに確認
zcat /var/log/epgstation-wol/update.log.2.gz | tail -20
```

## 今後の拡張案

### 1. メール通知（オプション）

logrotateの `postrotate` スクリプトでメール送信：

```bash
postrotate
    mail -s "ログローテーション完了" admin@example.com << EOF
ログローテーション完了
実行日時: $(date)
EOF
endscript
```

### 2. 保持期間の動的変更

config.json に以下を追加：

```json
{
  "logging": {
    "rotation": {
      "backup_count": 7,    # ローテーション世代数
      "max_days": 30        # 最大保持日数
    }
  }
}
```

### 3. ログのアーカイブ

古いログを別ディレクトリにアーカイブ：

```bash
postrotate
    mkdir -p /var/log/epgstation-wol/archive
    find /var/log/epgstation-wol -name "*.gz" -mtime +30 \
        -exec mv {} /var/log/epgstation-wol/archive/ \;
endscript
```

## 参考資料

- [logrotate マニュアル](https://linux.die.net/man/8/logrotate)
- [Debian/Ubuntu logrotate](https://manpages.debian.org/bullseye/logrotate/logrotate.8)
- [Raspberry Pi OS](https://www.raspberrypi.org/downloads/raspberry-pi-os/)
