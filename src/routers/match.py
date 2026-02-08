import logging
import json
from datetime import datetime, timedelta
from typing import List
from uuid import UUID, uuid4
from uuid6 import uuid7
import numpy as np
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic
from redis.asyncio import Redis

from src.routers.http_exceptions import bad_request, conflict, not_found
from src.db import Session
from src.services import match_db
from src.models.dc_models import (
    ClientDataModel,
    PositionedStonesModel,
    ShotInfoModel,
    TeamModel,
    MatchNameModel,
    AppliedRuleModel,
    GameModeModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    MatchMixDoublesSettingsSchema,
    PhysicalSimulatorSchema,
    PlayerSchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
    TournamentSchema,
)
from src.models.basic_authentication_models import UserModel
from src.converter import DataConverter
from src.redis_subscriber import RedisSubscriber
from src.domain.match_rules import (
    calculate_total_score,
    generate_reset_stone_coordinate_data,
    get_score_from_distance_list,
    stone_count_per_team,
    stone_distance_from_tee,
    total_shots_per_end as get_total_shots_per_end,
)
from src.services.simulation import simulate_fcv1
from src.authentication.basic_authentication import BasicAuthentication
from src.authentication.basic_authentication_crud import (
    CreateAuthentication,
    ReadAuthentication,
    DeleteAuthentication,
)
from src.simulator import StoneSimulator

redis = Redis(host="redis", port=6379, decode_responses=True, health_check_interval=30)

match_router = APIRouter()
logging.basicConfig(level=logging.INFO)
security = HTTPBasic()
rest_router = APIRouter()
data_converter = DataConverter()
read_authentication = ReadAuthentication()
create_authentication = CreateAuthentication()
delete_authentication = DeleteAuthentication()
basic_auth = BasicAuthentication()
stone_simulator = StoneSimulator()


async def state_end_number_update(state_data: StateSchema, next_shot_team_id: UUID | None):
    """Update the state data when the end number is updated

    Args:
        state_data (StateSchema): The latest state data of the match which is the state data at the end of the "end"
        next_shot_team_id (UUID): The team ID of the next shot
    """
    
    total_shot_number: int | None = 0

    # In mixed doubles, we wait for an explicit end-setup command before allowing shots.
    match_data: MatchDataSchema | None = await match_db.read_match_data(state_data.match_id)
    if match_data is None:
        raise not_found("Match not found.")

    is_mix_doubles = match_data.game_mode == GameModeModel.mix_doubles.value
    if is_mix_doubles:
        next_shot_team_id = None
        total_shot_number = None
    elif next_shot_team_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="next_shot_team_id must not be None in standard mode.",
        )

    stone_coordinate: StoneCoordinateSchema = StoneCoordinateSchema(
        stone_coordinate_id=uuid7(),
        data=generate_reset_stone_coordinate_data(match_data.game_mode),
    )

    state = StateSchema(
        state_id=uuid7(),
        winner_team_id=state_data.winner_team_id,
        match_id=state_data.match_id,
        end_number=state_data.end_number + 1,
        shot_number=None if total_shot_number is None else int(total_shot_number / 2),
        total_shot_number=total_shot_number,
        first_team_remaining_time=state_data.first_team_remaining_time,
        second_team_remaining_time=state_data.second_team_remaining_time,
        first_team_extra_end_remaining_time=state_data.first_team_extra_end_remaining_time,
        second_team_extra_end_remaining_time=state_data.second_team_extra_end_remaining_time,
        stone_coordinate_id=stone_coordinate.stone_coordinate_id,
        score_id=state_data.score_id,
        shot_id=None,
        next_shot_team_id=next_shot_team_id,
        created_at=datetime.now(),
        stone_coordinate=stone_coordinate,
    )
    await match_db.create_state_data(state)
    channel = f"match:{state_data.match_id}"
    await redis.publish(
        channel,
        json.dumps(
            {
                "type": "state_update",
                "match_id": str(state_data.match_id),
                "state_id": str(state.state_id),
            }
        ),
    )
