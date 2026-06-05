from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer, String, Uuid, Float, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from uuid import uuid4
from uuid6 import uuid7
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Match(Base):
    __tablename__ = "match_data"
    match_id = Column(Uuid, primary_key=True, default=uuid7)
    first_team_name = Column(String)
    second_team_name = Column(String)
    first_team_id = Column(Uuid, default=uuid4)
    first_team_player1_id = Column(Uuid, default=uuid4)
    first_team_player2_id = Column(Uuid, default=uuid4)
    # Optional in mixed doubles (2 players/team). Do not auto-generate IDs.
    first_team_player3_id = Column(Uuid, nullable=True)
    first_team_player4_id = Column(Uuid, nullable=True)
    second_team_id = Column(Uuid, default=uuid4)
    second_team_player1_id = Column(Uuid, default=uuid4)
    second_team_player2_id = Column(Uuid, default=uuid4)
    # Optional in mixed doubles (2 players/team). Do not auto-generate IDs.
    second_team_player3_id = Column(Uuid, nullable=True)
    second_team_player4_id = Column(Uuid, nullable=True)
    winner_team_id = Column(Uuid, nullable=True)
    score_id = Column(Uuid, default=uuid7)
    time_limit = Column(Float)
    extra_end_time_limit = Column(Float)
    standard_end_count = Column(Integer)
    applied_rule = Column(Integer)  # 0: fgz_rule (5-rock), 1: no_tick_rule, 2: modified_fgz_rule (mixed doubles)
    physical_simulator_id = Column(Uuid, default=uuid4)
    tournament_id = Column(Uuid, default=uuid7)
    match_name = Column(String)
    game_mode = Column(String(32), nullable=False, default="standard")
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, default=datetime.now)

    state = relationship(
        "State",
        primaryjoin="Match.match_id == foreign(State.match_id)",
        back_populates="match",
        cascade="all, delete",
    )
    first_team_player1 = relationship(
        "Player",
        primaryjoin="foreign(Match.first_team_player1_id) == Player.player_id",
        back_populates="first_player1",
        cascade="all, delete",
    )
    first_team_player2 = relationship(
        "Player",
        primaryjoin="foreign(Match.first_team_player2_id) == Player.player_id",
        back_populates="first_player2",
        cascade="all, delete",
    )
    first_team_player3 = relationship(
        "Player",
        primaryjoin="foreign(Match.first_team_player3_id) == Player.player_id",
        back_populates="first_player3",
        cascade="all, delete",
    )
    first_team_player4 = relationship(
        "Player",
        primaryjoin="foreign(Match.first_team_player4_id) == Player.player_id",
        back_populates="first_player4",
        cascade="all, delete",
    )
    second_team_player1 = relationship(
        "Player",
        primaryjoin="foreign(Match.second_team_player1_id) == Player.player_id",
        back_populates="second_player1",
        cascade="all, delete",
    )
    second_team_player2 = relationship(
        "Player",
        primaryjoin="foreign(Match.second_team_player2_id) == Player.player_id",
        back_populates="second_player2",
        cascade="all, delete",
    )
    second_team_player3 = relationship(
        "Player",
        primaryjoin="foreign(Match.second_team_player3_id) == Player.player_id",
        back_populates="second_player3",
        cascade="all, delete",
    )
    second_team_player4 = relationship(
        "Player",
        primaryjoin="foreign(Match.second_team_player4_id) == Player.player_id",
        back_populates="second_player4",
        cascade="all, delete",
    )
    score = relationship(
        "Score",
        primaryjoin="foreign(Match.score_id) == Score.score_id",
        back_populates="match",
        cascade="all, delete",
        uselist=False,  # 一対一のリレーション
    )
    simulator = relationship(
        "PhysicalSimulator",
        primaryjoin="foreign(Match.physical_simulator_id) == PhysicalSimulator.physical_simulator_id",
        back_populates="match",
        cascade="all, delete",
    )
    tournament = relationship(
        "Tournament",
        primaryjoin="foreign(Match.tournament_id) == Tournament.tournament_id",
        back_populates="match",
        cascade="all, delete",
    )

    mixed_doubles_settings = relationship(
        "MatchMixedDoublesSettings",
        primaryjoin="Match.match_id == foreign(MatchMixedDoublesSettings.match_id)",
        back_populates="match",
        cascade="all, delete",
        uselist=False,
    )



