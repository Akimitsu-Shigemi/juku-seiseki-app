#!/bin/bash
# ガードレール/フックの現在の内容を「正」として台帳に記録する。
# 人が意図して変更したあとに実行する（AIに勝手に実行させない運用にする）。
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
LIST="tools/guardrail-files.txt"
MANIFEST="tools/guardrail-manifest.sha256"
[ -f "$LIST" ] || { echo "guardrail: $LIST がありません" >&2; exit 2; }
: > "$MANIFEST"
while IFS= read -r f; do
  case "$f" in ''|\#*) continue;; esac
  [ -f "$f" ] && shasum -a 256 "$f" >> "$MANIFEST"
done < "$LIST"
echo "guardrail: 台帳 $MANIFEST を更新しました。"
