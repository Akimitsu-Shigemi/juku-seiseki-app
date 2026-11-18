#!/bin/bash
# セキュア開発ハーネス一式を別のリポジトリに展開する（使い回し用）。
#   使い方:  bash setup/setup-harness.sh /path/to/target-repo
#
# 展開するもの:
#   - hooks/pre-commit, hooks/pre-push（ブランチ強制・変更検知・push前テスト）
#   - tools/guardrail-*（監視対象一覧・ハッシュ台帳・検知/承認スクリプト）
#   - .github/workflows/guardrail-watch.yml（変更をSlack通知）
#   - .github/CODEOWNERS, GUARDRAILS.md
#   - AGENTS.md / SPEC.md / SECURITY.md（無ければ雛形を置く。既存なら触らない）
#   - core.hooksPath=hooks を設定し、台帳を初期化
set -eu

SRC="$(cd "$(dirname "$0")/.." && pwd)"     # このリポ（テンプレ元）のルート
DST="${1:?使い方: bash setup/setup-harness.sh <target-repo>}"
DST="$(cd "$DST" && pwd)"
[ -d "$DST/.git" ] || { echo "エラー: $DST はgitリポジトリではありません。先に 'git init' を。" >&2; exit 1; }

echo "展開先: $DST"
mkdir -p "$DST/hooks" "$DST/tools" "$DST/.github/workflows"

cp "$SRC/hooks/pre-commit"  "$SRC/hooks/pre-push"  "$DST/hooks/"
cp "$SRC/tools/guardrail-files.txt" "$SRC/tools/guardrail-check.sh" "$SRC/tools/guardrail-approve.sh" "$DST/tools/"
cp "$SRC/.github/workflows/guardrail-watch.yml" "$DST/.github/workflows/"
cp "$SRC/.github/CODEOWNERS" "$DST/.github/CODEOWNERS"
cp "$SRC/GUARDRAILS.md"      "$DST/GUARDRAILS.md"

# ルール3ファイルはプロジェクトごとに書くもの。無いときだけ雛形を置く（既存は上書きしない）。
if [ ! -f "$DST/AGENTS.md" ]; then
  cat > "$DST/AGENTS.md" <<'AGENTS_EOF'
# AGENTS — AIへの作業ルール

- 作業はこのリポジトリ内で行う
- SPEC.md と SECURITY.md に書かれていない機能を勝手に追加しない
- 変更後は必ずテストを実行する（pytest等）。テストの失敗を無視しない
- 秘密情報（鍵・パスワード等）をソースやログに書かない
- SQLは必ずプレースホルダ。文字列連結でクエリを作らない
- 作業ブランチを切ってから変更する（main/develop へ直接コミットしない）
- 外部へ勝手に通信・連絡しない（メール送信・外部API・公開ストレージへの送信は人の承認を得る）
- hooks/ と .github/ と tools/guardrail-* と本ファイルを勝手に書き換えない（GUARDRAILS.md参照）
- 完了時に、変更点とテスト結果を報告する
- 使うライブラリはバージョンを明記する
AGENTS_EOF
  echo "  AGENTS.md 雛形を作成"
fi
[ -f "$DST/SPEC.md" ]     || { echo "# SPEC — 仕様（このプロジェクトの作るもの・画面・完了条件を書く）" > "$DST/SPEC.md"; echo "  SPEC.md 雛形を作成"; }
[ -f "$DST/SECURITY.md" ] || { echo "# SECURITY — セキュリティ要件（認可・秘密情報・入力検証・監査ログ等を書く）" > "$DST/SECURITY.md"; echo "  SECURITY.md 雛形を作成"; }

chmod +x "$DST/hooks/pre-commit" "$DST/hooks/pre-push" "$DST/tools/guardrail-check.sh" "$DST/tools/guardrail-approve.sh"
( cd "$DST" && git config core.hooksPath hooks && bash tools/guardrail-approve.sh )

echo ""
echo "完了: $DST にハーネスを展開しました。"
echo "次にやること（GUARDRAILS.md 参照）:"
echo "  1) .github/CODEOWNERS のオーナー名を自分のGitHubアカウントに直す"
echo "  2) GitHubでブランチ保護（PR必須・CODEOWNERSレビュー必須・main直接push禁止）を設定"
echo "  3) Slack Incoming Webhook を作り、GitHub Secrets に SLACK_WEBHOOK_URL を登録"
echo "  4) pre-push のテストコマンドをプロジェクトに合わせて調整（既定は pytest）"