class MatchMixedDoublesSettings(Base):
    __tablename__ = "match_mixed_doubles_settings"

    match_id = Column(Uuid, ForeignKey("match_data.match_id", ondelete="CASCADE"), primary_key=True)
    positioned_stones_pattern = Column(Integer, nullable=False)
    team0_power_play_end = Column(Integer, nullable=True)
    team1_power_play_end = Column(Integer, nullable=True)
    # Per-end selector (hammer) team_id list stored as UUID strings.
    # Index corresponds to end_number.
    end_setup_team_ids = Column(JSONB, nullable=False, default=list)

    match = relationship(
        "Match",
        primaryjoin="foreign(MatchMixedDoublesSettings.match_id) == Match.match_id",
        back_populates="mixed_doubles_settings",
    )


class Score(Base):
    __tablename__ = "score"
    score_id = Column(Uuid, primary_key=True, default=uuid7)
    team0 = Column(ARRAY(Integer))
    team1 = Column(ARRAY(Integer))

    match = relationship(
        "Match",
        primaryjoin="Score.score_id == foreign(Match.score_id)",
        back_populates="score",
        cascade="all, delete",
        uselist=False,
    )
    state = relationship(
        "State",
        primaryjoin="Score.score_id == foreign(State.score_id)",
        back_populates="score",
        cascade="all, delete",
    )


class PhysicalSimulator(Base):
    __tablename__ = "physical_simulator"
    physical_simulator_id = Column(Uuid, primary_key=True, default=uuid4)
    simulator_name = Column(String)

    match = relationship(
        "Match",
        primaryjoin="PhysicalSimulator.physical_simulator_id == foreign(Match.physical_simulator_id)",
        back_populates="simulator",
        cascade="all, delete",
    )


class Tournament(Base):
    __tablename__ = "tournament"
    tournament_id = Column(Uuid, primary_key=True, default=uuid4)
    tournament_name = Column(String)

    match = relationship(
        "Match",
        primaryjoin="Tournament.tournament_id == foreign(Match.tournament_id)",
        back_populates="tournament",
        cascade="all, delete",
    )


class ShotInfo(Base):
    __tablename__ = "shot_info"
    shot_id = Column(Uuid, primary_key=True, default=uuid7)
    player_id = Column(Uuid, default=uuid4)
    team_id = Column(Uuid, default=uuid4)
    trajectory_id = Column(Uuid, default=uuid4)
    pre_shot_state_id = Column(Uuid, default=uuid7)
    post_shot_state_id = Column(Uuid, default=uuid7)
    actual_translational_velocity = Column(Float)
    actual_shot_angle = Column(Float)
    actual_angular_velocity = Column(Float)
    translational_velocity = Column(Float)
    angular_velocity = Column(Float)
    shot_angle = Column(Float)

    state = relationship(
        "State",
        primaryjoin="ShotInfo.shot_id == foreign(State.shot_id)",
        back_populates="shot_info",
        cascade="all, delete",
        uselist=False,
    )
    pre_shot_state = relationship(
        "State",
        primaryjoin="foreign(ShotInfo.pre_shot_state_id) == State.state_id",
        back_populates="pre_shot_info",
        cascade="all, delete",
    )
    post_shot_state = relationship(
        "State",
        primaryjoin="foreign(ShotInfo.post_shot_state_id) == State.state_id",
        back_populates="post_shot_info",
        cascade="all, delete",
    )


