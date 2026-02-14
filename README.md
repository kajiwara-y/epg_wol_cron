# EPG Station WOL Cron

EPG Stationの予約録画失敗を防ぐWOL（Wake-on-LAN）自動起動システムです。

## 概要

### システム構成

- **デスクトップPC**: epg station + Mirakurun（24時間休止可能）
- **RaspberryPi**: 常時稼働、予約監視・WOL送信

### 基本動作フロー

```
┌─────────────────────────────────────────────────────────┐
│ RaspberryPi (常時稼働)                                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ update_cache.py (10分間隔, PC起動時のみ実行)   │  │
│  │ - epg station APIから予約情報を取得            │  │
│  │ - reserves.json に保存                         │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ check_and_wol.py (5分間隔, 常時実行)            │  │
│  │ - reserves.json から予約をチェック              │  │
│  │ - PC起動状態確認                                │  │
│  │ - 25-30分前/0-5分前に予約あり → WOL送信       │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ send_wol.py (WOLパケット送信)                    │  │
│  │ - 指定MACアドレスへWOLパケット送信              │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ デスクトップPC（スリープ/休止状態から復帰）      │  │
│  └──────────────────────────────────────────────────┘  │
│
└─────────────────────────────────────────────────────────┘
```

## ディレクトリ構成

```
epgstation-wol/
├── scripts/
│   ├── update_cache.py       # 予約情報キャッシュ更新
│   ├── check_and_wol.py      # キャッシュ確認・WOL送信
│   ├── send_wol.py           # WOL送信ユーティリティ
│   └── utils/
│       ├── __init__.py
│       ├── logger.py         # ログ管理ユーティリティ
│       └── pc_monitor.py     # PC状態監視ユーティリティ
├── config/
│   ├── config.example.json   # 設定ファイル(サンプル)
│   └── config.json           # 実際の設定(git ignore)
├── cache/
│   └── reserves.json         # 予約情報キャッシュ
├── logs/
│   ├── update.log            # キャッシュ更新ログ
│   └── wol.log               # WOL送信ログ
├── setup/
│   ├── install.sh            # セットアップスクリプト
│   └── crontab.template      # cron設定テンプレート
├── README.md
├── .gitignore
└── requirements.txt
```

## インストール

### 必要な環境

- Python 3.7以上
- `pip` パッケージマネージャ

### セットアップ手順

#### 1. リポジトリのクローン（初回のみ）

```bash
git clone <repository-url> epgstation-wol
cd epgstation-wol
```

#### 2. 仮想環境の作成（初回のみ）

```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

#### 4. 設定ファイルの作成

```bash
cp config/config.example.json config/config.json
nano config/config.json
```

以下の項目を設定してください:

```json
{
  "desktop_pc": {
    "mac_address": "XX:XX:XX:XX:XX:XX",  # デスクトップPCのMACアドレス
    "ip_address": "192.168.1.100"         # デスクトップPCのIPアドレス
  },
  "epgstation": {
    "api_url": "http://192.168.1.100:8888/api",  # epg station APIのURL
    "timeout": 10                                  # API取得タイムアウト（秒）
  },
  "wol_timing": {
    "first_minutes": 30,   # 第1タイミング: 30分前
    "second_minutes": 5    # 第2タイミング: 5分前
  },
  "monitoring": {
    "pc_check_method": "ping",  # PC確認方法 ("ping" or "port")
    "pc_check_timeout": 3       # PC確認タイムアウト（秒）
  },
  "cache": {
    "path": "/path/to/cache/reserves.json",  # キャッシュファイルパス
    "max_age_hours": 24                       # キャッシュ最大保持時間
  },
  "logging": {
    "level": "INFO",           # ログレベル
    "dir": "/path/to/logs"    # ログディレクトリ
  }
}
```

#### 5. Cron設定

```bash
# crontabを編集
crontab -e

# 以下の行を追加
*/10 * * * * cd ~/epgstation-wol && source venv/bin/activate && python scripts/update_cache.py >> logs/update.log 2>&1
*/5 * * * * cd ~/epgstation-wol && source venv/bin/activate && python scripts/check_and_wol.py >> logs/wol.log 2>&1
```

## 使用方法

### 手動実行

```bash
# キャッシュ更新
python scripts/update_cache.py

# WOLチェック・送信
python scripts/check_and_wol.py

# WOL直接送信（テスト用）
python scripts/send_wol.py XX:XX:XX:XX:XX:XX
```

### ログ確認

```bash
# キャッシュ更新ログ
tail -f logs/update.log

