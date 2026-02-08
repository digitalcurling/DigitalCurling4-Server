from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from src.converter import DataConverter
from src.models.schema_models import (
    MatchDataSchema,
    MatchMixDoublesSettingsSchema,
    ScoreSchema,
    StateSchema,
    StoneCoordinateSchema,
)


def _build_minimal_match_data(*, end_setup_team_ids: list, team0_id: UUID, team1_id: UUID) -> MatchDataSchema:
    return MatchDataSchema(
        match_id=UUID("00000000-0000-0000-0000-000000000001"),
        first_team_name="A",
        second_team_name="B",
        first_team_id=team0_id,
        first_team_player1_id=UUID("00000000-0000-0000-0000-000000000011"),
        first_team_player2_id=UUID("00000000-0000-0000-0000-000000000012"),
        second_team_id=team1_id,
        second_team_player1_id=UUID("00000000-0000-0000-0000-000000000021"),
        second_team_player2_id=UUID("00000000-0000-0000-0000-000000000022"),
        winner_team_id=None,
        score_id=UUID("00000000-0000-0000-0000-000000000002"),
        time_limit=300.0,
        extra_end_time_limit=30.0,
        standard_end_count=8,
        physical_simulator_id=UUID("00000000-0000-0000-0000-000000000003"),
        applied_rule=2,
        tournament_id=UUID("00000000-0000-0000-0000-000000000004"),
        match_name="test",
        game_mode="mix_doubles",
        created_at=datetime.now(),
        started_at=datetime.now(),
        score=ScoreSchema(score_id=UUID("00000000-0000-0000-0000-000000000002"), team0=[0] * 9, team1=[0] * 9),
        mix_doubles_settings=MatchMixDoublesSettingsSchema(
            positioned_stones_pattern=0,
            team0_power_play_end=None,
            team1_power_play_end=None,
            end_setup_team_ids=end_setup_team_ids,
        ),
    )


def _build_pre_end_setup_state(*, end_number: int) -> StateSchema:
    stone_coordinate = StoneCoordinateSchema(
        stone_coordinate_id=UUID("00000000-0000-0000-0000-000000000010"),
        data={
            "team0": [{"x": 0.0, "y": 0.0} for _ in range(6)],
            "team1": [{"x": 0.0, "y": 0.0} for _ in range(6)],
        },
    )
    return StateSchema(
        state_id=UUID("00000000-0000-0000-0000-000000000020"),
        winner_team_id=None,
        match_id=UUID("00000000-0000-0000-0000-000000000001"),
        end_number=end_number,
        shot_number=None,
        total_shot_number=None,
        first_team_remaining_time=300.0,
        second_team_remaining_time=300.0,
        first_team_extra_end_remaining_time=30.0,
        second_team_extra_end_remaining_time=30.0,
        stone_coordinate_id=stone_coordinate.stone_coordinate_id,
        score_id=UUID("00000000-0000-0000-0000-000000000002"),
        shot_id=None,
        next_shot_team_id=None,
        created_at=datetime.now(),
        stone_coordinate=stone_coordinate,
        score=ScoreSchema(score_id=UUID("00000000-0000-0000-0000-000000000002"), team0=[0] * 9, team1=[0] * 9),
    )


def test_converter_end_setup_team_uses_end_setup_team_ids_uuid_string_ok():
    team0_id = UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17")
    team1_id = UUID("60e1e056-3613-4846-afc9-514ea7b6adde")

    # JSONB commonly returns UUIDs as strings.
    match_data = _build_minimal_match_data(
        end_setup_team_ids=[str(team0_id), str(team1_id)],
        team0_id=team0_id,
        team1_id=team1_id,
    )
    state_data = _build_pre_end_setup_state(end_number=1)

    model = DataConverter().convert_stateschema_to_statemodel(match_data, state_data)
    assert model.mix_doubles_settings is not None
    assert model.mix_doubles_settings.end_setup_team == "team1"


def test_converter_end_setup_team_defaults_to_team1_when_missing_ids():
    team0_id = UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17")
    team1_id = UUID("60e1e056-3613-4846-afc9-514ea7b6adde")

    match_data = _build_minimal_match_data(
        end_setup_team_ids=[],
        team0_id=team0_id,
        team1_id=team1_id,
    )
    state_data = _build_pre_end_setup_state(end_number=0)

    model = DataConverter().convert_stateschema_to_statemodel(match_data, state_data)
    assert model.mix_doubles_settings is not None
    assert model.mix_doubles_settings.end_setup_team == "team1"


def test_converter_end_setup_team_out_of_range_uses_default_team1():
    team0_id = UUID("5050f20f-cf97-4fb1-bbc1-f2c9052e0d17")
    team1_id = UUID("60e1e056-3613-4846-afc9-514ea7b6adde")

    match_data = _build_minimal_match_data(
        end_setup_team_ids=[str(team0_id)],
        team0_id=team0_id,
        team1_id=team1_id,
    )
    state_data = _build_pre_end_setup_state(end_number=3)

    model = DataConverter().convert_stateschema_to_statemodel(match_data, state_data)
    assert model.mix_doubles_settings is not None
    assert model.mix_doubles_settings.end_setup_team == "team1"
