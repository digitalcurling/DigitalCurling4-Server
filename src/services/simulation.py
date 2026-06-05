import numpy as np

from src.models.dc_models import ShotInfoModel
from src.models.schema_models import StateSchema
from src.simulator import StoneSimulator


def simulate_fcv1(
    *,
    shot_info: ShotInfoModel,
    state_data: StateSchema,
    total_shot_number: int,
    shot_per_team: int,
    team_number: int,
    applied_rule: int,
    stone_simulator: StoneSimulator,
) -> tuple[np.ndarray, np.ndarray]:
    """Run one shot simulation (fcv1).

    This is intentionally kept outside the HTTP router module.
    """

    velocity_x: np.float64 = shot_info.translational_velocity * np.cos(shot_info.shot_angle)
    velocity_y: np.float64 = shot_info.translational_velocity * np.sin(shot_info.shot_angle)

    stone_position = np.array(
        [
            coordinate
            for _, stones in state_data.stone_coordinate.data.items()
            for stone in stones
            for coordinate in (stone["x"], stone["y"])
        ]
    )

    simulated_stones_coordinate, trajectory = stone_simulator.simulator(
        stone_position,
        total_shot_number,
        velocity_x,
        velocity_y,
        shot_info.angular_velocity,
        team_number,
        shot_per_team,
        applied_rule,
    )
    return simulated_stones_coordinate, trajectory
