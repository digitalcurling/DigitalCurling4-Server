from uuid6 import uuid7
from uuid import UUID

from src.models.dc_models import (
    ScoreModel,
    StateModel,
    CoordinateDataModel,
    StoneCoordinateModel,
    ShotInfoModel,
    PowerPlayEndModel,
    MixedDoublesSettingsModel,
    GameModeModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    StateSchema,
    StoneCoordinateSchema,
)


class DataConverter:
    """This class is used to convert data between different formats."""

    def convert_stateschema_to_statemodel(
        self,
        match_data: MatchDataSchema,
        state_data: StateSchema,
        shot_info_data=None,
    ) -> StateModel:
        """Convert the StateSchema to the StateModel to send client

        Args:
            match_data (MatchDataSchema): The match data of the match
            state_data (StateSchema): The latest state data of the match

        Returns:
            StateModel: The state data of the match and is a type for transmission to the client
        """
        if match_data is None:
            raise ValueError("match_data is required")

        winner_team_name: str = None
        next_shot_team: str = None
        if state_data.winner_team_id is not None:
            winner_team_id = state_data.winner_team_id
            winner_team_name = (
                "team0" if winner_team_id == match_data.first_team_id else "team1"
            )

        if state_data.next_shot_team_id is not None:
            next_shot_team_id = state_data.next_shot_team_id
            next_shot_team = (
                "team0" if next_shot_team_id == match_data.first_team_id else "team1"
            )

        last_move = None
        if shot_info_data is not None:
            last_move = ShotInfoModel(
                translational_velocity=shot_info_data.translational_velocity,
                angular_velocity=shot_info_data.angular_velocity,
                shot_angle=shot_info_data.shot_angle,
            )

        # Determine if it is pre-end setup for mixed doubles
        is_pre_end_setup = match_data.game_mode == GameModeModel.mixed_doubles.value and state_data.next_shot_team_id is None

        team_shot_number = state_data.team_shot_number
        total_shot_number = state_data.total_shot_number
        # If it is pre-end setup, set team_shot_number and total_shot_number to None
        if is_pre_end_setup:
            team_shot_number = None
            total_shot_number = None

        # To parse stone coordinates data
        stone_coordinate_data: dict = {}
        for team, coords in state_data.stone_coordinate.data.items():
            if coords is None:
                normalized = []
            elif isinstance(coords, list) and coords and isinstance(coords[0], list):
                normalized = []
                for item in coords:
                    if isinstance(item, list):
                        normalized.extend(item)
                    else:
                        normalized.append(item)
            else:
                normalized = coords

            stone_coordinate_data[team] = [CoordinateDataModel(**coord) for coord in normalized]

        end_setup_team_id = match_data.second_team_id
        if (
            match_data.mixed_doubles_settings is not None
            and getattr(match_data.mixed_doubles_settings, "end_setup_team_ids", None) is not None
            and state_data is not None
        ):
            ids = match_data.mixed_doubles_settings.end_setup_team_ids
            if isinstance(ids, list) and 0 <= int(state_data.end_number) < len(ids):
                # JSONB stores UUIDs as strings; be defensive and normalize to UUID.
                end_setup_team_id = UUID(str(ids[int(state_data.end_number)]))

        state_model: StateModel = StateModel(
            winner_team=winner_team_name,
            first_team_name=match_data.first_team_name,
            second_team_name=match_data.second_team_name,
            end_number=state_data.end_number,
            team_shot_number=team_shot_number,
            total_shot_number=total_shot_number,
            next_shot_team=next_shot_team,
            first_team_remaining_time=state_data.first_team_remaining_time,
            second_team_remaining_time=state_data.second_team_remaining_time,
            first_team_extra_end_remaining_time=state_data.first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time=state_data.second_team_extra_end_remaining_time,
            mixed_doubles_settings=(
                MixedDoublesSettingsModel(
                    end_setup_team=(
                        "team0"
                        if (
                            (
                                end_setup_team_id
                            )
                            == match_data.first_team_id
                        )
                        else "team1"
                    ),
                    positioned_stones_pattern=int(
                        match_data.mixed_doubles_settings.positioned_stones_pattern
                    ),
                    power_play_end=PowerPlayEndModel(
                        team0=match_data.mixed_doubles_settings.team0_power_play_end,
                        team1=match_data.mixed_doubles_settings.team1_power_play_end,
                    ),
                )
                if match_data.mixed_doubles_settings is not None
                else None
            ),
            last_move=last_move,
            stone_coordinate=StoneCoordinateModel(data=stone_coordinate_data),
            score=ScoreModel(
                team0=state_data.score.team0,
                team1=state_data.score.team1,
            ),
        )
        return state_model

    def convert_stonecoordinate_to_stonecoordinateschema(
        self, stone_coordinate_data: StoneCoordinateModel
    ) -> StoneCoordinateSchema:
        """Convert the StoneCoordinateModel to the StoneCoordinateSchema to send client

        Args:
            stone_coordinate_data (StoneCoordinateModel): The stone coordinate data of the match

        Returns:
            StoneCoordinateSchema: The stone coordinate data of the match and is a type for transmission to the client
        """
        stone_coordinate_schema: StoneCoordinateSchema = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(), data=stone_coordinate_data.data
        )
        return stone_coordinate_schema
