from pydantic import BaseModel, ConfigDict, Json, Field
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime


class TournamentSchema(BaseModel):
    tournament_id: UUID
    tournament_name: str

    model_config = ConfigDict(from_attributes=True)


class PhysicalSimulatorSchema(BaseModel):
    physical_simulator_id: UUID
    simulator_name: str

    model_config = ConfigDict(from_attributes=True)


class PlayerSchema(BaseModel):
    player_id: UUID
    team_id: UUID
    max_velocity: float
    shot_std_dev: float
    angle_std_dev: float
    player_name: str

    model_config = ConfigDict(from_attributes=True)


class TrajectorySchema(BaseModel):
    trajectory_id: UUID
    trajectory_data: Json


class StoneCoordinateSchema(BaseModel):
    stone_coordinate_id: UUID
    data: dict

    model_config = ConfigDict(from_attributes=True)


class ScoreSchema(BaseModel):
    score_id: UUID
    team0: list
    team1: list

    model_config = ConfigDict(from_attributes=True)


class ShotInfoSchema(BaseModel):
    shot_id: UUID
    player_id: UUID
    team_id: UUID
    trajectory_id: UUID
    pre_shot_state_id: UUID
    post_shot_state_id: UUID
    actual_translational_velocity: float
    actual_shot_angle: float
    translational_velocity: float
    angular_velocity: float
    shot_angle: float

    model_config = ConfigDict(from_attributes=True)


class StateSchema(BaseModel):
    state_id: UUID
    winner_team_id: UUID | None
    match_id: UUID
    end_number: int
    shot_number: int | None
    total_shot_number: int | None
    first_team_remaining_time: float
    second_team_remaining_time: float
    first_team_extra_end_remaining_time: float
    second_team_extra_end_remaining_time: float
    stone_coordinate_id: UUID
    score_id: UUID
    shot_id: UUID | None
    next_shot_team_id: UUID | None
    created_at: datetime
    stone_coordinate: Optional[StoneCoordinateSchema] = None
    score: Optional[ScoreSchema] = None

    model_config = ConfigDict(from_attributes=True)


class MatchMixDoublesSettingsSchema(BaseModel):
    positioned_stones_pattern: int
    team0_power_play_end: int | None = None
    team1_power_play_end: int | None = None
    end_setup_team_ids: list[UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MatchDataSchema(BaseModel):
    match_id: UUID
    first_team_name: str | None
    second_team_name: str | None
    first_team_id: UUID
    first_team_player1_id: UUID
    first_team_player2_id: UUID
    # Mixed doubles uses only 2 players per team.
    first_team_player3_id: UUID | None = None
    first_team_player4_id: UUID | None = None
    second_team_id: UUID
    second_team_player1_id: UUID
    second_team_player2_id: UUID
    second_team_player3_id: UUID | None = None
    second_team_player4_id: UUID | None = None
    winner_team_id: UUID | None
    score_id: UUID
    time_limit: float
    extra_end_time_limit: float
    standard_end_count: int
    physical_simulator_id: UUID
    applied_rule: int
    tournament_id: UUID
    match_name: str
    game_mode: Literal["standard", "mix_doubles"] = "standard"
    created_at: datetime
    started_at: datetime
    score: Optional[ScoreSchema] = None
    tournament: Optional[TournamentSchema] = None
    simulator: Optional[PhysicalSimulatorSchema] = None
    mix_doubles_settings: Optional[MatchMixDoublesSettingsSchema] = None

    model_config = ConfigDict(from_attributes=True)


class TeamSchema(BaseModel):
    player1_id: UUID
    player2_id: UUID
    player3_id: UUID
    player4_id: UUID
    team_name: str
    player1: Optional[PlayerSchema] = None
    player2: Optional[PlayerSchema] = None
    player3: Optional[PlayerSchema] = None
    player4: Optional[PlayerSchema] = None
