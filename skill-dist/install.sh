#!/usr/bin/env bash
#
# ai-info-share Skill — 一键安装脚本
# 将 Skill 安装到全局位置 ~/.trae-cn/skills/ai-info-share/
# 脚本放在 ~/.scripts/ai-info-share/
#
# 用法:
#   bash install.sh            安装
#   bash install.sh --force    覆盖已存在的安装
#   bash install.sh --uninstall  卸载
#   bash install.sh -h|--help  显示帮助

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GLOBAL_SKILL_DIR="$HOME/.trae-cn/skills/ai-info-share"
SCRIPT_DIR_HOME="$HOME/.scripts/ai-info-share"
BINARY="ai-info-share.js"

UNINSTALL=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --uninstall) UNINSTALL=1 ;;
    --force)     FORCE=1 ;;
    -h|--help)
      cat <<'HELP'
ai-info-share Skill 安装脚本

用法:
  bash install.sh            安装到全局（TRAE 可识别）
  bash install.sh --force    覆盖已存在的安装
  bash install.sh --uninstall  卸载
  bash install.sh -h|--help  显示帮助

安装完成后，TRAE 在任意项目中都能识别 ai-info-share Skill。
HELP
      exit 0
      ;;
  esac
done

# ---------- 卸载 ----------
if [ "$UNINSTALL" = "1" ]; then
  echo "→ 正在卸载 ai-info-share …"
  if [ -d "$GLOBAL_SKILL_DIR" ]; then
    rm -rf "$GLOBAL_SKILL_DIR"
    echo "✅ 已删除 $GLOBAL_SKILL_DIR"
  else
    echo "ℹ️  未发现 $GLOBAL_SKILL_DIR"
  fi
  if [ -d "$SCRIPT_DIR_HOME" ]; then
    rm -rf "$SCRIPT_DIR_HOME"
    echo "✅ 已删除 $SCRIPT_DIR_HOME"
  else
    echo "ℹ️  未发现 $SCRIPT_DIR_HOME"
  fi
  if [ -x "$HOME/.local/bin/ai-info-share" ]; then
    rm -f "$HOME/.local/bin/ai-info-share"
    echo "✅ 已删除 $HOME/.local/bin/ai-info-share"
  fi
  echo ""
  echo "✅ 卸载完成"
  exit 0
fi

# ---------- 环境检查 ----------
if ! command -v node >/dev/null 2>&1; then
  echo "❌ 错误: 未检测到 node.js。请先安装 https://nodejs.org/（需要 >= v14）"
  exit 1
fi
NODE_VERSION="$(node --version | tr -d 'v' | cut -d. -f1)"
if [ "$NODE_VERSION" -lt 14 ]; then
  echo "⚠️  警告: node 版本 $(node --version) 较旧，建议 >= v14"
fi

# ---------- 检查已有安装 ----------
if [ -d "$GLOBAL_SKILL_DIR" ] && [ "$FORCE" = "0" ]; then
  echo "⚠️  $GLOBAL_SKILL_DIR 已存在。使用 --force 覆盖，或先手动备份。"
  exit 1
fi

# ---------- 安装 ----------
echo "→ 正在安装 ai-info-share Skill …"
echo "   Skill 目录: $GLOBAL_SKILL_DIR"
echo "   脚本目录:  $SCRIPT_DIR_HOME"

mkdir -p "$GLOBAL_SKILL_DIR"
mkdir -p "$SCRIPT_DIR_HOME"

cp "$SCRIPT_DIR/$BINARY" "$SCRIPT_DIR_HOME/$BINARY"
cp "$SCRIPT_DIR/SKILL.md" "$GLOBAL_SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/SKILL.md" "$SCRIPT_DIR_HOME/skill.md" 2>/dev/null || true
cp "$SCRIPT_DIR/README.md" "$SCRIPT_DIR_HOME/README.md" 2>/dev/null || true
chmod +x "$SCRIPT_DIR_HOME/$BINARY"

# 语法检查
if node --check "$SCRIPT_DIR_HOME/$BINARY" 2>/dev/null; then
  echo "   ✅ 脚本语法校验通过"
else
  echo "   ⚠️  脚本语法校验未通过"
fi

# 可选: 在 ~/.local/bin 放个别名
if [ ! -d "$HOME/.local/bin" ]; then
  mkdir -p "$HOME/.local/bin" 2>/dev/null || true
fi
WRAPPER_OK=0
if [ -d "$HOME/.local/bin" ]; then
  cat > "$HOME/.local/bin/ai-info-share" << 'WRAPPER'
#!/usr/bin/env bash
exec node "$HOME/.scripts/ai-info-share/ai-info-share.js" "$@"
WRAPPER
  chmod +x "$HOME/.local/bin/ai-info-share"
  WRAPPER_OK=1
fi

echo ""
echo "=========================================================="
echo "✅ ai-info-share Skill 已全局安装"
echo "=========================================================="
echo ""
echo "   TRAE 全局 Skill 目录: $GLOBAL_SKILL_DIR"
echo "   脚本目录:               $SCRIPT_DIR_HOME"
echo ""
echo "   方式一（推荐）:"
echo "     node ~/.scripts/ai-info-share/ai-info-share.js --help"
echo ""
if [ "$WRAPPER_OK" = "1" ]; then
  echo "   方式二（已安装包装脚本）:"
  echo "     ~/.local/bin/ai-info-share --help"
  echo ""
  echo "   若将 ~/.local/bin 加入 \$PATH，可直接："
  echo "     ai-info-share init"
fi
echo ""
echo "   子命令速览:"
echo "     init                           初始化平台目录"
echo "     add-agent <name> <label>       注册新 Agent"
echo "     publish-report <agent> <title> 发布报告"
echo "     update-widget <source-path>    更新 widget"
echo "     serve [port]                   本地预览"
echo ""
echo "   卸载: bash $SCRIPT_DIR/install.sh --uninstall"
echo "=========================================================="
