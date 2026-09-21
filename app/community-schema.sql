PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS community_tasks(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reference TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('low','normal','high','urgent')),
  state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','pending_acceptance','in_progress','review','closed')),
  creator INTEGER NOT NULL REFERENCES users(id),
  assignee INTEGER REFERENCES users(id),
  due_date TEXT,
  deliverable TEXT NOT NULL DEFAULT '',
  deliverable_version INTEGER NOT NULL DEFAULT 0,
  deliverable_submitted TEXT,
  created TEXT NOT NULL,
  updated TEXT NOT NULL,
  closed TEXT,
  closed_by INTEGER REFERENCES users(id),
  close_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS community_task_events(
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES community_tasks(id),
  actor INTEGER REFERENCES users(id),
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_task_reviews(
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES community_tasks(id),
  deliverable_version INTEGER NOT NULL,
  reviewer INTEGER NOT NULL REFERENCES users(id),
  decision TEXT NOT NULL CHECK(decision IN ('approve','changes')),
  comment TEXT NOT NULL,
  created TEXT NOT NULL,
  UNIQUE(task_id,deliverable_version,reviewer)
);

CREATE TABLE IF NOT EXISTS community_notifications(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  task_id INTEGER REFERENCES community_tasks(id),
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  href TEXT NOT NULL,
  dedupe_key TEXT NOT NULL,
  read_at TEXT,
  created TEXT NOT NULL,
  UNIQUE(user_id,dedupe_key)
);

CREATE TABLE IF NOT EXISTS community_activities(
  id INTEGER PRIMARY KEY,
  activity_type TEXT NOT NULL CHECK(activity_type IN ('dinamica','evento')),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reference TEXT NOT NULL DEFAULT '',
  starts_at TEXT,
  ends_at TEXT,
  location TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','completed','cancelled')),
  pending_details TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL,
  updated TEXT NOT NULL,
  updated_by INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS community_calls(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  copy TEXT NOT NULL,
  reference TEXT NOT NULL DEFAULT '',
  image_path TEXT NOT NULL DEFAULT '',
  exclusive_channel TEXT NOT NULL DEFAULT '',
  publish_at TEXT NOT NULL,
  starts_at TEXT,
  valid_until TEXT,
  permanent INTEGER NOT NULL DEFAULT 0 CHECK(permanent IN (0,1)),
  creator INTEGER NOT NULL REFERENCES users(id),
  created TEXT NOT NULL,
  updated TEXT NOT NULL,
  updated_by INTEGER NOT NULL REFERENCES users(id),
  CHECK(permanent=0 OR valid_until IS NULL)
);

CREATE TABLE IF NOT EXISTS community_comments(
  id INTEGER PRIMARY KEY,
  target_type TEXT NOT NULL CHECK(target_type IN ('task','activity','call','rolita')),
  target_id INTEGER NOT NULL,
  author INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_community_tasks_state ON community_tasks(state,priority,updated);
CREATE INDEX IF NOT EXISTS idx_community_task_events ON community_task_events(task_id,id);
CREATE INDEX IF NOT EXISTS idx_community_task_reviews ON community_task_reviews(task_id,deliverable_version,id);
CREATE INDEX IF NOT EXISTS idx_community_notifications ON community_notifications(user_id,read_at,id);
CREATE INDEX IF NOT EXISTS idx_community_activities ON community_activities(starts_at,id);
CREATE INDEX IF NOT EXISTS idx_community_calls ON community_calls(publish_at,id);
CREATE INDEX IF NOT EXISTS idx_community_comments ON community_comments(target_type,target_id,id);
