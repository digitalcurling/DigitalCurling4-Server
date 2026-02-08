import numpy as np

from src.domain.match_rules import (
    SCORE_DISTANCE,
    TEE_LINE,
    calculate_total_score,
    get_score_from_distance_list,
    stone_distance_from_tee,
)


def test_stone_distance_from_tee_center_is_zero():
    assert stone_distance_from_tee(0.0, TEE_LINE) == 0.0


def test_get_score_blank_end_when_no_stone_in_house():
    distance_list = [
        (0, stone_distance_from_tee(0.0, 0.0)),
        (1, stone_distance_from_tee(0.0, 0.0)),
    ]
    scored_team, score = get_score_from_distance_list(distance_list)
    assert scored_team is None
    assert score == 0


def test_get_score_counts_consecutive_scoring_stones_only():
    # team0 has two stones closer than team1's closest.
    distance_list = [
        (0, 0.10),
        (0, 0.20),
        (1, 0.30),
    ]
    assert all(d <= SCORE_DISTANCE for _, d in distance_list)

    scored_team, score = get_score_from_distance_list(distance_list)
    assert scored_team == 0
    assert score == 2


def test_get_score_stops_when_opponent_stone_is_closer():
    distance_list = [
        (0, 0.10),
        (1, 0.20),
        (0, 0.30),
    ]
    assert all(d <= SCORE_DISTANCE for _, d in distance_list)

    scored_team, score = get_score_from_distance_list(distance_list)
    assert scored_team == 0
    assert score == 1


def test_calculate_total_score_sums_list():
    assert calculate_total_score([0, 2, 0, 1]) == 3


def test_score_distance_constant_reasonable():
    # Sanity: SCORE_DISTANCE should be > house radius and < 3m.
    assert SCORE_DISTANCE > 1.8
    assert SCORE_DISTANCE < 3.0
    # And it should be finite.
    assert bool(np.isfinite(SCORE_DISTANCE))
