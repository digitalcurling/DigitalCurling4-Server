import pytest

from src.domain.match_rules import (
    generate_mixed_doubles_initial_stones,
    generate_reset_stone_coordinate_data,
    stone_count_per_team,
    total_shots_per_end,
)


def test_stone_count_per_team():
    assert stone_count_per_team("standard") == 8
    assert stone_count_per_team("mix_doubles") == 6


def test_total_shots_per_end():
    assert total_shots_per_end("standard") == 16
    assert total_shots_per_end("mix_doubles") == 10


def test_generate_reset_stone_coordinate_data_standard():
    data = generate_reset_stone_coordinate_data("standard")
    assert set(data.keys()) == {"team0", "team1"}
    assert len(data["team0"]) == 8
    assert len(data["team1"]) == 8
    assert all(coord == {"x": 0.0, "y": 0.0} for coord in data["team0"])
    assert all(coord == {"x": 0.0, "y": 0.0} for coord in data["team1"])


def test_generate_reset_stone_coordinate_data_mix_doubles():
    data = generate_reset_stone_coordinate_data("mix_doubles")
    assert set(data.keys()) == {"team0", "team1"}
    assert len(data["team0"]) == 6
    assert len(data["team1"]) == 6


def test_generate_mixed_doubles_initial_stones_invalid_pattern_raises():
    with pytest.raises(ValueError):
        generate_mixed_doubles_initial_stones(
            hammer_team_name="team0",
            power_play_side=None,
            positioned_stones_pattern=-1,
        )

    with pytest.raises(ValueError):
        generate_mixed_doubles_initial_stones(
            hammer_team_name="team0",
            power_play_side=None,
            positioned_stones_pattern=6,
        )


def test_generate_mixed_doubles_initial_stones_hammer_gets_house_when_requested():
    data = generate_mixed_doubles_initial_stones(
        hammer_team_name="team0",
        power_play_side=None,
        positioned_stones_pattern=0,
        hammer_stone_position="house",
    )

    # Function returns 8 slots per team for simulator compatibility.
    assert len(data["team0"]) == 8
    assert len(data["team1"]) == 8

    # When hammer_stone_position="house", hammer gets the house stone at index 0.
    assert data["team0"][0]["x"] == pytest.approx(0.0)
    assert data["team0"][0]["y"] == pytest.approx(38.870)


def test_generate_mixed_doubles_initial_stones_power_play_left_flips_x():
    left = generate_mixed_doubles_initial_stones(
        hammer_team_name="team0",
        power_play_side="left",
        positioned_stones_pattern=0,
        hammer_stone_position="house",
    )
    right = generate_mixed_doubles_initial_stones(
        hammer_team_name="team0",
        power_play_side="right",
        positioned_stones_pattern=0,
        hammer_stone_position="house",
    )

    # House stone x should be negative on left and positive on right.
    assert left["team0"][0]["x"] < 0
    assert right["team0"][0]["x"] > 0
    assert left["team0"][0]["y"] == pytest.approx(right["team0"][0]["y"])


def test_generate_mixed_doubles_initial_stones_invalid_hammer_stone_position_raises():
    with pytest.raises(ValueError):
        generate_mixed_doubles_initial_stones(
            hammer_team_name="team0",
            power_play_side=None,
            positioned_stones_pattern=0,
            hammer_stone_position="invalid",
        )
