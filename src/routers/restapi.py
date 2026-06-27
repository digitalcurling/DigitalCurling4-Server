import logging
from typing import List

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from src.crud import CollectID, ReadData
from src.db import Session
from src.routers.http_exceptions import not_found
from src.models.schemas import Match as MatchRow, ShotInfo as ShotInfoRow, State as StateRow
from src.models.schema_models import (
    MatchDataSchema,
    MatchSummarySchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
    TournamentSchema,
)

logging.basicConfig(level=logging.DEBUG)

rest_router = APIRouter()


async def _resolve_latest_match_id_by_name(session, match_name: str) -> UUID:
    """Resolve the latest match ID for a given match name.

    Args:
        session: Active database session.
        match_name: Match name used for filtering.

    Returns:
        UUID: Match ID of the most recently started match with the given name.

    Raises:
        HTTPException: If no match exists for the provided name.
    """

    stmt = (
        select(MatchRow.match_id)
        .where(MatchRow.match_name == match_name)
        .order_by(MatchRow.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    match_id = result.scalars().first()
    if match_id is None:
        raise not_found("Match not found.")
    return match_id


class MatchAPI:
    """Read-only endpoints for match-level resources."""

    @staticmethod
    @rest_router.get("/matches/{match_id}", response_model=MatchDataSchema)
    async def get_match(match_id: UUID):
        """Get match data by match identifier.

        Args:
            match_id: Match identifier.

        Returns:
            MatchDataSchema: Match details including related nested data when available.

        Raises:
            HTTPException: If the match does not exist.
        """

        async with Session() as session:
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")
            return match_data

    @staticmethod
    @rest_router.get("/matches/by-name/latest", response_model=MatchDataSchema)
    async def get_match_by_name_latest(match_name: str = Query(..., min_length=1)):
        """Get the latest started match by match name.

        Args:
            match_name: Match name used to resolve the latest match.

        Returns:
            MatchDataSchema: Match details for the latest matching match.

        Raises:
            HTTPException: If no matching match is found.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")
            return match_data

    @staticmethod
    @rest_router.get("/matches/{match_id}/score", response_model=ScoreSchema)
    async def get_match_score(match_id: UUID):
        """Get score data for a match by ID.

        Args:
            match_id: Match identifier.

        Returns:
            ScoreSchema: Score data for the specified match.

        Raises:
            HTTPException: If the match or its score data is not found.
        """

        async with Session() as session:
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None or match_data.score is None:
                raise not_found("Match not found.")
            return match_data.score

    @staticmethod
    @rest_router.get("/matches/by-name/score", response_model=ScoreSchema)
    async def get_match_score_by_name(match_name: str = Query(..., min_length=1)):
        """Get score data for the latest match by match name.

        Args:
            match_name: Match name used to resolve the latest match.

        Returns:
            ScoreSchema: Score data for the resolved match.

        Raises:
            HTTPException: If the match or its score data is not found.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None or match_data.score is None:
                raise not_found("Match not found.")
            return match_data.score

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/stone-coordinate/latest",
        response_model=StoneCoordinateSchema,
    )
    async def get_latest_stone_coordinate(match_id: UUID):
        """Get the latest stone coordinates in a match.

        Args:
            match_id: Match identifier.

        Returns:
            StoneCoordinateSchema: Latest stone coordinate snapshot.

        Raises:
            HTTPException: If the match state or stone coordinates are not found.
        """

        async with Session() as session:
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None or latest_state.stone_coordinate is None:
                raise not_found("Stone coordinate not found.")
            return latest_state.stone_coordinate

    @staticmethod
    @rest_router.get(
        "/matches/by-name/stone-coordinate/latest",
        response_model=StoneCoordinateSchema,
    )
    async def get_latest_stone_coordinate_by_name(match_name: str = Query(..., min_length=1)):
        """Get latest stone coordinates for the latest match by name.

        Args:
            match_name: Match name used to resolve the latest match.

        Returns:
            StoneCoordinateSchema: Latest stone coordinate snapshot.

        Raises:
            HTTPException: If no matching state or coordinates are found.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None or latest_state.stone_coordinate is None:
                raise not_found("Stone coordinate not found.")
            return latest_state.stone_coordinate

    @staticmethod
    @rest_router.get("/matches/{match_id}/ends", response_model=List[int])
    async def list_match_ends(match_id: UUID):
        """List end numbers from start to the latest available end.

        Args:
            match_id: Match identifier.

        Returns:
            List[int]: End numbers from 0 through the latest end.

        Raises:
            HTTPException: If the match is not found.
        """

        async with Session() as session:
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None:
                raise not_found("Match not found.")
            # Current end_number is the latest state's end_number.
            return list(range(0, int(latest_state.end_number) + 1))

    @staticmethod
    @rest_router.get("/matches/by-name/ends", response_model=List[int])
    async def list_match_ends_by_name(match_name: str = Query(..., min_length=1)):
        """List end numbers for the latest match resolved by name.

        Args:
            match_name: Match name used to resolve the latest match.

        Returns:
            List[int]: End numbers from 0 through the latest end.

        Raises:
            HTTPException: If the match is not found.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None:
                raise not_found("Match not found.")
            return list(range(0, int(latest_state.end_number) + 1))

    @staticmethod
    @rest_router.get("/matches/{match_id}/latest-state", response_model=StateSchema)
    async def get_latest_state(match_id: UUID):
        """Get the latest state snapshot of a match.

        Args:
            match_id: Match identifier.

        Returns:
            StateSchema: Latest state data.

        Raises:
            HTTPException: If no state is found for the match.
        """

        async with Session() as session:
            state_data = await ReadData.read_latest_state_data(match_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get("/matches/by-name/latest-state", response_model=StateSchema)
    async def get_latest_state_by_name(match_name: str = Query(..., min_length=1)):
        """Get the latest state snapshot for the latest match by name.

        Args:
            match_name: Match name used to resolve the latest match.

        Returns:
            StateSchema: Latest state data.

        Raises:
            HTTPException: If no state is found.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            state_data = await ReadData.read_latest_state_data(match_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/states",
        response_model=List[StateSchema],
    )
    async def get_states_in_end(match_id: UUID, end_number: int):
        """Get all state snapshots in a specific end for a match.

        Args:
            match_id: Match identifier.
            end_number: End index to fetch.

        Returns:
            List[StateSchema]: State snapshots in the specified end.
        """

        async with Session() as session:
            return await ReadData.read_state_data_in_end(match_id, end_number, session)

    @staticmethod
    @rest_router.get(
        "/matches/by-name/ends/{end_number}/states",
        response_model=List[StateSchema],
    )
    async def get_states_in_end_by_name(
        end_number: int,
        match_name: str = Query(..., min_length=1),
    ):
        """Get all state snapshots in an end for the latest match by name.

        Args:
            end_number: End index to fetch.
            match_name: Match name used to resolve the latest match.

        Returns:
            List[StateSchema]: State snapshots in the specified end.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            return await ReadData.read_state_data_in_end(match_id, end_number, session)

    # @staticmethod
    # @rest_router.post("/add_match", response_model=MatchDataSchema)
    # async def add_match(match: MatchModel):
    #     response = MatchDataSchema(
    #         match_id=match.match_id,
    #         first_team_id=uuid7(),
    #         second_team_id=uuid7(),
    #         score_id=uuid7(),
    #         time_limit=match.time_limit,
    #         extra_end_time_limit=match.extra_end_time_limit,
    #         standard_end_count=match.standard_end_count,
    #         physical_simulator_id=uuid4(),
    #         tournament_id=uuid7(),
    #         match_name=match.match_name,
    #         created_at=datetime.fromtimestamp(0),
    #         started_at=datetime.fromtimestamp(0)
    #     )
    #     logging.info(f"response: {response}")
    #     await CreateData.create_match_data(response)


class StateAPI:
    """Read-only endpoints for state-level resources."""

    @staticmethod
    @rest_router.get("/states/{state_id}", response_model=StateSchema)
    async def get_state(state_id: UUID):
        """Get a state snapshot by state identifier.

        Args:
            state_id: State identifier.

        Returns:
            StateSchema: Requested state snapshot.

        Raises:
            HTTPException: If the state is not found.
        """

        async with Session() as session:
            state_data = await ReadData.read_state_data(state_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get("/states", response_model=List[UUID])
    async def collect_state():
        """Collect all state identifiers.

        Returns:
            List[UUID]: Existing state identifiers.
        """

        async with Session() as session:
            state_id = await CollectID.collect_state_ids(session)
            return state_id


class MatchShotsAPI:
    """Read-only endpoints for match shot history."""

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/shots",
        response_model=List[ShotInfoSchema],
    )
    async def list_shots_in_end(match_id: UUID, end_number: int):
        """List shots in a specific end of a match.

        Args:
            match_id: Match identifier.
            end_number: End index to fetch.

        Returns:
            List[ShotInfoSchema]: Shots ordered by shot number.

        Raises:
            HTTPException: If the match is not found.
        """

        async with Session() as session:
            # Ensure match exists (friendlier 404 than empty list on typo).
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")

            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(StateRow.match_id == match_id, StateRow.end_number == end_number)
                .order_by(StateRow.total_shot_number)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [ShotInfoSchema.model_validate(r) for r in rows]

    @staticmethod
    @rest_router.get(
        "/matches/by-name/ends/{end_number}/shots",
        response_model=List[ShotInfoSchema],
    )
    async def list_shots_in_end_by_name(
        end_number: int,
        match_name: str = Query(..., min_length=1),
    ):
        """List shots in an end for the latest match by name.

        Args:
            end_number: End index to fetch.
            match_name: Match name used to resolve the latest match.

        Returns:
            List[ShotInfoSchema]: Shots ordered by shot number.
        """

        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(StateRow.match_id == match_id, StateRow.end_number == end_number)
                .order_by(StateRow.total_shot_number)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [ShotInfoSchema.model_validate(r) for r in rows]

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/shots/{total_shot_number}",
        response_model=ShotInfoSchema,
    )
    async def get_shot_in_end(match_id: UUID, end_number: int, total_shot_number: int):
        """Get one shot record identified by end and shot number.

        Args:
            match_id: Match identifier.
            end_number: End index.
            total_shot_number: Shot index within the end (unique per end, 0-based).

        Returns:
            ShotInfoSchema: Shot details for the requested index.

        Raises:
            HTTPException: If no matching shot is found.
        """

        async with Session() as session:
            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(
                    StateRow.match_id == match_id,
                    StateRow.end_number == end_number,
                    StateRow.total_shot_number == total_shot_number,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if row is None:
                raise not_found("Shot info not found.")
            return ShotInfoSchema.model_validate(row)

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/shots/latest",
        response_model=ShotInfoSchema,
    )
    async def get_latest_shot(match_id: UUID):
        """Get the latest shot record in a match.

        Args:
            match_id: Match identifier.

        Returns:
            ShotInfoSchema: Latest shot information.

        Raises:
            HTTPException: If the match or latest shot is not found.
        """

        async with Session() as session:
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")
            shot_info = await ReadData.read_latest_shot_info_by_match_id(match_id, session)
            if shot_info is None:
                raise not_found("No shots have been thrown yet.")
            return shot_info


class StonePositionAPI:
    """Read-only endpoint for stone coordinate resources."""

    @staticmethod
    @rest_router.get(
        "/stone_coordinate/{stone_coordinate_id}",
        response_model=StoneCoordinateSchema,
    )
    async def get_stone_position(stone_coordinate_id: UUID):
        """Get a stone coordinate snapshot by identifier.

        Args:
            stone_coordinate_id: Stone coordinate identifier.

        Returns:
            StoneCoordinateSchema: Stored stone coordinate data.

        Raises:
            HTTPException: If the stone coordinate record is not found.
        """

        async with Session() as session:
            stone_data = await ReadData.read_stone_data(stone_coordinate_id, session)
            if stone_data is None:
                raise not_found("Stone coordinate not found.")
            return stone_data


class ScoreAPI:
    """Read-only endpoints for score resources."""

    @staticmethod
    @rest_router.get("/scores/{score_id}", response_model=ScoreSchema)
    async def get_score(score_id: UUID):
        """Get score data by score identifier.

        Args:
            score_id: Score identifier.

        Returns:
            ScoreSchema: Stored score data.

        Raises:
            HTTPException: If the score is not found.
        """

        logging.info(f"score_id: {score_id}")
        async with Session() as session:
            score_data = await ReadData.read_score_data(score_id, session)
            if score_data is None:
                raise not_found("Score not found.")
            return score_data


class ShotInfoAPI:
    """Read-only endpoints for shot information resources."""

    @staticmethod
    @rest_router.get("/shots/{shot_id}", response_model=ShotInfoSchema)
    async def get_shot_info(shot_id: UUID):
        """Get shot information by shot identifier.

        Args:
            shot_id: Shot identifier.

        Returns:
            ShotInfoSchema: Shot information record.

        Raises:
            HTTPException: If the shot information is not found.
        """

        async with Session() as session:
            shot_info = await ReadData.read_shot_info_data(shot_id, session)
            if shot_info is None:
                raise not_found("Shot info not found.")
            return shot_info

    @staticmethod
    @rest_router.get(
        "/shots/by-post-state/{post_state_id}",
        response_model=ShotInfoSchema,
    )
    async def get_shot_info_by_post_state(post_state_id: UUID):
        """Get the latest shot info linked to a post-shot state.

        Args:
            post_state_id: Post-shot state identifier.

        Returns:
            ShotInfoSchema: Latest shot information for the state.

        Raises:
            HTTPException: If no shot information is found.
        """

        async with Session() as session:
            shot_info = await ReadData.read_last_shot_info_by_post_state_id(post_state_id, session)
            if shot_info is None:
                raise not_found("Shot info not found.")
            return shot_info


class TournamentAPI:
    """Read-only endpoints for tournament listing."""

    @staticmethod
    @rest_router.get("/tournaments", response_model=List[TournamentSchema])
    async def list_tournaments():
        """List all tournaments ordered by name.

        Returns:
            List[TournamentSchema]: All tournaments.
        """

        async with Session() as session:
            return await ReadData.read_all_tournaments(session)


class MatchListAPI:
    """Read-only endpoints for listing matches with filters."""

    @staticmethod
    @rest_router.get("/matches", response_model=List[MatchSummarySchema])
    async def list_matches(tournament_name: str = Query(..., min_length=1)):
        """List matches filtered by tournament name, ordered by start time descending.

        Args:
            tournament_name: Tournament name to filter by.

        Returns:
            List[MatchSummarySchema]: Matches with team0/team1 names and result.

        Raises:
            HTTPException: If no matches are found for the given tournament name.
        """

        async with Session() as session:
            matches = await ReadData.read_matches_by_tournament_name(tournament_name, session)
            if not matches:
                raise not_found("Tournament not found or has no matches.")
            return matches
