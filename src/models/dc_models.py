from pydantic import BaseModel, ConfigDict
from enum import Enum
from uuid import UUID
from typing import Optional, Dict, List, Literal


class MatchNameModel(str, Enum):
    team0 = "team0"  # team0 is first attacker team at the first end
    team1 = "team1"  # team1 is sencond attacker team at the first end


class AppliedRuleModel(str, Enum):
    fgz_rule = "fgz_rule"  # Applied 5-rock Free Guard Zone
    no_tick_rule = "no_tick_rule"  # Applied No Tick Rule
    modified_fgz_rule = "modified_fgz_rule"  # Mixed doubles only


class GameModeModel(str, Enum):
    standard = "standard"
    mix_doubles = "mix_doubles"


class TournamentModel(BaseModel):
    tournament_id: UUID
    tournament_name: str


class TournamentNameModel(BaseModel):
    tournament_name: str


class PhysicalSimulatorNameModel(BaseModel):
    simulator_name: str


class PhysicalSimulatorModel(BaseModel):
    physical_simulator_id: UUID
    simulator_name: str


class CoordinateDataModel(BaseModel):
    x: float
    y: float

    model_config = ConfigDict(from_attributes=True)


class StoneCoordinateModel(BaseModel):
    data: Dict[str, List[CoordinateDataModel]]  # フラットなDict型

    model_config = ConfigDict(from_attributes=True)


class ScoreModel(BaseModel):
    team0: list
    team1: list

    model_config = ConfigDict(from_attributes=True)


class ShotInfoModel(BaseModel):
    translational_velocity: float
    angular_velocity: float
    shot_angle: float


class PowerPlayEndModel(BaseModel):
    team0: int | None = None
    team1: int | None = None


class MixDoublesSettingsModel(BaseModel):
    end_setup_team: str
    positioned_stones_pattern: int
    power_play_end: PowerPlayEndModel


class EndSetupRequestModel(BaseModel):
    selector_throws_first: bool
    power_play_side: Optional[Literal["left", "right"]] = None


class PositionedStonesModel(str, Enum):
    center_guard = "center_guard"
    center_house = "center_house"
    pp_left = "pp_left"
    pp_right = "pp_right"


class PositionedStonesRequestModel(BaseModel):
    positioned_stones: PositionedStonesModel


class StateModel(BaseModel):
    winner_team: str | None
    end_number: int
    shot_number: int | None
    total_shot_number: int | None
    next_shot_team: str | None
    first_team_remaining_time: float
    second_team_remaining_time: float
    first_team_extra_end_remaining_time: float
    second_team_extra_end_remaining_time: float
    mix_doubles_settings: Optional[MixDoublesSettingsModel] = None
    last_move: Optional[ShotInfoModel] = None
    stone_coordinate: Optional[StoneCoordinateModel] = None
    score: Optional[ScoreModel] = None

    model_config = ConfigDict(from_attributes=True)


class PlayerModel(BaseModel):
    max_velocity: float
    shot_std_dev: float
    angle_std_dev: float
    player_name: str


class TeamModel(BaseModel):
    use_default_config: bool
    team_name: str
    player1: PlayerModel
    player2: PlayerModel
    # Mixed doubles uses only 2 players per team; allow omitting player3/player4.
    player3: Optional[PlayerModel] = None
    player4: Optional[PlayerModel] = None


class ClientDataModel(BaseModel):
    game_mode: GameModeModel
    tournament: TournamentNameModel
    simulator: PhysicalSimulatorNameModel
    applied_rule: AppliedRuleModel
    time_limit: float
    extra_end_time_limit: float
    standard_end_count: int
    match_name: str
    positioned_stones_pattern: Optional[int] = None


class MatchModel(BaseModel):
    match_id: UUID
    time_limit: float
    extra_end_time_limit: float
    standard_end_count: int
    match_name: str
    applied_rule: AppliedRuleModel
    game_mode: Optional[GameModeModel] = None
    mix_doubles_settings: Optional[MixDoublesSettingsModel] = None
    score: Optional[ScoreModel] = None
    simulator: Optional[PhysicalSimulatorModel] = None
    tournament: Optional[TournamentModel] = None
