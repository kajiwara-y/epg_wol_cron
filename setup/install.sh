#!/bin/bash

# EPG Station WOL Cron - セットアップスクリプト
# このスクリプトは Raspberry Pi 上で実行します
# 実行方法: sudo bash setup/install.sh

set -e

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 現在のスクリプトディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_DIR/config/config.json"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}EPG Station WOL Cron セットアップ${NC}"
echo -e "${GREEN}========================================${NC}"

# ========================================
# 1. 権限確認
# ========================================
echo -e "\n${YELLOW}1. 権限確認...${NC}"
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}エラー: このスクリプトは sudo で実行してください${NC}"
  echo "実行方法: sudo bash setup/install.sh"
  exit 1
fi
echo -e "${GREEN}✓ 権限確認: OK${NC}"

# ========================================
# 2. 設定ファイル確認
# ========================================
echo -e "\n${YELLOW}2. 設定ファイル確認...${NC}"
if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "${RED}エラー: 設定ファイルが見つかりません${NC}"
  echo "  期待位置: $CONFIG_FILE"
  echo ""
  echo "セットアップ方法："
  echo "  1. 設定ファイルを作成してください:"
  echo "     cp config/config.example.json config/config.json"
  echo "  2. config.json を編集してください:"
  echo "     nano config/config.json"
  echo "  3. このスクリプトを再実行してください:"
  echo "     sudo bash setup/install.sh"
  exit 1
fi
echo -e "${GREEN}✓ 設定ファイル: $CONFIG_FILE${NC}"

# ========================================
# 3. config.jsonから設定を読み込む
# ========================================
echo -e "\n${YELLOW}3. 設定ファイルから logging 設定を読み込み中...${NC}"

# JSONから値を抽出するPython処理
LOG_DIR=$(python3 -c "
import json
import sys
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    log_dir = config.get('logging', {}).get('dir', '/var/log/epgstation-wol')
    print(log_dir)
except Exception as e:
    print(f'エラー: {e}', file=sys.stderr)
    sys.exit(1)
")

if [ -z "$LOG_DIR" ]; then
  echo -e "${RED}エラー: logging.dir を読み込めませんでした${NC}"
  exit 1
fi

echo -e "${GREEN}✓ ログディレクトリ: $LOG_DIR${NC}"

# rotation設定の読み込み
ROTATION_CONFIG=$(python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    rotation = config.get('logging', {}).get('rotation', {})

    # デフォルト値を設定
    frequency = rotation.get('frequency', 'daily')
    rotate = rotation.get('rotate', 7)
    compress = rotation.get('compress', True)
    delaycompress = rotation.get('delaycompress', True)
    notifempty = rotation.get('notifempty', True)
    missingok = rotation.get('missingok', True)

    print(f'{frequency}|{rotate}|{compress}|{delaycompress}|{notifempty}|{missingok}')
except Exception as e:
    # デフォルト値
    print('daily|7|True|True|True|True')
")

IFS='|' read -r FREQUENCY ROTATE COMPRESS DELAYCOMPRESS NOTIFEMPTY MISSINGOK <<< "$ROTATION_CONFIG"
echo -e "${GREEN}✓ ローテーション設定を読み込みました${NC}"

# ========================================
# 4. ログディレクトリ作成
# ========================================
echo -e "\n${YELLOW}4. ログディレクトリ作成...${NC}"
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"
echo -e "${GREEN}✓ ログディレクトリ: $LOG_DIR${NC}"

# ========================================
# 5. logrotate設定を動的に生成
# ========================================
echo -e "\n${YELLOW}5. logrotate設定を生成中...${NC}"

LOGROTATE_CONFIG="/etc/logrotate.d/epgstation-wol"

# logrotate設定ファイルを生成
cat > "$LOGROTATE_CONFIG" << 'EOF'
# EPG Station WOL Cron - ログローテーション設定
# このファイルは setup/install.sh により自動生成されます
# 手動で編集する場合は config/config.json の logging.rotation セクションを更新してください

EOF

# 動的に設定内容を追加
cat >> "$LOGROTATE_CONFIG" << EOF
$LOG_DIR/*.log {
    # ローテーション頻度
    $FREQUENCY
EOF

# compress オプション
if [ "$COMPRESS" = "True" ]; then
  echo "    compress" >> "$LOGROTATE_CONFIG"
fi

# delaycompress オプション
if [ "$DELAYCOMPRESS" = "True" ]; then
  echo "    delaycompress" >> "$LOGROTATE_CONFIG"
fi

# notifempty オプション
if [ "$NOTIFEMPTY" = "True" ]; then
  echo "    notifempty" >> "$LOGROTATE_CONFIG"
fi

# missingok オプション
if [ "$MISSINGOK" = "True" ]; then
  echo "    missingok" >> "$LOGROTATE_CONFIG"
fi

# ローテーション世代数と その他の設定
cat >> "$LOGROTATE_CONFIG" << EOF
    rotate $ROTATE
    create 0644 root root
}
EOF

chmod 644 "$LOGROTATE_CONFIG"
echo -e "${GREEN}✓ logrotate設定を生成: $LOGROTATE_CONFIG${NC}"

# ========================================
# 6. logrotateの設定をテスト
# ========================================
echo -e "\n${YELLOW}6. logrotate設定をテスト...${NC}"
if logrotate -d "$LOGROTATE_CONFIG" > /dev/null 2>&1; then
  echo -e "${GREEN}✓ logrotate設定: OK${NC}"
else
  echo -e "${RED}警告: logrotate設定にエラーがあります${NC}"
  logrotate -d "$LOGROTATE_CONFIG" || true
fi

# ========================================
# 7. crontab設定の案内
# ========================================
echo -e "\n${YELLOW}7. crontab設定（手動実施）${NC}"
echo "以下のコマンドを実行して、cronタスクを登録してください："
echo ""
echo -e "${GREEN}crontab -e${NC}"
echo ""
echo "以下をcrontabに追加してください："
echo ""
echo -e "${GREEN}# EPG Station WOL Cron${NC}"
echo -e "${GREEN}# 予約情報キャッシュ更新 (10分間隔)${NC}"
echo -e "${GREEN}*/10 * * * * $PROJECT_DIR/scripts/update_cache.py${NC}"
echo ""
echo -e "${GREEN}# WOL送信判定 (5分間隔)${NC}"
echo -e "${GREEN}*/5 * * * * $PROJECT_DIR/scripts/check_and_wol.py${NC}"
echo ""
echo -e "${YELLOW}注意: ログは自動的に $LOG_DIR に記録されます${NC}"
echo ""

# ========================================
# 8. ファイルパーミッション確認
# ========================================
echo -e "\n${YELLOW}8. ファイルパーミッション確認...${NC}"
chmod +x "$PROJECT_DIR/scripts/update_cache.py"
chmod +x "$PROJECT_DIR/scripts/check_and_wol.py"
echo -e "${GREEN}✓ スクリプトパーミッション設定完了${NC}"

# ========================================
# セットアップ完了
# ========================================
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}セットアップが完了しました！${NC}"
echo -e "${GREEN}========================================${NC}"

echo ""
echo "次のステップ："
echo "1. crontab を設定してください"
echo "   $ crontab -e"
echo ""
echo "2. logrotateの設定を確認してください"
echo "   $ cat $LOGROTATE_CONFIG"
echo ""
echo "3. ログディレクトリを確認してください"
echo "   $ ls -la $LOG_DIR"
echo ""
echo "ローテーション設定:"
echo "  - 周期: $FREQUENCY"
echo "  - 保持世代数: $ROTATE"
echo "  - 圧縮: $COMPRESS"
echo ""
