-- 役割つきユーザー（パスワードはハッシュで保存）
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student','parent','teacher','admin')),
    name          TEXT NOT NULL
);

-- 生徒の属性。user_id は role='student' のusers.id
CREATE TABLE IF NOT EXISTS students (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id),
    highschool    TEXT NOT NULL,         -- 出身高校（今治市の高校。表示用）
    school        TEXT NOT NULL          -- 第一志望（大学・学部）
);

-- 保護者と生徒の対応（保護者は自分の子のみ閲覧可）
CREATE TABLE IF NOT EXISTS parent_child (
    parent_id     INTEGER NOT NULL REFERENCES users(id),
    student_id    INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (parent_id, student_id)
);

-- 成績（5教科 × 複数回）
CREATE TABLE IF NOT EXISTS scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES users(id),
    exam          TEXT NOT NULL,         -- 例: 2026-04
    subject       TEXT NOT NULL,         -- kokugo/sugaku/eigo/rika/shakai
    score         INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    -- 同じ生徒・回・教科は1行だけ（点数入力は上書き更新する）
    UNIQUE (student_id, exam, subject)
);

-- 監査ログ（誰が・いつ・何を）
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,         -- ISO時刻
    actor         TEXT,                  -- username（未ログインはNULL）
    action        TEXT NOT NULL,         -- login_success / login_fail / view_admin など
    detail        TEXT
);
