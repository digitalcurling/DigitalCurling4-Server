"""DB service layer for match-related use cases.

- Routers should not touch DB sessions directly; they call this module.
- This layer owns session/transaction boundaries.
- Use CRUD helpers that do NOT commit inside session.begin().
"""

from datetime import datetime
from uuid import UUID

from src.crud import CreateData, ReadData, UpdateData
from src.db import Session
from src.domain.match_rules import generate_mixed_doubles_initial_stones
from src.models.dc_models import PositionedStonesModel
from src.models.schema_models import (
    MatchDataSchema,
    PlayerSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
)
from uuid6 import uuid7


async def read_match_data(match_id: UUID) -> MatchDataSchema | None:
    async with Session() as session:
        return await ReadData.read_match_data(match_id, session)


async def read_latest_state_data(match_id: UUID) -> StateSchema | None:
    async with Session() as session:
        return await ReadData.read_latest_state_data(match_id, session)


async def read_player_data(player_id: UUID) -> PlayerSchema | None:
    async with Session() as session:
        return await ReadData.read_player_data(player_id, session)


async def read_simulator_id(simulator_name: str) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_simulator_id(simulator_name, session)


async def read_team_id(team_name: str) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_team_id(team_name, session)


async def read_player_id(player_name: str, team_id: UUID) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_player_id(player_name, team_id, session)


