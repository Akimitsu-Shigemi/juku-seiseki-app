# ガードレール（AIに勝手をさせない仕組み）

AIは便利だが、**ルールやフックを自分で書き換える**ことがある。だから「言葉のルール」だけでなく
「**仕組みで守る**」。ここでは何が有効で、何を人が設定する必要があるかを正直に書く。

## 大前提（正直に）
- リポジトリ内のファイル（フック・設定）は、AI（や人）が編集できる。だから**ローカルだけでは
  「完全な防止」はできない**。ローカルでできるのは「検知して止める・知らせる」＝見張り。
- **AIがセッションから回避できない“本物の防止”は、GitHub側の設定**（ブランチ保護＋CODEOWNERS＋CI）
  または管理者が配る**マネージド設定**。これらはリポジトリ内ファイルの外にある。

## いま有効なもの（このリポに入っている）

### ① ローカルのgitフック（`hooks/`、`git config core.hooksPath hooks` で有効化）
- `pre-commit`：main/develop への直接コミットを禁止。ガードレール/フックの**無断変更を検知**したらコミットを止める。
- `pre-push`：main への直接push を禁止。push の前に `pytest` を実行し、**赤なら中止**。
- 変更検知の台帳：`tools/guardrail-manifest.sha256`。監視対象は `tools/guardrail-files.txt`。
  正規の変更をしたら `tools/guardrail-approve.sh` を実行して台帳を更新する（**人が意図して**行う）。
- ※ローカルフックは `--no-verify` や設定変更で外せる。だから下の②③と併用する。

### ② GitHub Actions → GitHub Issue で通知（`.github/workflows/guardrail-watch.yml`）
- push/PR でガードレール/フック/ルールのファイルが変わると、**GitHub Issue を自動作成**して通知する（サーバー側で動く＝AIが止められない）。
- Issue はオーナーに割り当てられ、**GitHubからメールで届く**。**Slack不要・外部サービス不要・追加設定不要**（`GITHUB_TOKEN` だけで動く）。
- 意図した変更なら、その Issue を閉じればよい。心当たりが無ければ内容を確認する。
- （チームで Slack に流したい場合のみ）通知ステップを Slack Incoming Webhook（Secrets の `SLACK_WEBHOOK_URL`）に差し替える。

### ③ CODEOWNERS（`.github/CODEOWNERS`）
- ガードレール/ルール/フックの変更に、オーナー（@Akimitsu-Shigemi）のレビューを必須にする土台。

## 人が1回だけ設定すること（これで“本物”になる）
GitHub → リポジトリ → **Settings → Branches → Branch protection rules** で `main` に対して：
- Require a pull request before merging（直接pushを禁止）
- Require review from Code Owners（CODEOWNERSのレビュー必須）
- Require status checks to pass（テスト/監視ワークフローの成功を必須）
- Restrict who can push / Do not allow bypassing

これで、AIがローカルで何をしても、`main` を勝手に書き換えられなくなる。

## Claude Code を使う場合の追加の締め（任意・公式ドキュメントで確認済みの要点）
`.claude/settings.json`（または管理者のマネージド設定）で：
- ネットワーク系ツールを拒否：`"permissions":{"deny":["WebFetch","WebSearch","mcp__*","Bash(curl *)","Bash(wget *)"]}`
- ルールファイルの編集を拒否：`"deny":["Edit(AGENTS.md)","Edit(CLAUDE.md)","Edit(.claude/**)","Edit(hooks/**)"]`
- サンドボックスでネットワークを許可制に：`"sandbox":{"enabled":true,"network":{"allowedDomains":["github.com"],"strictAllowlist":true}}`
- フック自体を守るには管理者設定 `"allowManagedHooksOnly":true`（ユーザー/プロジェクトのフック改変を無効化）。

> ⚠ 注意：これらを「**いま動いている作業セッション**」に効かせると、作業中のAIのネットワークや編集も止まる。
> オン/オフは意図して人が切り替えること。正確な項目はこの分野の変化が速いので、
> Claude Code 公式ドキュメント（code.claude.com/docs）で都度確認する。

## まとめ（多層で守る）
| 層 | 仕組み | AIが外せるか |
|---|---|---|
| ローカル | gitフック（コミット阻止・変更検知） | 外せる（見張り） |
| サーバー | GitHub Actions → GitHub Issue 通知（メールで届く） | **外しにくい**（workflow改変もCODEOWNERS/保護で守る） |
| サーバー | ブランチ保護＋CODEOWNERS | **外せない**（人の設定） |
| 実行環境 | Claude Code の deny/サンドボックス/マネージド設定 | 管理者設定なら外せない |