class BaseServer:
    """Endpoint class for initiating match."""
    @staticmethod
    @match_router.post("/matches", response_model=UUID)
    async def start_match(
        client_data: ClientDataModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ) -> UUID:
        """Send the match_id to the client and Set up the match data

        Args:
            client_data (ClientDataModel):
                    tournament: TournamentNameModel
                    simulator: PhysicalSimulatorNameModel
                    applied_rule: AppliedRuleModel
                    time_limit: float
                    extra_end_time_limit: float
                    standard_end_count: int
                    match_name: str
            valid (bool): Basic authentication result

        Returns:
            UUID: send the match_id to the client
        """

        match_id: UUID = uuid7()
        score_id: UUID = uuid7()
        tournament_id: UUID = uuid7()
        simulator_id: UUID = None
        applied_rule_name: AppliedRuleModel = None
        applied_rule: int = None

        # ======= Validate client data =======
        if client_data.game_mode == GameModeModel.mix_doubles:
            if client_data.positioned_stones_pattern is None:
                client_data.positioned_stones_pattern = 0
            if client_data.positioned_stones_pattern < 0 or client_data.positioned_stones_pattern > 5:
                raise bad_request("positioned_stones_pattern must be between 0 and 5.")

        simulator_id = await match_db.read_simulator_id(client_data.simulator.simulator_name)
        if simulator_id is None:
            raise not_found("Simulator not found.")
        
        if client_data.applied_rule is None:
            raise bad_request("Applied rule is required.")

        # Pydantic already validates this as AppliedRuleModel.
        applied_rule_name = client_data.applied_rule

        if client_data.game_mode == GameModeModel.mix_doubles and applied_rule_name != AppliedRuleModel.modified_fgz_rule:
            raise bad_request('Mixed doubles only supports "modified_fgz_rule".')

        if client_data.game_mode == GameModeModel.standard and applied_rule_name == AppliedRuleModel.modified_fgz_rule:
            raise bad_request('Standard game mode does not support "modified_fgz_rule".')
        
        if applied_rule_name == AppliedRuleModel.fgz_rule:
            applied_rule = 0
        elif applied_rule_name == AppliedRuleModel.no_tick_rule:
            applied_rule = 1
        elif applied_rule_name == AppliedRuleModel.modified_fgz_rule:
            applied_rule = 2
        else:
            raise bad_request(
                'Invalid applied rule. Please choose "fgz_rule", "no_tick_rule", or "modified_fgz_rule".'
            )
