#!/bin/bash
# ガードレール/フックの変更を検知する。変更があれば一覧を表示し、非ゼロで終了してコミットを止める。
# 正規の変更をしたあとは tools/guardrail-approve.sh を実行して台帳を更新すること。
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
LIST="tools/guardrail-files.txt"
MANIFEST="tools/guardrail-manifest.sha256"
[ -f "$LIST" ] || { echo "guardrail: $LIST がありません" >&2; exit 2; }
if [ ! -f "$MANIFEST" ]; then
  echo "guardrail: 台帳 $MANIFEST がありません。tools/guardrail-approve.sh で作成してください。" >&2
  exit 2
fi
changed=0
while IFS= read -r f; do
  case "$f" in ''|\#*) continue;; esac
  cur=""
  [ -f "$f" ] && cur=$(shasum -a 256 "$f" | awk '{print $1}')
  old=$(awk -v p="$f" '$2==p{print $1}' "$MANIFEST")
  if [ "$cur" != "$old" ]; then
    if   [ -z "$cur" ]; then echo "  削除: $f" >&2
    elif [ -z "$old" ]; then echo "  追加(台帳に無い): $f" >&2
    else                     echo "  変更: $f" >&2; fi
    changed=1
  fi
done < "$LIST"
if [ "$changed" -ne 0 ]; then
  echo "⚠ ガードレール/フックの変更を検知しました（↑）。" >&2
  echo "  正規の変更なら tools/guardrail-approve.sh を実行して台帳を更新してください。" >&2
  exit 2
fi
exit 0