class State(Base):
    __tablename__ = "state"
    state_id = Column(Uuid, primary_key=True, default=uuid7)
    winner_team_id = Column(Uuid, nullable=True)
    match_id = Column(Uuid, default=uuid7)
    end_number = Column(Integer)
    team_shot_number = Column(Integer)
    total_shot_number = Column(Integer)
    first_team_remaining_time = Column(Float)
    second_team_remaining_time = Column(Float)
    first_team_extra_end_remaining_time = Column(Float)
    second_team_extra_end_remaining_time = Column(Float)
    stone_coordinate_id = Column(Uuid, default=uuid7)
    score_id = Column(Uuid, default=uuid7)
    shot_id = Column(Uuid, nullable=True)
    next_shot_team_id = Column(Uuid, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    match = relationship(
        "Match",
        primaryjoin="foreign(State.match_id) == Match.match_id",
        back_populates="state",
        cascade="all, delete",
    )
    score = relationship(
        "Score",
        primaryjoin="foreign(State.score_id) == Score.score_id",
        back_populates="state",
        cascade="all, delete",
    )
    shot_info = relationship(
        "ShotInfo",
        primaryjoin="foreign(State.shot_id) == ShotInfo.shot_id",
        back_populates="state",
        cascade="all, delete",
        uselist=False,
    )
    stone_coordinate = relationship(
        "StoneCoordinate",
        primaryjoin="foreign(State.stone_coordinate_id) == StoneCoordinate.stone_coordinate_id",
        back_populates="state",
        cascade="all, delete",
    )
    pre_shot_info = relationship(
        "ShotInfo",
        primaryjoin="State.state_id == foreign(ShotInfo.pre_shot_state_id)",
        back_populates="pre_shot_state",
        cascade="all, delete",
    )
    post_shot_info = relationship(
        "ShotInfo",
        primaryjoin="State.state_id == foreign(ShotInfo.post_shot_state_id)",
        back_populates="post_shot_state",
        cascade="all, delete",
    )


class StoneCoordinate(Base):
    __tablename__ = "stone_coordinate"
    stone_coordinate_id = Column(Uuid, primary_key=True, default=uuid7)
    data = Column(JSONB)

    state = relationship(
        "State",
        primaryjoin="StoneCoordinate.stone_coordinate_id == foreign(State.stone_coordinate_id)",
        back_populates="stone_coordinate",
        cascade="all, delete",
    )


class Trajectory(Base):
    __tablename__ = "trajectory"
    trajectory_id = Column(Uuid, primary_key=True, default=uuid7)
    trajectory_data = Column(JSONB)
    data_format_version = Column(String(32))


class Player(Base):
    __tablename__ = "player"
    player_id = Column(Uuid, primary_key=True, default=uuid4)
    team_id = Column(Uuid, default=uuid4)
    max_velocity = Column(Float)
    shot_std_dev = Column(Float)
    angle_std_dev = Column(Float)
    player_name = Column(String)

    first_player1 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.first_team_player1_id)",
        back_populates="first_team_player1",
        cascade="all, delete",
    )
    first_player2 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.first_team_player2_id)",
        back_populates="first_team_player2",
        cascade="all, delete",
    )
    first_player3 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.first_team_player3_id)",
        back_populates="first_team_player3",
        cascade="all, delete",
    )
    first_player4 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.first_team_player4_id)",
        back_populates="first_team_player4",
        cascade="all, delete",
    )
    second_player1 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.second_team_player1_id)",
        back_populates="second_team_player1",
        cascade="all, delete",
    )
    second_player2 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.second_team_player2_id)",
        back_populates="second_team_player2",
        cascade="all, delete",
    )
    second_player3 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.second_team_player3_id)",
        back_populates="second_team_player3",
        cascade="all, delete",
    )
    second_player4 = relationship(
        "Match",
        primaryjoin="Player.player_id == foreign(Match.second_team_player4_id)",
        back_populates="second_team_player4",
        cascade="all, delete",
    )
