#!/bin/bash
# FORLIU 快速体验脚本
# 用法: bash examples/quick_start.sh

set -e
cd "$(dirname "$0")/.."

echo "=============================="
echo "  FORLIU 金融股票选择 Skill"
echo "=============================="
echo ""

# 检查 Python
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
echo "[1/5] Python: $PYTHON ($($PYTHON --version))"

# 列出预设策略
echo ""
echo "[2/5] 可用预设策略:"
$PYTHON -m code.main presets

# Mock 模式筛选
echo ""
echo "[3/5] 低估值策略 TOP 5 (Mock 数据):"
$PYTHON -m code.main screen --strategy value --top 5 --provider mock

echo ""
echo "[4/5] 单股分析 (600519 贵州茅台):"
$PYTHON -m code.main analyze --stock 600519 --start 2025-06-01 --end 2025-06-10

# 配置展示
echo ""
echo "[5/5] 当前配置:"
$PYTHON -m code.main config show

echo ""
echo "=============================="
echo "  体验完成！"
echo "  下一步: pip3 install akshare baostock"
echo "  然后: python3 -m code.main screen --strategy value --provider smart+cache"
echo "=============================="
