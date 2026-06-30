const postgres = require('postgres');

async function initDb() {
  const connectionString = process.env.DATABASE_URL || 'postgresql://logto:logto@localhost:5432/logto';
  console.log(`[init-db] Connecting to ${connectionString.split('@')[1]}...`);
  
  const sql = postgres(connectionString, { max: 1 });

  try {
    console.log('[init-db] Creating subscriptions table...');
    await sql`
      CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        user_sub TEXT UNIQUE NOT NULL,
        plan TEXT NOT NULL,
        status TEXT NOT NULL,
        current_period_end TIMESTAMP WITH TIME ZONE,
        external_subscription_id TEXT,
        provider TEXT,
        display_name TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;

    console.log('[init-db] Creating payments table...');
    await sql`
      CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        user_sub TEXT NOT NULL,
        razorpay_event_id TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        payload JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;

    // DPDP Act 2023 — explicit consent must be recorded + demonstrable. Append-only:
    // a withdrawal inserts a new row with granted=FALSE, never a DELETE.
    console.log('[init-db] Creating consent_records table...');
    await sql`
      CREATE TABLE IF NOT EXISTS consent_records (
        id SERIAL PRIMARY KEY,
        user_sub TEXT,
        device_id TEXT,
        policy_version TEXT NOT NULL,
        consent_type TEXT NOT NULL DEFAULT 'signup',
        granted BOOLEAN NOT NULL DEFAULT TRUE,
        ip TEXT,
        user_agent TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records (user_sub)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_consent_device ON consent_records (device_id)`;

    console.log('[init-db] Creating community_posts table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_posts (
        id SERIAL PRIMARY KEY,
        user_sub TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_picture TEXT,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT 'discussion',
        score INTEGER NOT NULL DEFAULT 0,
        comment_count INTEGER NOT NULL DEFAULT 0,
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_posts_created ON community_posts (created_at DESC)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_posts_score ON community_posts (score DESC)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_posts_category ON community_posts (category)`;

    console.log('[init-db] Creating community_comments table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_comments (
        id SERIAL PRIMARY KEY,
        post_id INTEGER NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
        parent_id INTEGER REFERENCES community_comments(id) ON DELETE CASCADE,
        user_sub TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_picture TEXT,
        body TEXT NOT NULL,
        score INTEGER NOT NULL DEFAULT 0,
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_comments_post ON community_comments (post_id)`;

    console.log('[init-db] Creating community_votes table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_votes (
        id SERIAL PRIMARY KEY,
        user_sub TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        value SMALLINT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_sub, target_type, target_id)
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_votes_target ON community_votes (target_type, target_id)`;

    // Moderation flag — auto-hide on report threshold (added defensively for
    // databases created before this column existed).
    await sql`ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE`;
    await sql`ALTER TABLE community_comments ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE`;

    console.log('[init-db] Creating community_profiles table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_profiles (
        user_sub TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        picture TEXT,
        bio TEXT NOT NULL DEFAULT '',
        is_bot BOOLEAN NOT NULL DEFAULT FALSE,
        post_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      )
    `;

    console.log('[init-db] Creating community_follows table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_follows (
        follower_sub TEXT NOT NULL,
        following_sub TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (follower_sub, following_sub)
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_follows_following ON community_follows (following_sub)`;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_follows_follower ON community_follows (follower_sub)`;

    console.log('[init-db] Creating community_reports table...');
    await sql`
      CREATE TABLE IF NOT EXISTS community_reports (
        id SERIAL PRIMARY KEY,
        reporter_sub TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        resolved BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (reporter_sub, target_type, target_id)
      )
    `;
    await sql`CREATE INDEX IF NOT EXISTS idx_community_reports_target ON community_reports (target_type, target_id)`;

    // Seed the Aurom discussion bot profile.
    console.log('[init-db] Seeding Aurom bot profile...');
    await sql`
      INSERT INTO community_profiles (user_sub, display_name, picture, bio, is_bot)
      VALUES (
        'bot:aurom',
        'Aurom',
        '/aurom-avatar.svg',
        'I am Aurom — a humble keeper of discussion. Each day I bring a thread from the teachings of Guruji Sri Shailendra Sharma and the eternal texts, and ask how it lives in our world today.',
        TRUE
      )
      ON CONFLICT (user_sub) DO NOTHING
    `;

    console.log('[init-db] Database initialization complete.');
  } catch (err) {
    console.error('[init-db] Failed to initialize database:', err);
    process.exit(1);
  } finally {
    await sql.end();
  }
}

initDb();
