# EPG Station WOL Cron - Project CLAUDE Configuration

## プロジェクト概要

**目的**: EPG Stationの予約録画失敗を防ぐWOL(Wake-on-LAN)自動起動システム

**構成**:
- デスクトップPC: epg station + Mirakurun(24時間休止可)
- RaspberryPi: 常時稼働、予約監視・WOL送信

**実装アプローチ**: キャッシュ方式 + cron定期実行

---

## システム設計

### 基本フロー

1. **予約情報キャッシュ更新**(10分間隔)
   - PCが起動している時に実行可能
   - epg station REST APIから予約情報をJSON形式で取得・保存
   - 最終更新日時を記録

2. **WOL送信判定**(5分間隔・常時実行)
   - キャッシュからの予約チェック
   - 現在時刻から25-30分後、0-5分後に予約があるか確認
   - 条件合致 → WOLパケット送信
   - 送信済みフラグで重複防止

### キャッシュデータ構造

```json
{
  "last_updated": "2026-02-14T10:30:00",
  "reserves": [
    {
      "id": 12345,
      "program_name": "番組名",
      "start_time": "2026-02-14T20:00:00",
      "end_time": "2026-02-14T21:00:00",
      "wol_sent": false
    }
  ]
}
```

---

## 実装要件

### 機能要件

✅ **予約情報管理**
- epg station REST API連携（`/api/reserves`）
- JSON形式でのキャッシュ管理
- キャッシュ鮮度管理（最終更新日時記録）

✅ **WOL送信**
- 30分前と5分前のタイミング検出
- WOLパケット送信（`wakeonlan` コマンド使用）
- 重複送信防止（送信済みフラグ管理）

✅ **状態監視**
- PCの起動状態確認（ping/ncコマンド）
- PC起動中ならキャッシュ更新試行
- PC起動中なら不要なWOL送信をスキップ

✅ **エラーハンドリング**
- WOL送信失敗時のリトライ（3回程度）
- API取得失敗時の対処
- キャッシュ取得失敗時のフォールバック

### 非機能要件

- **ログ記録**: 全操作をログファイルに記録
- **警告機能**: キャッシュ古すぎる場合の警告
- **操作ログ**: WOL送信履歴の詳細記録

---

## ディレクトリ構成

```
epgstation-wol/
├── scripts/
│   ├── update_cache.py       # 予約情報キャッシュ更新
│   ├── check_and_wol.py      # キャッシュ確認・WOL送信
│   ├── send_wol.py           # WOL送信ユーティリティ
│   └── utils/
│       ├── pc_monitor.py     # PC状態監視ユーティリティ
│       └── logger.py         # ログ管理ユーティリティ
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

---

## Cron設定

```bash
# 予約情報キャッシュ更新(PCが起動してる時のみ成功)
*/10 * * * * /home/pi/epgstation-wol/scripts/update_cache.py >> /var/log/epgstation-wol/update.log 2>&1

# WOLチェック(常時実行)
*/5 * * * * /home/pi/epgstation-wol/scripts/check_and_wol.py >> /var/log/epgstation-wol/wol.log 2>&1
```

---

## 設定ファイル例

### config.example.json

```json
{
  "desktop_pc": {
    "mac_address": "XX:XX:XX:XX:XX:XX",
    "ip_address": "192.168.1.100"
  },
  "epgstation": {
    "api_url": "http://192.168.1.100:8888/api",
    "timeout": 10
  },
  "wol_timing": {
    "first_minutes": 30,
    "second_minutes": 5
  },
  "monitoring": {
    "pc_check_method": "ping",
    "pc_check_timeout": 3
  },
  "cache": {
    "path": "/home/pi/epgstation-wol/cache/reserves.json",
    "max_age_hours": 24
  },
  "logging": {
    "level": "INFO",
    "dir": "/var/log/epgstation-wol"
  }
}
```

---

## 開発ワークフロー

### Mac上での開発

```bash
# リポジトリクローン
git clone <repo_url> epgstation-wol
cd epgstation-wol

# 環境セットアップ
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 開発・テスト
# → スクリプト実装・修正

git add .
git commit -m "機能追加"
git push origin main
```

### RaspberryPi上での環境構築

```bash
# リポジトリ更新
cd ~/epgstation-wol
git pull

# 初回のみ
cp config/config.example.json config/config.json
nano config/config.json        # 実際の値を設定

# cron登録
./setup/install.sh
```

---

## テストケース

- ✓ 深夜帯の予約（日付跨ぎ）
- ✓ 連続予約
- ✓ 予約直前の手動起動との競合
- ✓ PC起動失敗時のリトライ
- ✓ キャッシュ古すぎる場合の警告
- ✓ WOL重複送信防止

---

## 開発優先度

### Phase 1（基本機能）
1. 予約情報取得・キャッシュ保存（update_cache.py）
2. WOL送信ユーティリティ（send_wol.py）
3. キャッシュ確認・WOL判定ロジック（check_and_wol.py）

### Phase 2（堅牢性）
1. PC起動状態監視
2. エラーハンドリング・リトライロジック
3. ログ管理・警告機能

### Phase 3（最適化）
1. 設定管理の改善
2. テストスイート構築
3. ドキュメント整備

---

## 参考情報

- **デスクトップPC設定**
  - BIOS/UEFIでWOL有効化
  - ネットワークドライバ設定でWOL有効化
  - 高速スタートアップを無効化（Windows）
  - スリープ/休止状態からの復帰設定

- **予約情報取得**
  - epg station REST API: `/api/reserves`
  - デスクトップPC起動時のみアクセス可能
  - キャッシュで対応

- **PC起動確認方法**
  - `ping` コマンド（最も一般的）
  - `nc`（netcat）でポート確認
  - SSH接続確認

---

## 言語設定

- **スクリプト言語**: Python 3
- **コメント**: 日本語で記述
- **ログ**: 日本語で記述
- **ドキュメント**: 日本語

---

## コーディング規約

### ロギングとprint文

✅ **推奨：logger使用**
```python
# loggerを使用してすべての情報を記録
self.logger.info("処理開始")
self.logger.warning("警告メッセージ")
self.logger.error("エラーメッセージ")
self.logger.debug("デバッグ情報")
```

❌ **非推奨：print文の使用**
- cronから実行される場合、print出力は消失するため使用禁止
- ログファイルに記録されないため、運用時の追跡が困難になる

**例外：仮実装段階のみ**
- 開発初期段階での一時的な動作確認のみprint使用可
- 実装完了時には必ずloggerに置き換える

### logger初期化

```python
# CacheUpdaterクラス内で初期化
self.logger = Logger(log_dir, "update", level="INFO", debug=debug)

# debug=Trueの場合、コンソール出力も有効
if debug:
    self.logger.info("デバッグモード有効: コンソール出力を表示します")
```

### エラーハンドリング

```python
# 設定ファイルが見つからない場合は、print + sys.exit()で対応
# （初期化前のため、loggerが未設定）
except FileNotFoundError:
    print(f"エラー: 設定ファイルが見つかりません: {config_path}")
    sys.exit(1)
```
