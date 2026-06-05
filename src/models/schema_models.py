from pydantic import BaseModel, ConfigDict, Json, Field
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime


class TournamentSchema(BaseModel):
    """Tournament metadata used by match records.

    Attributes:
        tournament_id: Unique identifier of the tournament.
        tournament_name: Display name of the tournament.
    """

    tournament_id: UUID
    tournament_name: str

    model_config = ConfigDict(from_attributes=True)


class PhysicalSimulatorSchema(BaseModel):
    """Physical simulator metadata linked to a match.

    Attributes:
        physical_simulator_id: Unique identifier of the simulator profile.
        simulator_name: Display name of the simulator profile.
    """

    physical_simulator_id: UUID
    simulator_name: str

    model_config = ConfigDict(from_attributes=True)


class PlayerSchema(BaseModel):
    """Player parameters used by simulation and matchmaking.

    Attributes:
        player_id: Unique identifier of the player.
        team_id: Team identifier the player belongs to.
        max_velocity: Maximum translational velocity available to the player.
        shot_std_dev: Standard deviation of shot speed error.
        angle_std_dev: Standard deviation of shot angle error.
        player_name: Display name of the player.
    """

    player_id: UUID
    team_id: UUID
    max_velocity: float
    shot_std_dev: float
    angle_std_dev: float
    player_name: str

    model_config = ConfigDict(from_attributes=True)


class TrajectorySchema(BaseModel):
    """Serialized trajectory data for a delivered shot.

    Attributes:
        trajectory_id: Unique identifier of the trajectory.
        trajectory_data: JSON payload describing motion over time.
    """

    trajectory_id: UUID
    trajectory_data: Json


class StoneCoordinateSchema(BaseModel):
    """Stone positions for a state snapshot.

    Attributes:
        stone_coordinate_id: Unique identifier of the coordinate snapshot.
        data: Mapping of stone identifiers to board coordinates.
    """

    stone_coordinate_id: UUID
    data: dict

    model_config = ConfigDict(from_attributes=True)


class ScoreSchema(BaseModel):
    """Cumulative or per-end score arrays for both teams.

    Attributes:
        score_id: Unique identifier of the score record.
        team0: Score list for the first team.
        team1: Score list for the second team.
    """

    score_id: UUID
    team0: list
    team1: list

    model_config = ConfigDict(from_attributes=True)


class ShotInfoSchema(BaseModel):
    """Shot execution details and measured outcomes.

    Attributes:
        shot_id: Unique identifier of the shot record.
        player_id: Player who delivered the shot.
        team_id: Team of the throwing player.
        trajectory_id: Linked trajectory identifier.
        pre_shot_state_id: State identifier immediately before the shot.
        post_shot_state_id: State identifier immediately after the shot.
        actual_translational_velocity: Observed translational velocity.
        actual_shot_angle: Observed release angle.
        actual_angular_velocity: Observed angular velocity.
        translational_velocity: Requested translational velocity.
        angular_velocity: Requested angular velocity.
        shot_angle: Requested release angle.
    """

    shot_id: UUID
    player_id: UUID
    team_id: UUID
    trajectory_id: UUID
    pre_shot_state_id: UUID
    post_shot_state_id: UUID
    actual_translational_velocity: float
    actual_shot_angle: float
    actual_angular_velocity: float
    translational_velocity: float
    angular_velocity: float
    shot_angle: float

    model_config = ConfigDict(from_attributes=True)


class StateSchema(BaseModel):
    """Game state snapshot for a specific end and shot timing.

    Attributes:
        state_id: Unique identifier of the state snapshot.
        winner_team_id: Match winner if the game has finished.
        match_id: Parent match identifier.
        end_number: End index of this state.
        team_shot_number: Shot index within the current end.
        total_shot_number: Total number of shots in the current end.
        first_team_remaining_time: Remaining thinking time for the first team.
        second_team_remaining_time: Remaining thinking time for the second team.
        first_team_extra_end_remaining_time: Remaining extra-end time for the first team.
        second_team_extra_end_remaining_time: Remaining extra-end time for the second team.
        stone_coordinate_id: Linked stone coordinate record.
        score_id: Linked score record.
        shot_id: Linked shot record when available.
        next_shot_team_id: Team that should throw next.
        created_at: Creation timestamp of this state snapshot.
        stone_coordinate: Embedded stone coordinates if loaded.
        score: Embedded score if loaded.
    """

    state_id: UUID
    winner_team_id: UUID | None
    match_id: UUID
    end_number: int
    team_shot_number: int | None
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