async def create_match_data(match_data: MatchDataSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_match_data(match_data, session)
        if not success:
            raise RuntimeError("Failed to create match data")


async def create_state_data(state: StateSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_state_data(state, session)
        if not success:
            raise RuntimeError("Failed to create state data")


async def create_player_data(player: PlayerSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_player_data(player, session)
        if not success:
            raise RuntimeError("Failed to create player data")


async def record_shot_result(
    shot_info: ShotInfoSchema,
    post_state: StateSchema,
    pre_state_id: UUID,
) -> None:
    """Create shot_info + post state, then link pre_state.shot_id in one transaction.

    NOTE: Do not call CRUD helpers that commit() inside this transaction.
    """

    async with Session() as session:
        async with session.begin():
            await CreateData.add_shot_info_data(shot_info, session)
            await CreateData.add_state_data(post_state, session)
            await UpdateData.set_state_shot_id_no_commit(pre_state_id, shot_info.shot_id, session)


async def update_match_data_with_team_name(
    match_id: UUID,
    team_name: str,
    expected_match_team_name: str,
) -> str | None:
    async with Session() as session:
        return await UpdateData.update_match_data_with_team_name(
            match_id, session, team_name, expected_match_team_name
        )


async def update_first_team(match_id: UUID, team_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_first_team(match_id, session, team_id, player_id_list, team_name)


async def update_second_team(match_id: UUID, team_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_second_team(match_id, session, team_id, player_id_list, team_name)


async def update_next_shot_team(match_id: UUID, team_id: UUID) -> None:
    async with Session() as session:
        await UpdateData.update_next_shot_team(match_id, team_id, session)


async def update_score(score) -> None:
    async with Session() as session:
        await UpdateData.update_score(score, session)


async def perform_mix_doubles_end_setup(
    match_data: MatchDataSchema,
    latest_state: StateSchema,
    match_team_name: str,
    request: PositionedStonesModel,
) -> UUID:
    """DB-backed end-setup (transactional).

    Responsibilities:
    - Authorize the caller against match_mix_doubles_settings.end_setup_team_ids[end_number].
    - Enforce power play rules (only once per team; disabled in extra ends).
    - Generate initial positioned stones and create the setup State for the end.

    The router is responsible for:
    - Authentication/authorization at the HTTP layer
    - Returning the right HTTP status code for ValueError vs other exceptions
    - Publishing redis events

    Args:
        match_data: MatchDataSchema of the match.
        latest_state: Latest StateSchema of the match.
        match_team_name: "team0" or "team1" of the caller.
        request: PositionedStonesModel from the client.
    """

    async with Session() as session:
        async with session.begin():
            # Caller is the team that is allowed to choose the positioned-stones pattern.
            caller_team_id = match_data.first_team_id if match_team_name == "team0" else match_data.second_team_id
            other_team_id = match_data.second_team_id if match_team_name == "team0" else match_data.first_team_id
            other_team_name = "team1" if match_team_name == "team0" else "team0"

            # Lock settings row to read/update power play usage and selector list.
            settings_row = await ReadData.read_mix_doubles_settings_row_for_update(
                match_data.match_id, session
            )
            if settings_row is None:
                raise RuntimeError("Mixed doubles settings row not found.")

            selector_list = settings_row.end_setup_team_ids or []
            # Seed list if missing (shouldn't happen in fresh DB).
            if not selector_list:
                selector_list = [str(match_data.second_team_id)]
                settings_row.end_setup_team_ids = selector_list

            current_end = latest_state.end_number
            if current_end < 0:
                raise ValueError("Invalid end_number")

            if current_end >= len(selector_list):
                raise ValueError("end_setup_team_ids is missing entries for current end.")

            # Authorization: only the expected selector team can run end-setup for this end.
            expected_selector_team_id = UUID(str(selector_list[current_end]))
            if caller_team_id != expected_selector_team_id:
                raise ValueError("Not your turn to setup positioned stones.")

            # Request parsing:
            # Curling definitions used here:
            # - "hammer" means the team that throws SECOND in the end.
            # - Positioned stones: one stone in the house + one guard.
            #   The team who is hammer gets the house stone; the lead team gets the guard.
            #
            # Client options:
            # - pp_left/pp_right: selector becomes hammer and may use power play; selector gets the house stone.
            # - center_house: selector becomes hammer (no power play); selector gets the house stone.
            # - center_guard: selector becomes lead; selector gets the guard stone (pattern-based).
            if request == PositionedStonesModel.pp_left:
                power_play_side: str | None = "left"
                selector_is_hammer = True
            elif request == PositionedStonesModel.pp_right:
                power_play_side = "right"
                selector_is_hammer = True
            elif request == PositionedStonesModel.center_house:
                power_play_side = None
                selector_is_hammer = True
            elif request == PositionedStonesModel.center_guard:
                power_play_side = None
                selector_is_hammer = False
            else:
                raise ValueError("Invalid positioned_stones option.")
            power_play_requested: bool = power_play_side is not None

            # Mixed doubles rule: power play cannot be used in extra ends.
            # If requested during extra end, treat it as center_house.
            is_extra_end = (current_end >= match_data.standard_end_count)
            if power_play_requested and is_extra_end:
                power_play_side = None
                selector_is_hammer = True
                power_play_requested = False

            # Determine throw order and which team is hammer for this end.
            # After end-setup, the lead team throws first.
            if selector_is_hammer:
                hammer_team_name = match_team_name
                first_throw_team_id = other_team_id
            else:
                hammer_team_name = other_team_name
                first_throw_team_id = caller_team_id

            if power_play_requested:
                used_end = (
                    settings_row.team0_power_play_end
                    if match_team_name == "team0"
                    else settings_row.team1_power_play_end
                )
                if used_end is not None:
                    # Do not block the match if client mistakenly requests power play twice.
                    # Fall back to the default behavior (center_house) and continue setup.
                    power_play_side = None
                    selector_is_hammer = True
                    power_play_requested = False
                else:
                    if match_team_name == "team0":
                        settings_row.team0_power_play_end = current_end
                    else:
                        settings_row.team1_power_play_end = current_end

            # If power play was disabled above (extra end or already used),
            # recompute throw order for the effective request (center_house).
            if selector_is_hammer:
                hammer_team_name = match_team_name
                first_throw_team_id = other_team_id
            else:
                hammer_team_name = other_team_name
                first_throw_team_id = caller_team_id

            # positioned_stones_pattern is chosen at match creation time.
            pattern = match_data.mix_doubles_settings.positioned_stones_pattern
            stone_data = generate_mixed_doubles_initial_stones(
                hammer_team_name,
                power_play_side,
                pattern,
                # By rule: hammer gets the house stone, lead gets the guard.
                hammer_stone_position="house",
            )

            stone_coordinate = StoneCoordinateSchema(
                stone_coordinate_id=uuid7(),
                data=stone_data,
            )

            setup_state = StateSchema(
                state_id=uuid7(),
                winner_team_id=None,
                match_id=match_data.match_id,
                end_number=latest_state.end_number,
                shot_number=0,
                total_shot_number=0,
                first_team_remaining_time=latest_state.first_team_remaining_time,
                second_team_remaining_time=latest_state.second_team_remaining_time,
                first_team_extra_end_remaining_time=latest_state.first_team_extra_end_remaining_time,
                second_team_extra_end_remaining_time=latest_state.second_team_extra_end_remaining_time,
                stone_coordinate_id=stone_coordinate.stone_coordinate_id,
                score_id=latest_state.score_id,
                shot_id=None,
                next_shot_team_id=first_throw_team_id,
                created_at=datetime.now(),
                stone_coordinate=stone_coordinate,
            )
            await CreateData.add_state_data(setup_state, session)

            return setup_state.state_id


async def set_end_setup_team_for_end(
    *,
    match_id: UUID,
    end_number: int,
    selector_team_id: UUID,
) -> None:
    """Persist selector (hammer) team for an end.

    Stored as JSONB list: match_mix_doubles_settings.end_setup_team_ids
    - Index corresponds to end_number (0-based).

    Typical call site:
    - After end N is scored, compute selector for end N+1 and call with end_number=N+1.

    Args:
        match_id: Match ID.
        end_number: End number (0-based).
        selector_team_id: Team ID that has the right to choose positioned stones for this end.

    Notes:
    - This function is strict: it allows setting an existing index or appending the next index.
      If there is a gap, it indicates a bug in the match flow.
    """
    async with Session() as session:
        async with session.begin():
            settings_row = await ReadData.read_mix_doubles_settings_row_for_update(match_id, session)
            if settings_row is None:
                raise RuntimeError("Mixed doubles settings row not found.")

            # IMPORTANT: JSONB returns a plain Python list. In-place mutations (append/index-assign)
            # are NOT reliably tracked by SQLAlchemy unless using MutableList.
            # Always copy to a new list, mutate, then assign back.
            selector_list = list(settings_row.end_setup_team_ids)
            if not selector_list:
                # Seed end 0 if missing.
                selector_list = [str(selector_team_id)]

            if end_number < 0:
                raise ValueError("end_number must be >= 0")

            if end_number < len(selector_list):
                selector_list[end_number] = str(selector_team_id)
            elif end_number == len(selector_list):
                selector_list.append(str(selector_team_id))
            else:
                raise RuntimeError("end_setup_team_ids has a gap; cannot set future end without previous entries.")

            settings_row.end_setup_team_ids = selector_list
