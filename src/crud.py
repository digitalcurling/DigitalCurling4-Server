# import database
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from typing import List

from src.models.schema_models import (
    MatchDataSchema,
    MatchSummarySchema,
    ScoreSchema,
    StateSchema,
    StoneCoordinateSchema,
    TournamentSchema,
    PhysicalSimulatorSchema,
    PlayerSchema,
    ShotInfoSchema,
)
from src.models.schemas import (
    Match,
    MatchMixedDoublesSettings,
    Score,
    State,
    StoneCoordinate,
    Tournament,
    PhysicalSimulator,
    Player,
    ShotInfo,
)
from uuid import UUID


class UpdateData:
    @staticmethod
    async def update_match_data_with_team_name(
        match_id, session: AsyncSession, team_name: str, match_team_name: str
    ) -> str | None:
        """Update match table with team name

        Args:
            match_id (_type_): To identify the match
            session (AsyncSession): AsyncSession object to interact with database
            team_name (str): client team name
            match_team_name (str): To identify the team name in match table, "team0" or "team1"

        Returns:
            str | None: _description_
        """
        try:
            stmt = select(Match).where(Match.match_id == match_id).with_for_update()
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            your_match_team_name = None

            if result.first_team_name is None and result.second_team_name is None:
                if match_team_name == "team0":
                    result.first_team_name = team_name
                    your_match_team_name = "team0"
                elif match_team_name == "team1":
                    result.second_team_name = team_name
                    your_match_team_name = "team1"
            elif result.first_team_name is None and result.second_team_name is not None:
                result.first_team_name = team_name
                your_match_team_name = "team0"
            elif result.first_team_name is not None and result.second_team_name is None:
                result.second_team_name = team_name
                your_match_team_name = "team1"
            else:
                return None
            await session.commit()
            return your_match_team_name

        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update match data with team name: {e}")
            return None

    @staticmethod
    async def update_first_team(
        match_id: UUID,
        session: AsyncSession,
        team_id: UUID,
        player_id_list: List[UUID],
        team_name: str,
    ) -> bool:
        """Update match table with first team data

        Args:
            match_id (UUID): To identify the match
            session (AsyncSession): AsyncSession object to interact with database
            player_id_list (List[UUID]): List of player ids
            first_team (TeamSchema): First attack at the first end
        """
        try:
            stmt = select(Match).where(Match.match_id == match_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return False

            if len(player_id_list) not in (2, 4):
                logging.error("Invalid player_id_list length for first team: %s", len(player_id_list))
                return False

            result.first_team_name = team_name
            result.first_team_id = team_id
            result.first_team_player1_id = player_id_list[0]
            result.first_team_player2_id = player_id_list[1]
            if len(player_id_list) == 4:
                result.first_team_player3_id = player_id_list[2]
                result.first_team_player4_id = player_id_list[3]
            else:
                # Mixed doubles: only 2 players. Keep slots 3/4 NULL.
                result.first_team_player3_id = None
                result.first_team_player4_id = None
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update first team data: {e}")
            return False

    @staticmethod
    async def update_second_team(
        match_id: UUID,
        session: AsyncSession,
        team_id: UUID,
        player_id_list: List[UUID],
        team_name: str,
    ) -> bool:
        """Update match table with second team data

        Args:
            match_id (UUID): To identify the match
            session (AsyncSession): AsyncSession object to interact with database
            player_id_list (List[UUID]): List of player ids
            second_team (TeamSchema): Second attack at the first end
        """
        try:
            stmt = select(Match).where(Match.match_id == match_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return False

            if len(player_id_list) not in (2, 4):
                logging.error("Invalid player_id_list length for second team: %s", len(player_id_list))
                return False

            result.second_team_name = team_name
            result.second_team_id = team_id
            result.second_team_player1_id = player_id_list[0]
            result.second_team_player2_id = player_id_list[1]
            if len(player_id_list) == 4:
                result.second_team_player3_id = player_id_list[2]
                result.second_team_player4_id = player_id_list[3]
            else:
                # Mixed doubles: only 2 players. Keep slots 3/4 NULL.
                result.second_team_player3_id = None
                result.second_team_player4_id = None
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update second team data: {e}")
            return False

    @staticmethod
    async def update_created_at_state_data(state_id: UUID, session: AsyncSession) -> bool:
        """Update state table with created_at data
        Args:
            state_id (UUID): To identify the state
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            stmt = select(State).where(State.state_id == state_id)
            result = await session.execute(stmt)
            result = result.scalars().first()
            if result is None:
                return False
            result.created_at = datetime.now()
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update created_at state data: {e}")
            return False

    @staticmethod
    async def update_next_shot_team(
        match_id: UUID, next_shot_team: UUID, session: AsyncSession
    ) -> bool:
        """Update next shot team in State table

        Args:
            match_id (UUID): To identify the latest state
            next_shot_team (UUID): Next shot team id
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            stmt = (
                select(State)
                .where(State.match_id == match_id)
                .order_by(
                    desc(State.end_number),
                    desc(State.total_shot_number).nullslast(),
                    desc(State.state_id),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return False

            result.next_shot_team_id = next_shot_team
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update next shot team data: {e}")
            return False

    @staticmethod
    async def update_score(score: ScoreSchema, session: AsyncSession) -> bool:
        """Update score table with new score

        Args:
            score (ScoreSchema): Score data which is updated at [end_number]
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            stmt = select(Score).where(Score.score_id == score.score_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return False

            result.team0 = score.team0
            result.team1 = score.team1
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update score data: {e}")
            return False

    @staticmethod
    async def update_score_no_commit(score: ScoreSchema, session: AsyncSession) -> None:
        """Update score row without committing. For use inside session.begin() blocks."""
        stmt = select(Score).where(Score.score_id == score.score_id)
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            raise RuntimeError(f"Score row not found while updating score: {score.score_id}")
        row.team0 = score.team0
        row.team1 = score.team1

    @staticmethod
    async def update_state_shot_id(state_id: UUID, shot_id: UUID, session: AsyncSession) -> bool:
        """Update a State row to attach the decided shot_id."""
        try:
            stmt = select(State).where(State.state_id == state_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return False

            result.shot_id = shot_id
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to update state shot_id: {e}")
            return False

    @staticmethod
    async def set_state_shot_id_no_commit(state_id: UUID, shot_id: UUID, session: AsyncSession) -> None:
        """Set State.shot_id without committing.

        Intended for service-layer transactions (session.begin()).
        """

        stmt = select(State).where(State.state_id == state_id)
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            raise RuntimeError("State not found while linking shot_id.")
        row.shot_id = shot_id


class ReadData:
    @staticmethod
    async def read_mixed_doubles_settings_row_for_update(
        match_id: UUID, session: AsyncSession
    ) -> MatchMixedDoublesSettings | None:
        """Read MatchMixedDoublesSettings row with row-level lock.

        This is intended for service-layer transactions (session.begin()) that need to
        update selector list / power play usage atomically.

        Returns:
            MatchMixedDoublesSettings | None: ORM row (NOT a Schema model).
        """

        stmt = (
            select(MatchMixedDoublesSettings)
            .where(MatchMixedDoublesSettings.match_id == match_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        if result is None:
            return None
        return result.scalars().first()

    @staticmethod
    async def read_match_data(
        match_id: UUID, session: AsyncSession
    ) -> MatchDataSchema | None:
        """Read match data and score, tournament, simulator data from database

        Args:
            match_id (UUID): To identify the match
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            MatchDataSchema: Match data with score, tournament, simulator data
        """
        try:
            stmt = (
                select(Match)
                .where(Match.match_id == match_id)
                .options(
                    joinedload(Match.score),
                    joinedload(Match.tournament),
                    joinedload(Match.simulator),
                    joinedload(Match.mixed_doubles_settings),
                )
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            match_data = MatchDataSchema.model_validate(result)
            return match_data
        except Exception as e:
            logging.error(f"Failed to read match data: {e}")
            return None


    @staticmethod
    async def read_state_data(state_id: UUID, session: AsyncSession) -> StateSchema | None:
        """Read specific state data and stone coordinate data from database

        Args:
            state_id (UUID): To get the specific state data
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            StateSchema: State data with stone coordinate data
        """
        try:
            stmt = (
                select(State)
                .options(
                    joinedload(State.stone_coordinate),
                    joinedload(State.score),
                )
                .where(State.state_id == state_id)
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            return StateSchema.model_validate(result)
        except Exception as e:
            logging.error(f"Failed to read state data: {e}")
            return None

    @staticmethod
    async def read_latest_state_data(
        match_id: UUID, session: AsyncSession
    ) -> StateSchema | None:
        """Read the latest state data and stone coordinate data from database

        Args:
            match_id (UUID): To identify the latest state
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            StateSchema: Latest state data with stone coordinate data
        """
        try:
            stmt = (
                select(State)
                .options(
                    joinedload(State.stone_coordinate),
                    joinedload(State.score),
                )
                .where(State.match_id == match_id)
                .order_by(
                    desc(State.end_number),
                    desc(State.total_shot_number).nullslast(),
                    desc(State.state_id),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            state_data = StateSchema.model_validate(result)
            return state_data

        except Exception as e:
            logging.error(f"Failed to read latest state data: {e}")
            return None

    @staticmethod
    async def read_state_data_in_end(
        match_id: UUID, end_number: int, session: AsyncSession
    ) -> List[StateSchema]:
        """Read state data in specific end number from database

        Args:
            match_id (UUID): To identify the match
            end_number (int): To identify the end number
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            List[StateSchema]: State data in specific end number
        """
        try:
            stmt = (
                select(State)
                .options(
                    joinedload(State.stone_coordinate),
                    joinedload(State.score),
                )
                .where(State.match_id == match_id, State.end_number == end_number)
                .order_by(State.total_shot_number)
            )
            result = await session.execute(stmt)
            result = result.scalars().all()

            if result is None:
                return []

            state_data_list: List[StateSchema] = []
            for state in result:
                state_data_list.append(
                    StateSchema.model_validate(state)
                )

            # state_data_list = [StateSchema.model_validate(state) for state in result]
            return state_data_list

        except Exception as e:
            logging.error(f"Failed to read state data in end: {e}")
            return []

    @staticmethod
    async def read_stone_data(
        stone_coordinate_id: UUID, session: AsyncSession
    ) -> StoneCoordinateSchema | None:
        """Read stone coordinate data from database

        Args:
            stone_coordinate_id (UUID): To identify the stone coordinate data

        Returns:
            StoneCoordinateSchema: Stone coordinate data
        """
        try:
            stmt = select(StoneCoordinate).where(
                StoneCoordinate.stone_coordinate_id == stone_coordinate_id
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            stone_data = StoneCoordinateSchema(
                stone_coordinate_id=result.stone_coordinate_id,
                data=result.data,
            )
            return stone_data

        except Exception as e:
            logging.error(f"Failed to read stone data: {e}")
            return None

    @staticmethod
    async def read_score_data(score_id: UUID, session: AsyncSession) -> ScoreSchema | None:
        """Read score data from database

        Args:
            score_id (UUID): To identify the score data
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            ScoreSchema: Score data with first team score and second team score
        """
        try:
            stmt = select(Score).where(Score.score_id == score_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            score_data = ScoreSchema(
                score_id=result.score_id,
                team0=result.team0,
                team1=result.team1,
            )
            return score_data
        except Exception as e:
            logging.error(f"Failed to read score data: {e}")
            return None

    @staticmethod
    async def read_team_id(team_name: str, session: AsyncSession) -> UUID | None:
        """Read team id data from database
        Args:
            team_name (str): To identify the team name
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            UUID: Team id
        """
        try:
            stmt = (
                select(Match)
                .where(
                    (Match.first_team_name == team_name)
                    | (Match.second_team_name == team_name)
                )
                .options(
                    joinedload(Match.score),
                    joinedload(Match.tournament),
                    joinedload(Match.simulator),
                )
                .order_by(desc(Match.created_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            result = result.scalars().first()
            if result is None:
                return None

            match_data = MatchDataSchema.model_validate(result)

            if match_data.first_team_name == team_name:
                return match_data.first_team_id
            elif match_data.second_team_name == team_name:
                return match_data.second_team_id
            else:
                return None
        except Exception as e:
            logging.error(f"Failed to read team player data: {e}")
            return None

    @staticmethod
    async def read_player_id(
        player_name: str, team_id: UUID, session: AsyncSession
    ) -> UUID | None:
        """Read player id data from database

        Args:
            player_name (str): To identify the player name
            team_id (UUID): To identify the team id
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            UUID: Player id
        """
        try:
            stmt = select(Player).where(
                (Player.player_name == player_name) & (Player.team_id == team_id)
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            return result.player_id
        except Exception as e:
            logging.error(f"Failed to read player id data: {e}")

    @staticmethod
    async def read_player_data(player_id: UUID, session: AsyncSession) -> PlayerSchema | None:
        """Read player data from database

        Args:
            player_id (UUID): To identify the player
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            PlayerSchema: Player data with player name, team id, max velocity, shot dispersion rate
        """
        try:
            stmt = select(Player).where(Player.player_id == player_id)
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            player_data = PlayerSchema.model_validate(result)

            return player_data

        except Exception as e:
            logging.error(f"Failed to read player data: {e}")
            return None

    @staticmethod
    async def read_simulator_name(match_id: UUID, session: AsyncSession) -> str | None:
        """Read simulator name from match data

        Args:
            match_id (UUID): To identify the match
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            str: Simulator name
        """
        try:
            stmt = select(Match.simulator).where(Match.match_id == match_id)
            result = await session.execute(stmt)
            result = result.scalars().first()
            simulator_name = result.simulator.simulator_name
            return simulator_name
        except Exception as e:
            logging.error(f"Failed to read simulator name: {e}")
            return None

    @staticmethod
    async def read_simulator_id(simulator_name: str, session: AsyncSession) -> UUID | None:
        """Read simulator id from simulator name(fcv1)

        Args:
            simulator_name (str): Now, fcv1 only
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            UUID: _description_
        """
        try:
            stmt = select(PhysicalSimulator).where(
                PhysicalSimulator.simulator_name == simulator_name
            )
            result = await session.execute(stmt)
            result = result.scalars().first()

            if result is None:
                return None

            return result.physical_simulator_id
        except Exception as e:
            logging.error(f"Failed to read simulator id: {e}")
            return None

    @staticmethod
    async def read_shot_info_data(shot_id: UUID, session: AsyncSession) -> ShotInfoSchema | None:
        """Read shot info data from database by shot_id."""
        try:
            stmt = select(ShotInfo).where(ShotInfo.shot_id == shot_id)
            result = await session.execute(stmt)
            result = result.scalars().first()
            if result is None:
                return None
            return ShotInfoSchema.model_validate(result)
        except Exception as e:
            logging.error(f"Failed to read shot info data: {e}")
            return None

    @staticmethod
    async def read_last_shot_info_by_post_state_id(
        post_shot_state_id: UUID, session: AsyncSession
    ) -> ShotInfoSchema | None:
        """Read the shot info that produced the given state (post_shot_state_id == state_id)."""
        try:
            stmt = select(ShotInfo).where(ShotInfo.post_shot_state_id == post_shot_state_id)
            result = await session.execute(stmt)
            result = result.scalars().first()
            if result is None:
                return None
            return ShotInfoSchema.model_validate(result)
        except Exception as e:
            logging.error(f"Failed to read last shot info by post state id: {e}")
            return None

    @staticmethod
    async def read_all_tournaments(session: AsyncSession) -> List[TournamentSchema]:
        """Read all tournaments ordered by tournament_name."""
        try:
            stmt = select(Tournament).order_by(Tournament.tournament_name)
            result = await session.execute(stmt)
            return [TournamentSchema.model_validate(row) for row in result.scalars().all()]
        except Exception as e:
            logging.error(f"Failed to read all tournaments: {e}")
            return []

    @staticmethod
    async def read_matches_by_tournament_name(
        tournament_name: str, session: AsyncSession
    ) -> List[MatchSummarySchema]:
        """Read all matches belonging to a tournament, ordered by started_at descending."""
        try:
            stmt = (
                select(Match)
                .join(Tournament, Match.tournament_id == Tournament.tournament_id)
                .where(Tournament.tournament_name == tournament_name)
                .order_by(Match.started_at.desc())
            )
            result = await session.execute(stmt)
            return [MatchSummarySchema.model_validate(row) for row in result.scalars().all()]
        except Exception as e:
            logging.error(f"Failed to read matches by tournament name: {e}")
            return []


class CreateData:
    @staticmethod
    async def create_match_data(match: MatchDataSchema, session: AsyncSession) -> bool:
        """Create match data with score, tournament, simulator data

        Args:
            match (MatchDataSchema): Match data with score, tournament, simulator data
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_score = Score(
                score_id=match.score.score_id,
                team0=match.score.team0,
                team1=match.score.team1,
            )
            new_tournament = Tournament(
                tournament_id=match.tournament.tournament_id,
                tournament_name=match.tournament.tournament_name,
            )

            new_match = Match(
                match_id=match.match_id,
                first_team_name=match.first_team_name,
                second_team_name=match.second_team_name,
                first_team_id=match.first_team_id,
                first_team_player1_id=match.first_team_player1_id,
                first_team_player2_id=match.first_team_player2_id,
                first_team_player3_id=match.first_team_player3_id,
                first_team_player4_id=match.first_team_player4_id,
                second_team_id=match.second_team_id,
                second_team_player1_id=match.second_team_player1_id,
                second_team_player2_id=match.second_team_player2_id,
                second_team_player3_id=match.second_team_player3_id,
                second_team_player4_id=match.second_team_player4_id,
                score_id=match.score_id,
                time_limit=match.time_limit,
                extra_end_time_limit=match.extra_end_time_limit,
                standard_end_count=match.standard_end_count,
                applied_rule=match.applied_rule,
                physical_simulator_id=match.physical_simulator_id,
                tournament_id=match.tournament_id,
                match_name=match.match_name,
                game_mode=match.game_mode,
                created_at=match.created_at,
                started_at=match.started_at,
            )

            new_md_settings = None
            if getattr(match, "mixed_doubles_settings", None) is not None:
                md = match.mixed_doubles_settings
                # At match creation time, power play is always unused, so both values must be None (DB NULL).
                # They are set to an end_number only when a team consumes power play during /end-setup.
                new_md_settings = MatchMixedDoublesSettings(
                    match_id=match.match_id,
                    positioned_stones_pattern=md.positioned_stones_pattern,
                    team0_power_play_end=None,
                    team1_power_play_end=None,
                    # Seed selector list (JSONB): end 0 selector defaults to the hammer team (second_team_id).
                    end_setup_team_ids=(
                        [str(x) for x in md.end_setup_team_ids]
                        if getattr(md, "end_setup_team_ids", None)
                        else [str(match.second_team_id)]
                    ),
                )

            items = [new_score, new_tournament, new_match]
            if new_md_settings is not None:
                items.append(new_md_settings)

            session.add_all(items)
            await session.commit()
            return True

        except Exception as e:
            await session.rollback()
            logging.exception(
                "Failed to create match data (match_id=%s, score_id=%s, simulator_id=%s, game_mode=%s): %s",
                getattr(match, "match_id", None),
                getattr(match, "score_id", None),
                getattr(match, "physical_simulator_id", None),
                getattr(match, "game_mode", None),
                e,
            )
            return False

    @staticmethod
    async def create_state_data(state: StateSchema, session: AsyncSession) -> bool:
        """Create state data with stone coordinate data

        Args:
            state (StateSchema): State data with stone coordinate data
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_stone_coordinate = StoneCoordinate(
                stone_coordinate_id=state.stone_coordinate.stone_coordinate_id,
                data=state.stone_coordinate.data,
            )

            new_state = State(
                state_id=state.state_id,
                winner_team_id=state.winner_team_id,
                match_id=state.match_id,
                end_number=state.end_number,
                team_shot_number=state.team_shot_number,
                total_shot_number=state.total_shot_number,
                first_team_remaining_time=state.first_team_remaining_time,
                second_team_remaining_time=state.second_team_remaining_time,
                first_team_extra_end_remaining_time=state.first_team_extra_end_remaining_time,
                second_team_extra_end_remaining_time=state.second_team_extra_end_remaining_time,
                stone_coordinate_id=state.stone_coordinate_id,
                score_id=state.score_id,
                shot_id=state.shot_id,
                next_shot_team_id=state.next_shot_team_id,
                created_at=state.created_at,
            )
            session.add_all([new_stone_coordinate, new_state])
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.exception(
                "Failed to create state data (state_id=%s, match_id=%s, end_number=%s, total_shot_number=%s): %s",
                getattr(state, "state_id", None),
                getattr(state, "match_id", None),
                getattr(state, "end_number", None),
                getattr(state, "total_shot_number", None),
                e,
            )
            return False

    @staticmethod
    async def add_state_data(state: StateSchema, session: AsyncSession) -> None:
        """Add state + stone coordinate rows to the current transaction without committing.

        This is used when the caller wants atomic multi-step updates under a DB lock.
        """
        new_stone_coordinate = StoneCoordinate(
            stone_coordinate_id=state.stone_coordinate.stone_coordinate_id,
            data=state.stone_coordinate.data,
        )

        new_state = State(
            state_id=state.state_id,
            winner_team_id=state.winner_team_id,
            match_id=state.match_id,
            end_number=state.end_number,
            team_shot_number=state.team_shot_number,
            total_shot_number=state.total_shot_number,
            first_team_remaining_time=state.first_team_remaining_time,
            second_team_remaining_time=state.second_team_remaining_time,
            first_team_extra_end_remaining_time=state.first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time=state.second_team_extra_end_remaining_time,
            stone_coordinate_id=state.stone_coordinate_id,
            score_id=state.score_id,
            shot_id=state.shot_id,
            next_shot_team_id=state.next_shot_team_id,
            created_at=state.created_at,
        )

        session.add_all([new_stone_coordinate, new_state])

    @staticmethod
    async def add_shot_info_data(shot_info: ShotInfoSchema, session: AsyncSession) -> None:
        """Add shot_info row to the current transaction without committing."""

        new_shot_info = ShotInfo(
            shot_id=shot_info.shot_id,
            player_id=shot_info.player_id,
            team_id=shot_info.team_id,
            trajectory_id=shot_info.trajectory_id,
            pre_shot_state_id=shot_info.pre_shot_state_id,
            post_shot_state_id=shot_info.post_shot_state_id,
            actual_translational_velocity=shot_info.actual_translational_velocity,
            actual_shot_angle=shot_info.actual_shot_angle,
            actual_angular_velocity=shot_info.actual_angular_velocity,
            translational_velocity=shot_info.translational_velocity,
            shot_angle=shot_info.shot_angle,
            angular_velocity=shot_info.angular_velocity,
        )
        session.add(new_shot_info)

    @staticmethod
    async def create_stone_data(stone: StoneCoordinateSchema, session: AsyncSession):
        """Create stone coordinate data

        Args:
            stone (StoneCoordinateSchema): Stone coordinate data
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_stone = StoneCoordinate(
                stone_coordinate_id=stone.stone_coordinate_id,
                data=stone.data,
            )
            session.add(new_stone)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create stone data: {e}")
            return False

    @staticmethod
    async def create_score_data(score: ScoreSchema, session: AsyncSession) -> bool:
        """Create score data

        Args:
            score (ScoreSchema): Score data with first team score and second team score
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_score = Score(
                score_id=score.score_id,
                team0=score.team0,
                team1=score.team1,
            )
            session.add(new_score)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create score data: {e}")
            return False

    @staticmethod
    async def create_shot_info_data(shot_info: ShotInfoSchema, session: AsyncSession) -> bool:
        """Create shot info data which is changed by dispersion rate

        Args:
            shot_info (ShotInfoSchema): Shot info data with translation velocity, angular velocity, shot angle
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_shot_info = ShotInfo(
                shot_id=shot_info.shot_id,
                player_id=shot_info.player_id,
                team_id=shot_info.team_id,
                trajectory_id=shot_info.trajectory_id,
                pre_shot_state_id=shot_info.pre_shot_state_id,
                post_shot_state_id=shot_info.post_shot_state_id,
                actual_translational_velocity=shot_info.actual_translational_velocity,
                actual_shot_angle=shot_info.actual_shot_angle,
                actual_angular_velocity=shot_info.actual_angular_velocity,
                translational_velocity=shot_info.translational_velocity,
                shot_angle=shot_info.shot_angle,
                angular_velocity=shot_info.angular_velocity,
            )
            session.add(new_shot_info)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create shot info data: {e}")
            return False

    @staticmethod
    async def create_tournament_data(
        tournament: TournamentSchema, session: AsyncSession
    ):
        """Create tournament data

        Args:
            tournament (TournamentSchema): Tournament data with tournament name
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_tournament = Tournament(
                tournament_id=tournament.tournament_id,
                tournament_name=tournament.tournament_name,
            )
            session.add(new_tournament)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create tournament data: {e}")
            return False

    @staticmethod
    async def create_physical_simulator_data(
        simulator: PhysicalSimulatorSchema, session: AsyncSession
    ):
        """Create physical simulator data

        Args:
            simulator (PhysicalSimulatorSchema): Physical simulator data with simulator name
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            stmt = select(PhysicalSimulator).where(
                PhysicalSimulator.simulator_name == simulator.simulator_name
            )
            result = await session.execute(stmt)
            result = result.scalars().first()
            if result is None:
                new_simulator = PhysicalSimulator(
                    physical_simulator_id=simulator.physical_simulator_id,
                    simulator_name=simulator.simulator_name,
                )
                session.add(new_simulator)
                await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create physical simulator data: {e}")
            return False

    @staticmethod
    async def create_default_player_data(player: PlayerSchema, session: AsyncSession) -> bool:
        """Create default player data to use learning AI

        Args:
            player (PlayerSchema): Player data with player name, team id, max velocity, shot dispersion rate
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            result = await session.execute(
                select(Player).where(Player.player_id == player.player_id)
            )
            player_data = result.scalars().first()
            if not player_data:
                new_player = Player(
                    player_id=player.player_id,
                    team_id=player.team_id,
                    max_velocity=player.max_velocity,
                    shot_std_dev=player.shot_std_dev,
                    angle_std_dev=player.angle_std_dev,
                    player_name=player.player_name,
                )
                session.add(new_player)
                await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create default player data: {e}")
            return False

    @staticmethod
    async def create_player_data(player: PlayerSchema, session: AsyncSession) -> bool:
        """Create player data with player name, team id, max velocity, shot dispersion rate

        Args:
            player (PlayerSchema): Player data with player name, team id, max velocity, shot dispersion rate
            session (AsyncSession): AsyncSession object to interact with database
        """
        try:
            new_player = Player(
                player_id=player.player_id,
                team_id=player.team_id,
                max_velocity=player.max_velocity,
                shot_std_dev=player.shot_std_dev,
                angle_std_dev=player.angle_std_dev,
                player_name=player.player_name,
            )
            session.add(new_player)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Failed to create player data: {e}")
            return False


class CollectID:
    @staticmethod
    async def collect_state_ids(session: AsyncSession) -> List[UUID]:
        """Collect all state ids from state table
        Args:
            session (AsyncSession): AsyncSession object to interact with database

        Returns:
            List[UUID]: List of state ids
        """
        try:
            stmt = select(State.state_id)
            result = await session.execute(stmt)
            state_ids = result.scalars().all()
            return state_ids

        except Exception as e:
            logging.error(f"Failed to collect state ids: {e}")
            return []
