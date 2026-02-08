from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

try:
    from src.main import app
except ModuleNotFoundError as e:
    # On Windows, the native simulator extension may be unavailable until
    # `src/simulator.pyd` is provided. Skip these API tests in that case.
    if "src.simulator" in str(e):
        pytest.skip("Native simulator module missing (src.simulator).", allow_module_level=True)
    raise
from src.models.dc_models import PositionedStonesModel, GameModeModel
from src.models.schema_models import (
    MatchDataSchema,
    MatchMixDoublesSettingsSchema,
    ScoreSchema,
    StateSchema,
    StoneCoordinateSchema,
)


def _match_data(*, game_mode: str) -> MatchDataSchema:
    match_id = UUID("00000000-0000-0000-0000-000000000101")
    team0_id = UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17")
    team1_id = UUID("60e1e056-3613-4846-afc9-514ea7b6adde")
    score_id = UUID("00000000-0000-0000-0000-000000000102")

    return MatchDataSchema(
        match_id=match_id,
        first_team_name="A",
        second_team_name="B",
        first_team_id=team0_id,
        first_team_player1_id=UUID("00000000-0000-0000-0000-000000000111"),
        first_team_player2_id=UUID("00000000-0000-0000-0000-000000000112"),
        second_team_id=team1_id,
        second_team_player1_id=UUID("00000000-0000-0000-0000-000000000121"),
        second_team_player2_id=UUID("00000000-0000-0000-0000-000000000122"),
        winner_team_id=None,
        score_id=score_id,
        time_limit=300.0,
        extra_end_time_limit=30.0,
        standard_end_count=8,
        physical_simulator_id=UUID("00000000-0000-0000-0000-000000000103"),
        applied_rule=2,
        tournament_id=UUID("00000000-0000-0000-0000-000000000104"),
        match_name="test",
        game_mode=game_mode,
        created_at=datetime.now(),
        started_at=datetime.now(),
        score=ScoreSchema(score_id=score_id, team0=[0] * 9, team1=[0] * 9),
        mix_doubles_settings=(
            MatchMixDoublesSettingsSchema(
                positioned_stones_pattern=0,
                team0_power_play_end=None,
                team1_power_play_end=None,
                end_setup_team_ids=[team1_id],
            )
            if game_mode == GameModeModel.mix_doubles.value
            else None
        ),
    )


def _latest_state(*, match_id: UUID, started: bool, winner_team_id: UUID | None = None) -> StateSchema:
    stone_coordinate = StoneCoordinateSchema(
        stone_coordinate_id=UUID("00000000-0000-0000-0000-000000000210"),
        data={
            "team0": [{"x": 0.0, "y": 0.0} for _ in range(6)],
            "team1": [{"x": 0.0, "y": 0.0} for _ in range(6)],
        },
    )
    return StateSchema(
        state_id=UUID("00000000-0000-0000-0000-000000000220"),
        winner_team_id=winner_team_id,
        match_id=match_id,
        end_number=0,
        shot_number=0 if started else None,
        total_shot_number=0 if started else None,
        first_team_remaining_time=300.0,
        second_team_remaining_time=300.0,
        first_team_extra_end_remaining_time=30.0,
        second_team_extra_end_remaining_time=30.0,
        stone_coordinate_id=stone_coordinate.stone_coordinate_id,
        score_id=UUID("00000000-0000-0000-0000-000000000102"),
        shot_id=None,
        next_shot_team_id=UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17") if started else None,
        created_at=datetime.now(),
        stone_coordinate=stone_coordinate,
        score=ScoreSchema(score_id=UUID("00000000-0000-0000-0000-000000000102"), team0=[0] * 9, team1=[0] * 9),
    )


def test_end_setup_rejects_standard_mode(monkeypatch: pytest.MonkeyPatch):
    md = _match_data(game_mode=GameModeModel.standard.value)
    latest = _latest_state(match_id=md.match_id, started=False)

    async def fake_check_match_data(*args, **kwargs):
        return "team0"

    async def fake_read_match_data(match_id):
        return md

    async def fake_read_latest_state_data(match_id):
        return latest

    monkeypatch.setattr("src.routers.match.basic_auth.check_match_data", fake_check_match_data)
    monkeypatch.setattr("src.services.match_db.read_match_data", fake_read_match_data)
    monkeypatch.setattr("src.services.match_db.read_latest_state_data", fake_read_latest_state_data)

    client = TestClient(app)
    res = client.post(f"/matches/{md.match_id}/end-setup", params={"request": PositionedStonesModel.center_house})
    assert res.status_code == 400


def test_end_setup_conflict_if_end_already_started(monkeypatch: pytest.MonkeyPatch):
    md = _match_data(game_mode=GameModeModel.mix_doubles.value)
    latest = _latest_state(match_id=md.match_id, started=True)

    async def fake_check_match_data(*args, **kwargs):
        return "team0"

    async def fake_read_match_data(match_id):
        return md

    async def fake_read_latest_state_data(match_id):
        return latest

    monkeypatch.setattr("src.routers.match.basic_auth.check_match_data", fake_check_match_data)
    monkeypatch.setattr("src.services.match_db.read_match_data", fake_read_match_data)
    monkeypatch.setattr("src.services.match_db.read_latest_state_data", fake_read_latest_state_data)

    client = TestClient(app)
    res = client.post(f"/matches/{md.match_id}/end-setup", params={"request": PositionedStonesModel.center_house})
    assert res.status_code == 409
    assert "End already started" in res.text


def test_end_setup_calls_service_and_publishes_state(monkeypatch: pytest.MonkeyPatch):
    md = _match_data(game_mode=GameModeModel.mix_doubles.value)
    latest = _latest_state(match_id=md.match_id, started=False)
    setup_state_id = UUID("00000000-0000-0000-0000-000000000999")

    async def fake_check_match_data(*args, **kwargs):
        return "team0"

    async def fake_read_match_data(match_id):
        return md

    async def fake_read_latest_state_data(match_id):
        return latest

    async def fake_perform_mix_doubles_end_setup(**kwargs):
        return setup_state_id

    published = {}

    async def fake_publish(channel, payload):
        published["channel"] = channel
        published["payload"] = payload

    monkeypatch.setattr("src.routers.match.basic_auth.check_match_data", fake_check_match_data)
    monkeypatch.setattr("src.services.match_db.read_match_data", fake_read_match_data)
    monkeypatch.setattr("src.services.match_db.read_latest_state_data", fake_read_latest_state_data)
    monkeypatch.setattr("src.services.match_db.perform_mix_doubles_end_setup", fake_perform_mix_doubles_end_setup)
    monkeypatch.setattr("src.routers.match.redis.publish", fake_publish)

    client = TestClient(app)
    res = client.post(f"/matches/{md.match_id}/end-setup", params={"request": PositionedStonesModel.center_house})
    assert res.status_code == 200
    assert published.get("channel") == f"match:{md.match_id}"