# WOL送信ログ
tail -f logs/wol.log
```

## 動作原理

### キャッシュ更新フロー (update_cache.py)

1. **epg station APIへのアクセス**
   - デスクトップPCが起動している時のみ成功
   - `/api/reserves` エンドポイントから予約情報を取得

2. **キャッシュ保存**
   - JSON形式で `cache/reserves.json` に保存
   - `last_updated` フィールドに更新日時を記録

### WOL送信フロー (check_and_wol.py)

1. **PC起動状態確認**
   - `ping` コマンドまたはポート接続で確認
   - 起動中ならスキップ（不要なWOL送信防止）

2. **キャッシュ鮮度チェック**
   - キャッシュの更新日時から経過時間を確認
   - 設定の `max_age_hours` を超えている場合は警告

3. **予約検索**
   - 現在時刻から以下のタイミングをチェック:
     - **第1タイミング**: 25-35分前の予約
     - **第2タイミング**: 3-7分前の予約

4. **WOL送信**
   - 条件に合致する予約が見つかった場合、WOLパケットを送信
   - キャッシュに送信済みフラグを設定（重複送信防止）

### WOL送信処理 (send_wol.py)

1. **MACアドレス検証**
   - 入力されたMACアドレスの形式を検証

2. **WOLパケット構築**
   - ヘッダ: `FF:FF:FF:FF:FF:FF`
   - ペイロード: MACアドレスを16回繰り返す

3. **ブロードキャスト送信**
   - UDPポート9へ `255.255.255.255` にブロードキャスト送信

## キャッシュデータ形式

```json
{
  "last_updated": "2026-02-14T10:30:00",
  "reserves": [
    {
      "id": 12345,
      "program_name": "番組名",
      "start_time": "2026-02-14T20:00:00",
      "end_time": "2026-02-14T21:00:00",
      "wol_sent_first": false,
      "wol_sent_second": false
    }
  ]
}
```

## トラブルシューティング

### WOLが機能しない場合

1. **デスクトップPCのBIOS設定**
   - BIOS/UEFIでWOL（Wake-on-LAN）を有効化
   - ネットワークドライバ設定でWOL有効化
   - Windowsの場合: 高速スタートアップを無効化

2. **ネットワーク設定**
   - ファイアウォールがUDPポート9をブロックしていないか確認
   - ルータのブロードキャスト転送設定を確認

3. **MACアドレスの確認**
   - 正しいMACアドレスが設定されているか確認
   - `ipconfig /all` (Windows) または `ifconfig` (Linux/Mac) で確認可能

### ログに記録がない場合

1. **Cron実行権限の確認**
   ```bash
   crontab -l  # 登録内容確認
   ```

2. **仮想環境の有効化**
   - Cronからの実行時は仮想環境を有効化する必要があります
   - `source ~/epgstation-wol/venv/bin/activate` を実行

3. **ログディレクトリのパーミッション**
   ```bash
   chmod 755 logs
   ```

## テスト

### 各スクリプトの個別テスト

```bash
# キャッシュ更新テスト（PCが起動している状態で実行）
python scripts/update_cache.py

# WOLチェック・送信テスト
python scripts/check_and_wol.py

# WOL直接送信テスト
python scripts/send_wol.py XX:XX:XX:XX:XX:XX
```

### ログ確認

```bash
# 最新のログを表示
tail -20 logs/update.log
tail -20 logs/wol.log

# リアルタイムでログを監視
tail -f logs/update.log &
tail -f logs/wol.log
```

## デスクトップPC設定

### Windows 10/11

1. **BIOSでWOL有効化**
   - 再起動時にDel/F2キーを長押ししてBIOS画面へ
   - Power Management → Wake on LAN を有効化

2. **ネットワークドライバ設定**
   - デバイスマネージャー → ネットワークアダプタ → 右クリック → プロパティ
   - 詳細設定タブ → 「Magic Packet時にスリープ解除」を有効化

3. **高速スタートアップ無効化**
   - コントロールパネル → 電源オプション
   - 「電源ボタンの動作を選択」→ 「現在利用可能ではない設定を変更」
   - 「高速スタートアップを有効にする」をオフ

### Linux

WOLを有効化するには、`ethtool` コマンドを使用:

```bash
# WOL有効化
sudo ethtool -s eth0 wol g

# 設定確認
ethtool eth0 | grep Wake-on
```

起動時に自動有効化するには `/etc/network/interfaces` に追加:

```
pre-up ethtool -s eth0 wol g
```

## 参考情報

- [EPG Station GitHub](https://github.com/l3tnun/EPGStation)
- [Wake-on-LAN - Wikipedia](https://ja.wikipedia.org/wiki/Wake-on-LAN)

## ライセンス

MIT

## 作成者

ProjectSand Team
