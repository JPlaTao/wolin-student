#!/bin/bash
# 一键启动开发服务器（自动使用 .venv）
# 用法: ./start.sh [--reload] [--port PORT]

PORT=8080
RELOAD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reload) RELOAD="--reload" ;;
    --port) PORT="$2"; shift ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "🚀 启动沃林学生管理系统 (port=$PORT, reload=$RELOAD)"
echo "    Python: $SCRIPT_DIR/.venv/Scripts/python"
exec "$SCRIPT_DIR/.venv/Scripts/uvicorn" main:app --host 0.0.0.0 --port "$PORT" $RELOAD