# ==================================

        # Add one score index for when the game goes into overtime
        team_score: List = [0] * (client_data.standard_end_count + 1)

        # Create stone coordinate data(all stones at (0,0))
        stone_coordinate: StoneCoordinateSchema = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(),
            data=generate_reset_stone_coordinate_data(client_data.game_mode.value),
        )

        state = StateSchema(
            state_id=uuid7(),
            winner_team_id=None,
            match_id=match_id,
            end_number=0,
            shot_number=None if client_data.game_mode == GameModeModel.mix_doubles else 0,
            total_shot_number=None if client_data.game_mode == GameModeModel.mix_doubles else 0,
            first_team_remaining_time=client_data.time_limit,
            second_team_remaining_time=client_data.time_limit,
            first_team_extra_end_remaining_time=client_data.extra_end_time_limit,
            second_team_extra_end_remaining_time=client_data.extra_end_time_limit,
            stone_coordinate_id=stone_coordinate.stone_coordinate_id,
            score_id=score_id,
            shot_id=None,
            # In mixed doubles, the first end requires an explicit end-setup command.
            next_shot_team_id=None
            if client_data.game_mode == GameModeModel.mix_doubles
            else "5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate,
        )
        # Create score data
        score: ScoreSchema = ScoreSchema(
            score_id=score_id, team0=team_score, team1=team_score
        )
        # Create simulator data
        simulator: PhysicalSimulatorSchema = PhysicalSimulatorSchema(
            physical_simulator_id=simulator_id,
            simulator_name=client_data.simulator.simulator_name,
        )
        # Create tournament data
        tournament: TournamentSchema = TournamentSchema(
            tournament_id=tournament_id,
            tournament_name=client_data.tournament.tournament_name,
        )
        # Create match data
        match_data: MatchDataSchema = MatchDataSchema(
            match_id=match_id,
            first_team_name=None,
            second_team_name=None,
            first_team_id="5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
            first_team_player1_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",  # Set the ID of the player to be used in AI matches as default
            first_team_player2_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",
            first_team_player3_id=None if client_data.game_mode == GameModeModel.mix_doubles else "006951d4-37b2-48eb-85a2-af9463a1e7aa",
            first_team_player4_id=None if client_data.game_mode == GameModeModel.mix_doubles else "006951d4-37b2-48eb-85a2-af9463a1e7aa",
            second_team_id="60e1e056-3613-4846-afc9-514ea7b6adde",
            second_team_player1_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",  # Set the ID of the player to be used in AI matches as default
            second_team_player2_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            second_team_player3_id=None if client_data.game_mode == GameModeModel.mix_doubles else "0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            second_team_player4_id=None if client_data.game_mode == GameModeModel.mix_doubles else "0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            winner_team_id=None,
            score_id=score_id,
            time_limit=client_data.time_limit,
            standard_end_count=client_data.standard_end_count,
            extra_end_time_limit=client_data.extra_end_time_limit,
            applied_rule=applied_rule,
            physical_simulator_id=simulator_id,
            tournament_id=tournament_id,
            match_name=client_data.match_name,
            game_mode=client_data.game_mode.value,
            mix_doubles_settings=(
                MatchMixDoublesSettingsSchema(
                    positioned_stones_pattern=int(client_data.positioned_stones_pattern),
                    team0_power_play_end=None,
                    team1_power_play_end=None,
                    # Per rules: end 0 selector is the hammer team (team1 = second_team_id).
                    end_setup_team_ids=[UUID(str("60e1e056-3613-4846-afc9-514ea7b6adde"))],
                )
                if client_data.game_mode == GameModeModel.mix_doubles
                else None
            ),
            created_at=datetime.now(),
            started_at=datetime.now(),
            score=score,
            simulator=simulator,
            tournament=tournament,
        )

        await match_db.create_match_data(match_data)
        await match_db.create_state_data(state)

        return match_id


