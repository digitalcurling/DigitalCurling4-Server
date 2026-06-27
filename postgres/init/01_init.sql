-- ======================================
-- 1) Enable Extension
-- ======================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ======================================
-- 2) Create all table bodies
-- ======================================
-- Score
CREATE TABLE IF NOT EXISTS score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team0 INTEGER[],
  team1 INTEGER[]
);

-- PhysicalSimulator
CREATE TABLE IF NOT EXISTS physical_simulator (
    physical_simulator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulator_name VARCHAR
);

-- Tournament
CREATE TABLE IF NOT EXISTS tournament (
    tournament_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_name VARCHAR
);

-- StoneCoordinate
CREATE TABLE IF NOT EXISTS stone_coordinate (
    stone_coordinate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  data JSONB
);

-- Trajectory
CREATE TABLE IF NOT EXISTS trajectory (
    trajectory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trajectory_data JSONB,
  data_format_version VARCHAR(32)
);

-- Player
CREATE TABLE IF NOT EXISTS player (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    max_velocity DOUBLE PRECISION,
    shot_std_dev DOUBLE PRECISION,
    angle_std_dev DOUBLE PRECISION,
    player_name VARCHAR
);

-- Match
CREATE TABLE IF NOT EXISTS match_data (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_team_name VARCHAR,
    second_team_name VARCHAR,
    first_team_id UUID DEFAULT gen_random_uuid(),
    first_team_player1_id UUID DEFAULT gen_random_uuid(),
    first_team_player2_id UUID DEFAULT gen_random_uuid(),
    first_team_player3_id UUID NULL,
    first_team_player4_id UUID NULL,
    second_team_id UUID DEFAULT gen_random_uuid(),
    second_team_player1_id UUID DEFAULT gen_random_uuid(),
    second_team_player2_id UUID DEFAULT gen_random_uuid(),
    second_team_player3_id UUID NULL,
    second_team_player4_id UUID NULL,
    winner_team_id UUID,
    score_id UUID DEFAULT gen_random_uuid(),
    time_limit DOUBLE PRECISION,
    applied_rule INTEGER, -- 0: five rock rule, 1: no tick rule
    extra_end_time_limit DOUBLE PRECISION,
    standard_end_count INTEGER,
    physical_simulator_id UUID DEFAULT gen_random_uuid(),
    tournament_id UUID DEFAULT gen_random_uuid(),
    match_name VARCHAR,
    game_mode VARCHAR(32) NOT NULL DEFAULT 'standard',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE match_data
  ADD CONSTRAINT chk_match_game_mode
    CHECK (game_mode IN ('standard', 'mixed_doubles'));

-- Mixed Doubles Settings (only exists for game_mode='mixed_doubles')
CREATE TABLE IF NOT EXISTS match_mixed_doubles_settings (
    match_id UUID PRIMARY KEY,
  positioned_stones_pattern INTEGER NOT NULL,
    team0_power_play_end INTEGER NULL,
    team1_power_play_end INTEGER NULL,
    -- Per-end selector(hammer) team_id list. Index corresponds to end_number.
    end_setup_team_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

ALTER TABLE match_mixed_doubles_settings
  ADD CONSTRAINT chk_md_settings_pattern
    CHECK (positioned_stones_pattern BETWEEN 0 AND 5);

ALTER TABLE match_mixed_doubles_settings
  ADD CONSTRAINT chk_md_settings_pp_end
    CHECK (
      (team0_power_play_end IS NULL OR team0_power_play_end >= 0)
      AND (team1_power_play_end IS NULL OR team1_power_play_end >= 0)
    );

-- ShotInfo
CREATE TABLE IF NOT EXISTS shot_info (
    shot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    trajectory_id UUID DEFAULT gen_random_uuid(),
    pre_shot_state_id UUID DEFAULT gen_random_uuid(),
    post_shot_state_id UUID DEFAULT gen_random_uuid(),
    actual_translational_velocity DOUBLE PRECISION,
    actual_shot_angle DOUBLE PRECISION,
    actual_angular_velocity DOUBLE PRECISION,
    translational_velocity DOUBLE PRECISION,
    angular_velocity DOUBLE PRECISION,
    shot_angle DOUBLE PRECISION
);

-- State
CREATE TABLE IF NOT EXISTS state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    winner_team_id UUID,
    match_id UUID DEFAULT gen_random_uuid(),
    end_number INTEGER,
    team_shot_number INTEGER,
    total_shot_number INTEGER,
    first_team_remaining_time DOUBLE PRECISION,
    second_team_remaining_time DOUBLE PRECISION,
    first_team_extra_end_remaining_time DOUBLE PRECISION,
    second_team_extra_end_remaining_time DOUBLE PRECISION,
    stone_coordinate_id UUID DEFAULT gen_random_uuid(),
    score_id UUID DEFAULT gen_random_uuid(),
    shot_id UUID,
    next_shot_team_id UUID null,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ======================================
-- 3)　Add all foreign key constraints
-- ======================================
-- match_data → score / physical_simulator / tournament / player(x8)
ALTER TABLE match_data
  ADD CONSTRAINT fk_match_score
    FOREIGN KEY(score_id) REFERENCES score(score_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_simulator
    FOREIGN KEY(physical_simulator_id) REFERENCES physical_simulator(physical_simulator_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_tournament
    FOREIGN KEY(tournament_id) REFERENCES tournament(tournament_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p1  FOREIGN KEY(first_team_player1_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p2  FOREIGN KEY(first_team_player2_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p3  FOREIGN KEY(first_team_player3_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p4  FOREIGN KEY(first_team_player4_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p5  FOREIGN KEY(second_team_player1_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p6  FOREIGN KEY(second_team_player2_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p7  FOREIGN KEY(second_team_player3_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p8  FOREIGN KEY(second_team_player4_id) REFERENCES player(player_id) ON DELETE CASCADE;

-- shot_info → player / trajectory / state(x2)
ALTER TABLE shot_info
  ADD CONSTRAINT fk_shot_player
    FOREIGN KEY(player_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_shot_trajectory
    FOREIGN KEY(trajectory_id) REFERENCES trajectory(trajectory_id);

-- state → match_data / score / shot_info / stone_coordinate
ALTER TABLE state
  ADD CONSTRAINT fk_state_match
    FOREIGN KEY(match_id) REFERENCES match_data(match_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_state_score
    FOREIGN KEY(score_id) REFERENCES score(score_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_state_stone_coord
    FOREIGN KEY(stone_coordinate_id) REFERENCES stone_coordinate(stone_coordinate_id) ON DELETE CASCADE;

-- match_mixed_doubles_settings → match_data
ALTER TABLE match_mixed_doubles_settings
  ADD CONSTRAINT fk_md_settings_match
    FOREIGN KEY(match_id) REFERENCES match_data(match_id) ON DELETE CASCADE;

-- ======================================
-- 4) Indexes for read APIs
-- ======================================
-- Search by match_name, and pick latest match quickly.
CREATE INDEX IF NOT EXISTS idx_match_data_match_name_started_at
  ON match_data (match_name, started_at DESC);

-- Efficient per-end retrieval and ordering.
CREATE INDEX IF NOT EXISTS idx_state_match_end_shot
  ON state (match_id, end_number, team_shot_number);