class MatchMixedDoublesSettingsSchema(BaseModel):
    """Match settings specific to mixed doubles mode.

    Attributes:
        positioned_stones_pattern: Initial positioned-stones pattern index.
        team0_power_play_end: Selected power-play end for the first team.
        team1_power_play_end: Selected power-play end for the second team.
        end_setup_team_ids: Team order used when preparing each end.
    """

    positioned_stones_pattern: int
    team0_power_play_end: int | None = None
    team1_power_play_end: int | None = None
    end_setup_team_ids: list[UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MatchDataSchema(BaseModel):
    """Primary match record returned by REST APIs.

    Attributes:
        match_id: Unique identifier of the match.
        first_team_name: Display name of the first team.
        second_team_name: Display name of the second team.
        first_team_id: Identifier of the first team.
        first_team_player1_id: First player identifier of the first team.
        first_team_player2_id: Second player identifier of the first team.
        first_team_player3_id: Third player identifier of the first team when used.
        first_team_player4_id: Fourth player identifier of the first team when used.
        second_team_id: Identifier of the second team.
        second_team_player1_id: First player identifier of the second team.
        second_team_player2_id: Second player identifier of the second team.
        second_team_player3_id: Third player identifier of the second team when used.
        second_team_player4_id: Fourth player identifier of the second team when used.
        winner_team_id: Winner identifier when the match is decided.
        score_id: Linked score identifier.
        time_limit: Thinking-time limit for regular ends.
        extra_end_time_limit: Thinking-time limit for extra ends.
        standard_end_count: Number of scheduled ends.
        physical_simulator_id: Simulator profile identifier.
        applied_rule: Applied ruleset identifier.
        tournament_id: Tournament identifier.
        match_name: Human-readable match name.
        game_mode: Match mode, either standard or mixed_doubles.
        created_at: Match creation timestamp.
        started_at: Match start timestamp.
        score: Embedded score model if loaded.
        tournament: Embedded tournament model if loaded.
        simulator: Embedded simulator model if loaded.
        mixed_doubles_settings: Embedded mixed doubles settings if loaded.
    """

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
    game_mode: Literal["standard", "mixed_doubles"] = "standard"
    created_at: datetime
    started_at: datetime
    score: Optional[ScoreSchema] = None
    tournament: Optional[TournamentSchema] = None
    simulator: Optional[PhysicalSimulatorSchema] = None
    mixed_doubles_settings: Optional[MatchMixedDoublesSettingsSchema] = None

    model_config = ConfigDict(from_attributes=True)


class MatchSummarySchema(BaseModel):
    """Lightweight match record for listing purposes.

    Attributes:
        match_id: Unique identifier of the match.
        match_name: Human-readable match name.
        first_team_name: Display name of team0 (first team).
        second_team_name: Display name of team1 (second team).
        winner_team_id: Winner identifier when the match is decided.
        game_mode: Match mode, either standard or mixed_doubles.
        started_at: Match start timestamp.
        tournament_id: Tournament identifier.
    """

    match_id: UUID
    match_name: str
    first_team_name: str | None
    second_team_name: str | None
    winner_team_id: UUID | None
    game_mode: Literal["standard", "mixed_doubles"]
    started_at: datetime
    tournament_id: UUID

    model_config = ConfigDict(from_attributes=True)


class TeamSchema(BaseModel):
    """Team composition with optional embedded player data.

    Attributes:
        player1_id: Identifier of player slot 1.
        player2_id: Identifier of player slot 2.
        player3_id: Identifier of player slot 3.
        player4_id: Identifier of player slot 4.
        team_name: Display name of the team.
        player1: Embedded player model for slot 1 if loaded.
        player2: Embedded player model for slot 2 if loaded.
        player3: Embedded player model for slot 3 if loaded.
        player4: Embedded player model for slot 4 if loaded.
    """

    player1_id: UUID
    player2_id: UUID
    player3_id: UUID
    player4_id: UUID
    team_name: str
    player1: Optional[PlayerSchema] = None
    player2: Optional[PlayerSchema] = None
    player3: Optional[PlayerSchema] = None
    player4: Optional[PlayerSchema] = None