class DCServer:
    """A server class that provides the main API endpoints for the entire match,
    including match initiation and state management.
    """

    # ==============================================================================
    # ==== Standard & Mixed doubles EndPoint =======================================
    # ==============================================================================

    @staticmethod
    @match_router.post("/store-team-config")
    async def store_team_config(
        match_id: UUID,
        expected_match_team_name: MatchNameModel,
        team_config_data: TeamModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ):
        """Store the team configuration data in the database

        Args:
            match_id (UUID): To identify the match
            expected_match_team_name (MatchNameModel):  The team name used in this match.
                                                        If you choose team0 to select the first attacker and your opponent has not yet set up team0, you can continue to use team0, and if your opponent uses team0, you become team1.
            team_config_data (TeamModel): The team configuration data
            user_data (UserModel): The user data for authentication
        """
        match_data: MatchDataSchema | None = await match_db.read_match_data(match_id)
        match_team_name: str | None = await match_db.update_match_data_with_team_name(
            match_id,
            team_config_data.team_name,
            expected_match_team_name,
        )

        # To reconnect this match, check if the client is the same as the one who started the match
        if match_team_name is None:
            match_team_name = await basic_auth.check_match_data(user_data, match_id)
            if match_team_name is None:
                raise conflict("This match has already started.")
        else:
            await basic_auth.create_match_data(
                user_data,
                match_id,
                match_team_name,
            )

        # match_data.game_mode is stored as a plain string in DB.
        # We compare it with the Enum's `.value` (e.g. "mix_doubles").
        is_mix_doubles = match_data is not None and match_data.game_mode == GameModeModel.mix_doubles.value

        # Mixed doubles uses only 2 players per team.
        # If the client sends player3/player4 anyway, fail fast instead of silently ignoring them.
        if is_mix_doubles and (team_config_data.player3 is not None or team_config_data.player4 is not None):
            raise bad_request("Mixed doubles uses only player1/player2; player3/player4 must be omitted.")

        if team_config_data.use_default_config:
            logging.info("Using default config")

            # Signal team-config completion via Redis to avoid DB polling in SSE subscribers.
            # Default config counts as "configured" for initial sync.
            if match_team_name in ("team0", "team1"):
                channel = f"match:{match_id}"
                config_key = f"match:{match_id}:team_config:{match_team_name}"
                await redis.set(config_key, "1", ex=60 * 60 * 24)
                await redis.publish(
                    channel,
                    json.dumps(
                        {
                            "type": "team_config_updated",
                            "match_id": str(match_id),
                            "team": match_team_name,
                        }
                    ),
                )
            return match_team_name

        # Standard requires 4 players; mixed doubles uses only 2.
        # TeamModel allows player3/player4 to be omitted for mixed doubles.
        if not is_mix_doubles and (team_config_data.player3 is None or team_config_data.player4 is None):
            raise bad_request("player3 and player4 are required for standard mode.")

        # Build the list of players to register.
        # Avoid getattr("player{i}") to keep types explicit and prevent silent None handling.
        player_models = (
            [team_config_data.player1, team_config_data.player2]
            if is_mix_doubles
            else [
                team_config_data.player1,
                team_config_data.player2,
                team_config_data.player3,
                team_config_data.player4,
            ]
        )

        team_id: UUID | None = await match_db.read_team_id(team_config_data.team_name)
        if team_id is None:
            team_id = uuid4()

        player_id_list: List[UUID] = []
        for player_model in player_models:
            if player_model is None:
                raise bad_request("Missing player configuration.")

            player_name: str = player_model.player_name
            player_id: UUID | None = await match_db.read_player_id(player_name, team_id)
            if player_id is None:
                player_id = uuid4()
                player_data: PlayerSchema = PlayerSchema(
                    player_id=player_id,
                    team_id=team_id,
                    max_velocity=player_model.max_velocity,
                    shot_std_dev=player_model.shot_std_dev,
                    angle_std_dev=player_model.angle_std_dev,
                    player_name=player_name,
                )
                await match_db.create_player_data(player_data)
            player_id_list.append(player_id)

        # Mixed doubles uses only 2 players, so player_id_list has length 2.
        # CRUD writes player3/player4 slots as NULL in match_data.
        if match_team_name == "team0":
            await match_db.update_first_team(match_id, team_id, player_id_list, team_config_data.team_name)
            # Standard: decide the initial next_shot_team at team0 config.
            # Mixed doubles: wait for an explicit end-setup command.
            if match_data is None or match_data.game_mode == GameModeModel.standard.value:
                await match_db.update_next_shot_team(match_id, team_id)
        elif match_team_name == "team1":
            await match_db.update_second_team(match_id, team_id, player_id_list, team_config_data.team_name)

            # Mixed doubles rule: end 0 positioned-stones selector is the hammer team (team1 / second_team).
            # If team1 registers as a different team_id, reflect it into end_setup_team_ids[0]
            # as long as the match hasn't started the first end yet.
            if is_mix_doubles:
                latest_state = await match_db.read_latest_state_data(match_id)
                if (
                    latest_state is not None
                    and latest_state.end_number == 0
                    and latest_state.next_shot_team_id is None
                    and latest_state.total_shot_number is None
                ):
                    await match_db.set_end_setup_team_for_end(
                        match_id=match_id,
                        end_number=0,
                        selector_team_id=team_id,
                    )

        # Signal team-config completion via Redis to avoid DB polling in SSE subscribers.
        # We publish only after team info has been written successfully.
        if match_team_name in ("team0", "team1"):
            channel = f"match:{match_id}"
            config_key = f"match:{match_id}:team_config:{match_team_name}"
            await redis.set(config_key, "1", ex=60 * 60 * 24)
            await redis.publish(
                channel,
                json.dumps(
                    {
                        "type": "team_config_updated",
                        "match_id": str(match_id),
                        "team": match_team_name,
                    }
                ),
            )

        return match_team_name

    @staticmethod
    @match_router.get("/matches/{match_id}/stream")
    async def stream_state_info(
        match_id: UUID, user_data: UserModel = Depends(basic_auth.check_user_data)
    ):
        """Stream the state information to the client
        Args:
            match_id (UUID): match_id
            user_data (UserModel): The user data for authentication
        """
        match_team_name: str = await basic_auth.check_match_data(user_data, match_id)
        channel: str = f"match:{match_id}"
        redis_subscriber = RedisSubscriber(Session, match_id, match_team_name)

        return StreamingResponse(
            redis_subscriber.event_generator(channel, redis),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @staticmethod
    @match_router.get("/matches/{match_id}/viewer")
    async def stream_state_info_viewer(
        match_id: UUID
    ):
        """Stream the state information to the viewer client
        Args:
            match_id (UUID): match_id
        """
        # Viewer has no authentication, so validate the match exists up-front.
        # Otherwise the SSE generator may raise and immediately disconnect.
        match_data = await match_db.read_match_data(match_id)
        if match_data is None:
            raise not_found("Match not found.")

        channel: str = f"match:{match_id}"
        redis_subscriber = RedisSubscriber(Session, match_id, "viewer")

        return StreamingResponse(
            redis_subscriber.event_generator(channel, redis),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @staticmethod
    @match_router.post("/shots")
    async def receive_shot_info(
        match_id: UUID,
        shot_info: ShotInfoModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ) -> None:
        """Receive the shot information from the client

        Args:
            match_id (UUID): match_id
            shot_info (ShotInfoModel): shot information from the client
            user_data (UserModel): The user data for authentication
        """
        end_time: datetime = datetime.now()
        match_data: MatchDataSchema = None
        pre_state_data: StateSchema = None
        player_data: PlayerSchema = None

        # Get match data to know simulator and team_id
        match_data = await match_db.read_match_data(match_id)
        # Get latest state data to know total shot number, stone coordinate and remaining time and so on.
        pre_state_data = await match_db.read_latest_state_data(match_id)

        if match_data is None or pre_state_data is None:
            raise not_found("Match or state not found.")

        # If the match is already finished, do not accept further shots.
        if pre_state_data.winner_team_id is not None:
            raise conflict("Match already finished.")

        # Mixed doubles: require end-setup before the first shot of the end.
        # We encode "end-setup completed" by setting next_shot_team_id in the setup state.
        if pre_state_data.next_shot_team_id is None:
            raise conflict("End setup required.")
        if pre_state_data.total_shot_number is None:
            raise conflict("End setup required.")
        # Get match team name to know which team is sending the shot information
        match_team_name: str = await basic_auth.check_match_data(
            user_data, match_id
        )
        shot_team_name: str = (
            "team0"
            if pre_state_data.next_shot_team_id == match_data.first_team_id
            else "team1"
        )
        # Check if shot info which client sent is valid or not
        if shot_team_name != match_team_name:
            raise conflict("Not your turn.")

        winner_team_id: UUID = None
        next_shot_team_id: UUID = None
        player_id: UUID = None
        # shot team which send this "shot_info"
        shot_team_id: UUID = pre_state_data.next_shot_team_id
        # total shot number at this time
        end_number: int = pre_state_data.end_number
        total_shot_number: int = int(pre_state_data.total_shot_number)
        shot_per_team: int = total_shot_number // 2
        # Player assignment differs by game mode.
        player_number: int = int(total_shot_number / 4) + 1
        team_number: int = 0 if match_team_name == "team0" else 1
        next_end_first_shot_team_id: UUID = None
        next_end_selector_team_id: UUID | None = None

        # Check player ID
        if match_data.game_mode == GameModeModel.mix_doubles.value:
            # Mixed doubles uses 2 players per team.
            # Per team per end (5 stones): Player1 throws 1st + 5th, Player2 throws 2nd-4th.
            shot_index_for_team = shot_per_team
            player_slot = 1 if shot_index_for_team in (0, 4) else 2
            if match_team_name == "team0":
                player_id = getattr(match_data, f"first_team_player{player_slot}_id")
            else:
                player_id = getattr(match_data, f"second_team_player{player_slot}_id")
        else:
            # Standard: 4 players per team, each throwing in order.
            if match_team_name == "team0":
                player_id = getattr(match_data, f"first_team_player{player_number}_id")
            elif match_team_name == "team1":
                player_id = getattr(match_data, f"second_team_player{player_number}_id")

        player_data = await match_db.read_player_data(player_id)
        if player_data is None:
            raise not_found("Player not found.")
        dist_translational_velocity = np.max(
            [
                np.min([shot_info.translational_velocity, player_data.max_velocity])
                + np.random.normal(loc=0.0, scale=player_data.shot_std_dev),
                0.0,
            ]
        )

        dist_shot_info: ShotInfoModel = shot_info.model_copy(deep=True)
        dist_shot_info.translational_velocity = dist_translational_velocity
        dist_shot_info.shot_angle = shot_info.shot_angle + np.random.normal(loc=0.0, scale=player_data.angle_std_dev)

        # Calculate the time difference between the last state and this shot
        # and update the remaining time
        pre_end_time: datetime = pre_state_data.created_at
        time_diff: timedelta = end_time - pre_end_time
        time_diff_seconds: float = time_diff.total_seconds()

        team0_remaining_time: float = pre_state_data.first_team_remaining_time
        team1_remaining_time: float = pre_state_data.second_team_remaining_time
        team0_extra_end_remaining_time: float = (
            pre_state_data.first_team_extra_end_remaining_time
        )
        team1_extra_end_remaining_time: float = (
            pre_state_data.second_team_extra_end_remaining_time
        )

        if pre_state_data.end_number < match_data.standard_end_count:
            if match_team_name == "team0":
                team0_remaining_time -= time_diff_seconds
                if team0_remaining_time < 0:
                    winner_team_id = match_data.second_team_id
                    team0_remaining_time = 0
            elif match_team_name == "team1":
                team1_remaining_time -= time_diff_seconds
                if team1_remaining_time < 0:
                    winner_team_id = match_data.first_team_id
                    team1_remaining_time = 0
        else:
            if match_team_name == "team0":
                team0_extra_end_remaining_time -= time_diff_seconds
                if team0_extra_end_remaining_time < 0:
                    winner_team_id = match_data.second_team_id
                    team0_extra_end_remaining_time = 0
            elif match_team_name == "team1":
                team1_extra_end_remaining_time -= time_diff_seconds
                if team1_extra_end_remaining_time < 0:
                    winner_team_id = match_data.first_team_id
                    team1_extra_end_remaining_time = 0

        # Simulate the stone
        simulated_stones_coordinate, trajectory = simulate_fcv1(
            shot_info=dist_shot_info,
            state_data=pre_state_data,
            total_shot_number=total_shot_number,
            shot_per_team=shot_per_team,
            team_number=team_number,
            applied_rule=match_data.applied_rule,
            stone_simulator=stone_simulator,
        )

        # Update the total shot number and shot per team
        total_shot_number += 1
        shot_per_team = total_shot_number // 2

        next_shot_team_id = (
            match_data.first_team_id
            if shot_team_id == match_data.second_team_id
            else match_data.second_team_id
        )

        shot_info_data: ShotInfoSchema = ShotInfoSchema(
            shot_id=uuid7(),
            player_id=player_id,
            team_id=shot_team_id,
            trajectory_id=uuid7(),
            pre_shot_state_id=pre_state_data.state_id,
            post_shot_state_id=uuid7(),
            actual_translational_velocity=shot_info.translational_velocity,     # actual value before distortion
            actual_shot_angle=shot_info.shot_angle,
            translational_velocity=dist_translational_velocity,                 # distorted value
            shot_angle=dist_shot_info.shot_angle,
            angular_velocity=shot_info.angular_velocity,
        )

        # Count of stones depends on game mode(standard: 8, mix_doubles: 6)
        stone_count = stone_count_per_team(match_data.game_mode)

        stone_coordinate = {
            "team0": [
                {
                    "x": simulated_stones_coordinate[0][i][0],
                    "y": simulated_stones_coordinate[0][i][1],
                }
                for i in range(stone_count)
            ],
            "team1": [
                {
                    "x": simulated_stones_coordinate[1][i][0],
                    "y": simulated_stones_coordinate[1][i][1],
                }
                for i in range(stone_count)
            ],
        }
        stone_coordinate_data: StoneCoordinateSchema = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(),
            data=stone_coordinate,
        )

        # total_shots_per_end depends on game mode(standard: 16, mix_doubles: 10)
        total_shots_per_end = get_total_shots_per_end(match_data.game_mode)

        # The shot is the last shot of the "end"
        if total_shot_number == total_shots_per_end:
            next_shot_team_id: UUID = None
            pre_score_data: ScoreSchema = pre_state_data.score
            team0_score: List = pre_score_data.team0
            team1_score: List = pre_score_data.team1

            team0_stones_position = [
                (stone[0], stone[1]) for stone in simulated_stones_coordinate[0][:stone_count]
            ]
            team1_stones_position = [
                (stone[0], stone[1]) for stone in simulated_stones_coordinate[1][:stone_count]
            ]
            distance_list: List = []
            for i in range(stone_count):
                distance_list.append(
                    (
                        0,
                        stone_distance_from_tee(
                            float(team0_stones_position[i][0]),
                            float(team0_stones_position[i][1]),
                        ),
                    )
                )
                distance_list.append(
                    (
                        1,
                        stone_distance_from_tee(
                            float(team1_stones_position[i][0]),
                            float(team1_stones_position[i][1]),
                        ),
                    )
                )
            scored_team, score = get_score_from_distance_list(distance_list)
            if scored_team is None:
                next_end_first_shot_team_id = (
                    match_data.first_team_id
                    if match_team_name == "team1"
                    else match_data.second_team_id
                )

            # Mixed doubles: decide next end's positioned-stones selector.
            # We persist it only if the match continues (winner not decided), right before we create the next end state.
            if match_data.game_mode == GameModeModel.mix_doubles.value:
                current_selector = None
                if (
                    match_data.mix_doubles_settings is not None
                    and getattr(match_data.mix_doubles_settings, "end_setup_team_ids", None) is not None
                ):
                    ids = match_data.mix_doubles_settings.end_setup_team_ids
                    if isinstance(ids, list) and 0 <= int(end_number) < len(ids):
                        current_selector = ids[int(end_number)]

                if current_selector is None:
                    current_selector = match_data.second_team_id

                if scored_team == 0:
                    next_end_selector_team_id = match_data.second_team_id
                elif scored_team == 1:
                    next_end_selector_team_id = match_data.first_team_id
                else:
                    # Blank end: toggle selector.
                    next_end_selector_team_id = (
                        match_data.second_team_id
                        if current_selector == match_data.first_team_id
                        else match_data.first_team_id
                    )

            if end_number < match_data.standard_end_count:
                if scored_team == 0:
                    team0_score[end_number] = score
                    team1_score[end_number] = 0
                    next_end_first_shot_team_id = match_data.second_team_id
                elif scored_team == 1:
                    team0_score[end_number] = 0
                    team1_score[end_number] = score
                    next_end_first_shot_team_id = match_data.first_team_id
            elif end_number >= match_data.standard_end_count:
                if scored_team == 0:
                    team0_score[match_data.standard_end_count] = score
                    team1_score[match_data.standard_end_count] = 0
                    next_end_first_shot_team_id = None
                    winner_team_id = match_data.first_team_id
                elif scored_team == 1:
                    team0_score[match_data.standard_end_count] = 0
                    team1_score[match_data.standard_end_count] = score
                    winner_team_id = match_data.second_team_id
                    next_end_first_shot_team_id = None

            score_data: ScoreSchema = ScoreSchema(
                score_id=pre_score_data.score_id,
                team0=team0_score,
                team1=team1_score,
            )
            await match_db.update_score(score_data)

            if end_number >= match_data.standard_end_count - 1:
                team0_total_score: int = calculate_total_score(team0_score)
                team1_total_score: int = calculate_total_score(team1_score)
                if team0_total_score > team1_total_score:
                    next_end_first_shot_team_id = None
                    winner_team_id = match_data.first_team_id
                elif team0_total_score < team1_total_score:
                    next_end_first_shot_team_id = None
                    winner_team_id = match_data.second_team_id
                else:
                    winner_team_id = None

        state_data: StateSchema = StateSchema(
            state_id=shot_info_data.post_shot_state_id,
            winner_team_id=winner_team_id,
            match_id=match_id,
            end_number=pre_state_data.end_number,
            shot_number=shot_per_team,
            total_shot_number=total_shot_number,
            first_team_remaining_time=team0_remaining_time,
            second_team_remaining_time=team1_remaining_time,
            first_team_extra_end_remaining_time=team0_extra_end_remaining_time,
            second_team_extra_end_remaining_time=team1_extra_end_remaining_time,
            stone_coordinate_id=stone_coordinate_data.stone_coordinate_id,
            score_id=pre_state_data.score_id,
            shot_id=None,
            next_shot_team_id=next_shot_team_id,
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate_data,
        )
        await match_db.record_shot_result(
            shot_info=shot_info_data,
            post_state=state_data,
            pre_state_id=pre_state_data.state_id,
        )

        channel = f"match:{match_id}"
        await redis.publish(
            channel,
            json.dumps(
                {
                    "type": "state_update",
                    "match_id": str(match_id),
                    "state_id": str(state_data.state_id),
                }
            ),
        )

        if total_shot_number == total_shots_per_end and winner_team_id is None:
            if (
                match_data.game_mode == GameModeModel.mix_doubles.value
                and next_end_selector_team_id is not None
            ):
                await match_db.set_end_setup_team_for_end(
                    match_id=match_id,
                    end_number=end_number + 1,
                    selector_team_id=next_end_selector_team_id,
                )
            await state_end_number_update(state_data, next_end_first_shot_team_id)


    # ==============================================================================
    # ==== Only Mixed doubles EndPoint =============================================
    # ==============================================================================
    @staticmethod
    @match_router.post("/matches/{match_id}/end-setup")
    async def end_setup(
        match_id: UUID,
        request: PositionedStonesModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ) -> None:
        """Mixed doubles: decide throw order (and optional power play), then place pre-positioned stones."""
        match_team_name: str = await basic_auth.check_match_data(user_data, match_id)

        match_data: MatchDataSchema | None = await match_db.read_match_data(match_id)
        latest_state: StateSchema | None = await match_db.read_latest_state_data(match_id)

        if match_data is None or latest_state is None:
            raise not_found("Match not found.")

        if match_data.game_mode != GameModeModel.mix_doubles.value:
            raise bad_request("end-setup is only for mix_doubles.")

        if match_data.mix_doubles_settings is None:
            raise conflict("Mixed doubles settings missing.")

        if latest_state.winner_team_id is not None:
            raise conflict("Match already finished.")

        # Pre-end setup state is encoded as next_shot_team_id=None and total_shot_number=None.
        # After setup we create a new state with total_shot_number=0 and next_shot_team_id set.
        if latest_state.next_shot_team_id is not None or latest_state.total_shot_number is not None:
            raise conflict("End already started.")

        try:
            setup_state_id = await match_db.perform_mix_doubles_end_setup(
                match_data=match_data,
                latest_state=latest_state,
                match_team_name=match_team_name,
                request=request,
            )
        except ValueError as e:
            message = str(e)
            if "only be used" in message:
                raise bad_request(message)
            raise conflict(message)

        await redis.publish(
            f"match:{match_id}",
            json.dumps(
                {
                    "type": "state_update",
                    "match_id": str(match_id),
                    "state_id": str(setup_state_id),
                }
            ),
        )
