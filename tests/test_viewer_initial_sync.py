import asyncio
from datetime import datetime
from uuid import UUID

import pytest

import src.redis_subscriber as redis_subscriber
from src.redis_subscriber import RedisSubscriber
from src.models.schema_models import MatchDataSchema, StateSchema


class _AsyncSessionCtx:
    def __init__(self, session_obj=None):
        self._session_obj = session_obj

    async def __aenter__(self):
        return self._session_obj

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSessionMaker:
    def __call__(self):
        return _AsyncSessionCtx(session_obj=object())


class _FakeStateModel:
    def __init__(self, payload: dict):
        self._payload = payload

    def model_dump(self):
        return self._payload


def _make_match(match_id: UUID) -> MatchDataSchema:
    now = datetime(2026, 3, 4, 0, 0, 0)
    return MatchDataSchema(
        match_id=match_id,
        first_team_name="A",
        second_team_name="B",
        first_team_id=UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17"),
        first_team_player1_id=UUID("006951d4-37b2-48eb-85a2-af9463a1e7aa"),
        first_team_player2_id=UUID("006951d4-37b2-48eb-85a2-af9463a1e7aa"),
        second_team_id=UUID("60e1e056-3613-4846-afc9-514ea7b6adde"),
        second_team_player1_id=UUID("0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0"),
        second_team_player2_id=UUID("0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0"),
        winner_team_id=None,
        score_id=UUID("11111111-1111-1111-1111-111111111111"),
        time_limit=600.0,
        extra_end_time_limit=60.0,
        standard_end_count=8,
        physical_simulator_id=UUID("22222222-2222-2222-2222-222222222222"),
        applied_rule=0,
        tournament_id=UUID("33333333-3333-3333-3333-333333333333"),
        match_name="m",
        game_mode="standard",
        created_at=now,
        started_at=now,
    )


def _make_state(match_id: UUID, state_id: UUID, end_number: int, team_shot_number: int | None, created_at: datetime) -> StateSchema:
    return StateSchema(
        state_id=state_id,
        winner_team_id=None,
        match_id=match_id,
        end_number=end_number,
        team_shot_number=team_shot_number,
        total_shot_number=0,
        first_team_remaining_time=600.0,
        second_team_remaining_time=600.0,
        first_team_extra_end_remaining_time=60.0,
        second_team_extra_end_remaining_time=60.0,
        stone_coordinate_id=UUID("44444444-4444-4444-4444-444444444444"),
        score_id=UUID("11111111-1111-1111-1111-111111111111"),
        shot_id=None,
        next_shot_team_id=None,
        created_at=created_at,
        stone_coordinate=None,
        score=None,
    )


def test_viewer_initial_sync_replays_states_in_order(monkeypatch: pytest.MonkeyPatch):
    match_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    match_data = _make_match(match_id)

    # Intentionally out-of-order.
    s1 = _make_state(match_id, UUID("00000000-0000-0000-0000-000000000001"), end_number=2, team_shot_number=0, created_at=datetime(2026, 3, 4, 0, 0, 2))
    s2 = _make_state(match_id, UUID("00000000-0000-0000-0000-000000000002"), end_number=2, team_shot_number=None, created_at=datetime(2026, 3, 4, 0, 0, 1))
    s3 = _make_state(match_id, UUID("00000000-0000-0000-0000-000000000003"), end_number=2, team_shot_number=1, created_at=datetime(2026, 3, 4, 0, 0, 3))

    latest = s3

    async def _read_match_data(_match_id, _session):
        return match_data

    async def _read_latest_state_data(_match_id, _session):
        return latest

    async def _read_state_data_in_end(_match_id, _end_number, _session):
        return [s1, s3, s2]

    async def _read_last_shot_info_by_post_state_id(_state_id, _session):
        return None

    def _convert_stateschema_to_statemodel(_match_data, state_schema, _shot_info):
        return _FakeStateModel(
            {
                "state_id": str(state_schema.state_id),
                "team_shot_number": state_schema.team_shot_number,
            }
        )

    monkeypatch.setattr(redis_subscriber.read_data, "read_match_data", _read_match_data)
    monkeypatch.setattr(redis_subscriber.read_data, "read_latest_state_data", _read_latest_state_data)
    monkeypatch.setattr(redis_subscriber.read_data, "read_state_data_in_end", _read_state_data_in_end)
    monkeypatch.setattr(redis_subscriber.read_data, "read_last_shot_info_by_post_state_id", _read_last_shot_info_by_post_state_id)
    monkeypatch.setattr(redis_subscriber.data_converter, "convert_stateschema_to_statemodel", _convert_stateschema_to_statemodel)

    subscriber = RedisSubscriber(_FakeSessionMaker(), match_id=str(match_id), match_team_name="viewer")

    async def _collect():
        return [msg async for msg in subscriber._initial_sync_for_viewer()]

    messages = asyncio.run(_collect())

    assert len(messages) == 3
    assert messages[0].startswith("event: state_update")
    assert messages[1].startswith("event: state_update")
    assert messages[2].startswith("event: latest_state_update")

    # Ensure ordering: team_shot_number None first, then 0, then 1.
    assert "00000000-0000-0000-0000-000000000002" in messages[0]
    assert "00000000-0000-0000-0000-000000000001" in messages[1]
    assert "00000000-0000-0000-0000-000000000003" in messages[2]


def test_viewer_initial_sync_ping_when_db_not_ready(monkeypatch: pytest.MonkeyPatch):
    match_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    async def _read_match_data(_match_id, _session):
        return None

    async def _read_latest_state_data(_match_id, _session):
        return None

    monkeypatch.setattr(redis_subscriber.read_data, "read_match_data", _read_match_data)
    monkeypatch.setattr(redis_subscriber.read_data, "read_latest_state_data", _read_latest_state_data)

    subscriber = RedisSubscriber(_FakeSessionMaker(), match_id=str(match_id), match_team_name="viewer")

    async def _collect():
        return [msg async for msg in subscriber._initial_sync_for_viewer()]

    messages = asyncio.run(_collect())
    assert messages == [": ping\n\n"]
