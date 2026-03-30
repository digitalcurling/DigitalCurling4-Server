import json
import logging
from typing import List, AsyncGenerator
from uuid import UUID
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.crud import ReadData, UpdateData
from src.models.schema_models import StateSchema, MatchDataSchema
from src.models.dc_models import StateModel
from src.converter import DataConverter

HEART_BEAT = 30

logging.basicConfig(level=logging.INFO)

read_data = ReadData()
update_data = UpdateData()
data_converter = DataConverter()


class RedisSubscriber:
    """Redis subscriber class to handle SSE events."""

    def __init__(
        self, Session: async_sessionmaker, match_id: str, match_team_name: str
    ):
        """Initialize RedisSubscriber with session, match_id and match_team_name."""
        self.match_id: str = match_id
        self.Session: async_sessionmaker = Session
        self.match_team_name: str = match_team_name

    async def event_generator(self, channel: str, redis: Redis) -> AsyncGenerator[str, None]:
        """SSE event generator.

        This stream has two phases:
        1) Initial sync
           - viewer: send only the latest board once
           - player(team0/team1): wait for (a) both clients connected and (b) both teams configured,
             then replay all states of the current end so both clients start from the same board.
        2) Normal streaming: on each state_update publish, send the latest board.
        """
        pubsub = redis.pubsub()
        presence_key_self: str | None = None
        presence_ttl_seconds = HEART_BEAT * 3

        await pubsub.subscribe(channel)

        try:
            # ---- Initial sync ----
            if self.match_team_name == "viewer":
                async for message in self._initial_sync_for_viewer():
                    yield message
            else:
                presence_key_self = f"match:{self.match_id}:presence:{self.match_team_name}"
                async for message in self._initial_sync_for_player(
                    channel=channel,
                    redis=redis,
                    pubsub=pubsub,
                    presence_key_self=presence_key_self,
                    presence_ttl_seconds=presence_ttl_seconds,
                ):
                    yield message

            # ---- Normal streaming ----
            async for message in self._stream_latest_updates(
                redis=redis,
                pubsub=pubsub,
                presence_key_self=presence_key_self,
                presence_ttl_seconds=presence_ttl_seconds,
            ):
                yield message

        finally:
            logging.info("Unsubscribing from channel")
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            if presence_key_self is not None:
                await redis.delete(presence_key_self)


    async def _initial_sync_for_viewer(self) -> AsyncGenerator[str, None]:
        """Viewer initial sync.

        Behavior:
        - Determine the current end by reading the latest state.
        - Fetch all state rows in that end and replay them in order.
          Earlier states are sent as `state_update`, and the last as `latest_state_update`.
        - Viewer does not participate in presence/initial barrier coordination.

        Note: Unlike player initial sync, viewer must not mutate DB state.
        """
        async with self.Session() as session:
            match_data: MatchDataSchema | None = await read_data.read_match_data(self.match_id, session)
            latest_state_data: StateSchema | None = await read_data.read_latest_state_data(
                self.match_id, session
            )

        # Viewer can connect before the first state row exists.
        # Keep the SSE connection alive until we can send a proper board.
        if match_data is None or latest_state_data is None:
            yield ": ping\n\n"
            return

        # Replay all states of the current end.
        async with self.Session() as session:
            state_data_in_end = await read_data.read_state_data_in_end(
                self.match_id, latest_state_data.end_number, session
            )

        if not state_data_in_end:
            # Fallback: if the end history query returns nothing, at least send the latest board.
            async with self.Session() as session:
                shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                    latest_state_data.state_id, session
                )
            latest_state_model: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, latest_state_data, shot_info_data
            )
            payload = json.dumps(latest_state_model.model_dump())
            yield f"event: latest_state_update\ndata: {payload}\n\n"
            return

        sorted_states = self._sort_states_for_replay(state_data_in_end)
        for i, state_schema in enumerate(sorted_states):
            async with self.Session() as session:
                shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                    state_schema.state_id, session
                )

            state_model: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, state_schema, shot_info_data
            )
            payload = json.dumps(state_model.model_dump())

            if i == len(sorted_states) - 1:
                yield f"event: latest_state_update\ndata: {payload}\n\n"
            else:
                yield f"event: state_update\ndata: {payload}\n\n"


    @staticmethod
    def _sort_states_for_replay(states: List[StateSchema]) -> List[StateSchema]:
        """Stable sort for replay.

        We primarily sort by team_shot_number. Because team_shot_number may be None (mixed doubles)
        or duplicated in some flows, we use created_at and state_id as tie-breakers.
        """
        def key_fn(s: StateSchema) -> tuple[int, int, str]:
            # None should come first in a replay (e.g., pre-setup states).
            shot_key = -1 if s.team_shot_number is None else int(s.team_shot_number)
            created_key = int(s.created_at.timestamp()) if getattr(s, "created_at", None) else 0
            return (shot_key, created_key, str(s.state_id))

        return sorted(list(states), key=key_fn)


    async def _initial_sync_for_player(
        self,
        *,
        channel: str,
        redis: Redis,
        pubsub,
        presence_key_self: str,
        presence_ttl_seconds: int,
    ) -> AsyncGenerator[str, None]:
        """Player initial sync.

        A player stream joins a coordination barrier:
        - presence keys indicate both streams are connected
        - team_config keys indicate both teams have configured
        Once both are satisfied, one subscriber publishes an "initial_sync" message.
        Upon receiving it, we replay state history for the current end.
        """
        presence_key_team0 = f"match:{self.match_id}:presence:team0"
        presence_key_team1 = f"match:{self.match_id}:presence:team1"

        config_key_team0 = f"match:{self.match_id}:team_config:team0"
        config_key_team1 = f"match:{self.match_id}:team_config:team1"

        await redis.set(presence_key_self, "1", ex=presence_ttl_seconds)
        await redis.publish(
            channel,
            json.dumps(
                {
                    "type": "presence_updated",
                    "match_id": str(self.match_id),
                    "team": self.match_team_name,
                }
            ),
        )

        # If Redis was restarted, team_config keys may be missing even though DB is configured.
        async with self.Session() as session:
            match_data = await read_data.read_match_data(self.match_id, session)
        if (
            match_data is not None
            and match_data.first_team_name is not None
            and match_data.second_team_name is not None
        ):
            await redis.set(config_key_team0, "1", ex=60 * 60 * 24)
            await redis.set(config_key_team1, "1", ex=60 * 60 * 24)

        waiting_for_initial_sync_signal = True

        while True:
            await redis.expire(presence_key_self, presence_ttl_seconds)

            config_count = await redis.exists(config_key_team0, config_key_team1)
            both_teams_configured = config_count == 2

            presence_count = await redis.exists(presence_key_team0, presence_key_team1)
            both_streams_connected = presence_count == 2

            if both_teams_configured and both_streams_connected and waiting_for_initial_sync_signal:
                # One of the subscribers emits an "initial_sync" signal.
                signal_lock_key = f"match:{self.match_id}:initial_sync:signal_lock"
                acquired = await redis.set(signal_lock_key, "1", nx=True, ex=5)
                if acquired:
                    await redis.publish(
                        channel,
                        json.dumps({"type": "initial_sync", "match_id": str(self.match_id)}),
                    )
                waiting_for_initial_sync_signal = False

            msg = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=HEART_BEAT
            )
            if msg is None:
                # Keep the SSE connection alive while waiting for the barrier.
                yield ": ping\n\n"
                continue

            if msg.get("type") != "message":
                continue

            msg_type = self._extract_message_type(msg)
            if msg_type != "initial_sync":
                continue

            async for replay_message in self._replay_current_end_states(redis=redis):
                yield replay_message
            break


    async def _replay_current_end_states(self, *, redis: Redis) -> AsyncGenerator[str, None]:
        """Replay all states for the current end as SSE messages."""
        state_data_in_end: List[StateSchema] = []
        async with self.Session() as session:
            latest_state_data: StateSchema = await read_data.read_latest_state_data(
                self.match_id, session
            )
            if latest_state_data is None:
                return
            if latest_state_data.end_number == 0 and latest_state_data.total_shot_number in (None, 0):
                start_lock_key = f"match:{self.match_id}:initial_state_start_time_set"
                acquired = await redis.set(start_lock_key, "1", nx=True, ex=60 * 60 * 24)
                if acquired:
                    await update_data.update_created_at_state_data(
                        latest_state_data.state_id, session
                    )
            state_data_in_end = await read_data.read_state_data_in_end(
                self.match_id, latest_state_data.end_number, session
            )

        for i in range(len(state_data_in_end)):
            async with self.Session() as session:
                match_data = await read_data.read_match_data(self.match_id, session)
                shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                    state_data_in_end[i].state_id, session
                )
            if match_data is None:
                continue

            state_data: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, state_data_in_end[i], shot_info_data
            )
            payload = json.dumps(state_data.model_dump())
            logging.debug(f"Payload: {payload}")
            if i == len(state_data_in_end) - 1:
                yield f"event: latest_state_update\ndata: {payload}\n\n"
            else:
                yield f"event: state_update\ndata: {payload}\n\n"


    async def _stream_latest_updates(
        self,
        *,
        redis: Redis,
        pubsub,
        presence_key_self: str | None,
        presence_ttl_seconds: int,
    ) -> AsyncGenerator[str, None]:
        """Normal streaming loop.

        Ignores coordination messages and streams only the latest state.
        """
        while True:
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=HEART_BEAT
            )

            if presence_key_self is not None:
                await redis.expire(presence_key_self, presence_ttl_seconds)

            if msg is None:
                yield ": ping\n\n"
                continue

            if msg.get("type") != "message":
                continue

            published_state_id, msg_type = self._extract_state_id_and_type(msg)

            # Coordination/control messages are ignored during normal streaming.
            if msg_type in {"presence_updated", "team_config_updated", "initial_sync", "__internal_replay__"}:
                continue

            async with self.Session() as session:
                match_data = await read_data.read_match_data(self.match_id, session)

                latest_state_data: StateSchema | None = None
                if published_state_id is not None:
                    latest_state_data = await read_data.read_state_data(published_state_id, session)
                if latest_state_data is None:
                    latest_state_data = await read_data.read_latest_state_data(self.match_id, session)

                shot_info_data = None
                if latest_state_data is not None:
                    shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                        latest_state_data.state_id, session
                    )

            # If DB is not ready (e.g., state row not created yet), do not crash the stream.
            if match_data is None or latest_state_data is None:
                yield ": ping\n\n"
                continue

            latest_state_model: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, latest_state_data, shot_info_data
            )
            payload = json.dumps(latest_state_model.model_dump())
            yield f"event: latest_state_update\ndata: {payload}\n\n"


    def _extract_message_type(self, msg: dict) -> str | None:
        try:
            raw = msg.get("data")
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            if isinstance(raw, str):
                parsed = json.loads(raw)
                return parsed.get("type")
        except Exception:
            return None
        return None


    def _extract_state_id_and_type(self, msg: dict) -> tuple[UUID | None, str | None]:
        published_state_id: UUID | None = None
        msg_type: str | None = None
        try:
            raw = msg.get("data")
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            if isinstance(raw, str):
                parsed = json.loads(raw)
                msg_type = parsed.get("type")
                state_id_str = parsed.get("state_id")
                if state_id_str:
                    published_state_id = UUID(str(state_id_str))
        except Exception:
            return None, None
        return published_state_id, msg_type
