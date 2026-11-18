# 再利用ガイド：セキュア開発ハーネス一式

このリポジトリで作った「ハーネス＋ガードレール＋テストで証明」の仕組みを、
**別のプロジェクトでも使い回す**ための記録。SUNABACO「生成AIセキュア開発講座」Day16〜21の進め方に沿う。

## この仕組みは何を守るか（3層）
1. **ハーネス（言葉のルール）**：`AGENTS.md`／`SPEC.md`／`SECURITY.md`。AIに守らせたい約束を文章で。
2. **テストで証明**：対策を実装したら、効いていることをテストで示す（全部緑＝証拠）。
   未実装のP0は xfail/赤で「未達」を見える化（`tests/p0/`）。
3. **ガードレール（仕組みで強制）**：言葉は破られるので、プログラムで守る。
   - ローカル：`hooks/`（ブランチ強制・変更検知・push前テスト）
   - サーバー：GitHub Actions→GitHub Issue通知（メールで届く）、CODEOWNERS、ブランチ保護
   - 実行環境：Claude Code の deny/サンドボックス/マネージド設定
   → 詳細は [GUARDRAILS.md](../GUARDRAILS.md)。

## 新しいプロジェクトへの展開（1コマンド）
```bash
# 1) 新リポをgit化（まだなら）
cd /path/to/new-project && git init

# 2) このリポのスクリプトでハーネス一式を展開
bash "/Users/akimitsu/Documents/SUNABACO/SUNABACO Cyber security testing/juku-seiseki-app/setup/setup-harness.sh" /path/to/new-project
```
展開されるもの：`hooks/`・`tools/guardrail-*`・`.github/workflows/guardrail-watch.yml`・
`.github/CODEOWNERS`・`GUARDRAILS.md`、無ければ `AGENTS.md`/`SPEC.md`/`SECURITY.md` の雛形。
`core.hooksPath=hooks` を設定し、変更検知の台帳も初期化する。

## 展開後に人がやること（ここまでやって“本物”）
1. `.github/CODEOWNERS` のオーナー名を自分のGitHubアカウントに直す。
2. GitHub → Settings → Branches → `main` に **ブランチ保護**
   （PR必須・CODEOWNERSレビュー必須・直接push禁止・ステータスチェック必須）。
3. 通知は既定で **GitHub Issue**（オーナーに割り当て＝メールで届く。追加設定不要）。
   チームでSlackに流す場合のみ、通知ステップを Webhook＋Secrets `SLACK_WEBHOOK_URL` に差し替える。
4. `hooks/pre-push` のテストコマンドをプロジェクトに合わせる（既定 `pytest`。Next.js等なら `npm test` 等）。
5. `SPEC.md`/`SECURITY.md` にそのプロジェクトの中身を書く。

## 日々の運用
- 作業は必ず**ブランチを切って**から（main/develop直コミットはフックが拒否）。
- ルール/フックを**正規に**変えたら `bash tools/guardrail-approve.sh` で台帳を更新（人が意図して実行）。
- 無断変更はコミット時に検知されて止まる＋（push後は）Slackに通知。
- 対策を足したら**テストで証明**（`tests/`）。P0の未達は `tests/p0/` に受入テストとして残す。

## 開発の順番（Day21の流れ）
1. 要件・設計（Mermaidで構成図と**信頼境界**、STRIDEで脅威、**優先順位P0/P1/P2**）。
2. バックログ化（セキュリティ対策も“普通の開発項目”として並べる＝セキュア・バイ・デザイン）。
3. **P0のテストを先に作る（実装はまだ）**＝Redファースト。未実装なら赤/xfailで見える化。
4. 最小実装で緑に → リファクタ（青）。全部緑＝「ここまで担保」の証拠をお客さんに渡せる。
5. ガードレールを整えてからデプロイ。コスト・品質・締切の折り合いで“どこまでで出すか”は人が決める。

## 限界（正直に）
- リポ内のファイルはAIが編集できる＝ローカルだけでは完全防止にならない（見張りまで）。
- **本物の防止はGitHub側**（ブランチ保護＋CODEOWNERS＋CI）か**管理者マネージド設定**。
- この分野は変化が速い。Claude Code等の設定は公式ドキュメントで都度確認する。
