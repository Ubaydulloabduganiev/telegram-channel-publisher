from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import asyncpg
from aiogram.types import MessageEntity


@dataclass(slots=True)
class Post:
    id: int
    user_id: int
    media_type: str
    file_id: str
    caption: str | None
    entities_json: str | None
    has_spoiler: bool
    show_caption_above_media: bool
    status: str
    scheduled_at: datetime | None
    published_message_id: int | None
    attempts: int
    last_error: str | None

    @property
    def entities(self) -> list[MessageEntity] | None:
        if not self.entities_json:
            return None
        raw = json.loads(self.entities_json)
        return [MessageEntity.model_validate(item) for item in raw]


def serialize_entities(entities: list[MessageEntity] | None) -> str | None:
    if not entities:
        return None
    return json.dumps(
        [e.model_dump(mode="json", exclude_none=True) for e in entities],
        ensure_ascii=False,
    )


def _post_from_record(row: asyncpg.Record | None) -> Post | None:
    if row is None:
        return None
    return Post(
        id=row["id"],
        user_id=row["user_id"],
        media_type=row["media_type"],
        file_id=row["file_id"],
        caption=row["caption"],
        entities_json=row["entities_json"],
        has_spoiler=row["has_spoiler"],
        show_caption_above_media=row["show_caption_above_media"],
        status=row["status"],
        scheduled_at=row["scheduled_at"],
        published_message_id=row["published_message_id"],
        attempts=row["attempts"],
        last_error=row["last_error"],
    )


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=5,
                command_timeout=15,
            )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def init_schema(self) -> None:
        await self.connect()
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS publisher_posts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
                    file_id TEXT NOT NULL,
                    caption TEXT,
                    entities_json TEXT,
                    has_spoiler BOOLEAN NOT NULL DEFAULT FALSE,
                    show_caption_above_media BOOLEAN NOT NULL DEFAULT FALSE,
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'scheduled', 'publishing',
                            'published', 'cancelled', 'failed'
                        )),
                    scheduled_at TIMESTAMPTZ,
                    published_message_id BIGINT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_publisher_posts_due
                    ON publisher_posts(status, scheduled_at);

                CREATE INDEX IF NOT EXISTS idx_publisher_posts_user
                    ON publisher_posts(user_id, status, scheduled_at);
                """
            )

    async def create_post(self, *, user_id: int, media_type: str, file_id: str, caption: str | None, entities: list[MessageEntity] | None, has_spoiler: bool, show_caption_above_media: bool) -> int:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return int(await conn.fetchval(
                """INSERT INTO publisher_posts(user_id, media_type, file_id, caption, entities_json, has_spoiler, show_caption_above_media)
                VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
                user_id, media_type, file_id, caption, serialize_entities(entities), has_spoiler, show_caption_above_media,
            ))

    async def get_post(self, post_id: int) -> Post | None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return _post_from_record(await conn.fetchrow(
                """SELECT id,user_id,media_type,file_id,caption,entities_json,has_spoiler,show_caption_above_media,status,scheduled_at,published_message_id,attempts,last_error
                FROM publisher_posts WHERE id=$1""", post_id,
            ))

    async def update_caption(self, *, post_id: int, user_id: int, caption: str, entities: list[MessageEntity] | None) -> bool:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE publisher_posts SET caption=$1, entities_json=$2, updated_at=NOW()
                WHERE id=$3 AND user_id=$4 AND status='draft'""",
                caption, serialize_entities(entities), post_id, user_id,
            )
            return result.endswith("1")

    async def schedule_post(self, *, post_id: int, user_id: int, scheduled_at: datetime) -> bool:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE publisher_posts SET status='scheduled', scheduled_at=$1, updated_at=NOW(), attempts=0, last_error=NULL
                WHERE id=$2 AND user_id=$3 AND status='draft'""",
                scheduled_at, post_id, user_id,
            )
            return result.endswith("1")

    async def cancel_post(self, *, post_id: int, user_id: int) -> bool:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE publisher_posts SET status='cancelled', updated_at=NOW()
                WHERE id=$1 AND user_id=$2 AND status IN ('draft','scheduled','failed')""",
                post_id, user_id,
            )
            return result.endswith("1")

    async def claim_immediate(self, *, post_id: int, user_id: int) -> bool:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE publisher_posts SET status='publishing', updated_at=NOW()
                WHERE id=$1 AND user_id=$2 AND status='draft'""", post_id, user_id,
            )
            return result.endswith("1")

    async def release_immediate(self, *, post_id: int, user_id: int, error: str) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE publisher_posts SET status='draft', last_error=$1, updated_at=NOW()
                WHERE id=$2 AND user_id=$3 AND status='publishing'""",
                error[:1000], post_id, user_id,
            )

    async def mark_published(self, *, post_id: int, message_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE publisher_posts SET status='published', published_message_id=$1, updated_at=NOW(), last_error=NULL WHERE id=$2""",
                message_id, post_id,
            )

    async def list_scheduled(self, *, user_id: int, limit: int = 20) -> list[Post]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id,user_id,media_type,file_id,caption,entities_json,has_spoiler,show_caption_above_media,status,scheduled_at,published_message_id,attempts,last_error
                FROM publisher_posts WHERE user_id=$1 AND status='scheduled' ORDER BY scheduled_at ASC LIMIT $2""",
                user_id, limit,
            )
            return [_post_from_record(row) for row in rows]  # type: ignore[list-item]

    async def claim_due_posts(self, *, limit: int = 20) -> list[Post]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """SELECT id FROM publisher_posts WHERE status='scheduled' AND scheduled_at <= NOW()
                    ORDER BY scheduled_at ASC FOR UPDATE SKIP LOCKED LIMIT $1""", limit,
                )
                ids = [row["id"] for row in rows]
                if not ids:
                    return []
                claimed = await conn.fetch(
                    """UPDATE publisher_posts SET status='publishing', updated_at=NOW() WHERE id = ANY($1::bigint[])
                    RETURNING id,user_id,media_type,file_id,caption,entities_json,has_spoiler,show_caption_above_media,status,scheduled_at,published_message_id,attempts,last_error""",
                    ids,
                )
                return [_post_from_record(row) for row in claimed]  # type: ignore[list-item]

    async def scheduled_publish_failed(self, *, post_id: int, error: str, max_attempts: int = 5) -> tuple[str, int]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE publisher_posts SET attempts=attempts+1,
                status=CASE WHEN attempts+1 >= $1 THEN 'failed' ELSE 'scheduled' END,
                last_error=$2, updated_at=NOW() WHERE id=$3 AND status='publishing'
                RETURNING status, attempts""",
                max_attempts, error[:1000], post_id,
            )
            if not row:
                return ("failed", max_attempts)
            return (row["status"], row["attempts"])
