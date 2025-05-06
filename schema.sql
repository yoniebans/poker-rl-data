CREATE TABLE hand_histories (
    hand_id TEXT PRIMARY KEY,
    raw_text TEXT,
    pokergpt_format JSONB,
    
    -- Metadata for filtering
    game_type TEXT,
    blinds NUMERIC[2],
    big_blind NUMERIC,
    player_count INTEGER,
    
    -- Win statistics
    winner TEXT,
    bb_won NUMERIC,
    
    -- Game states
    has_preflop BOOLEAN,
    has_flop BOOLEAN,
    has_turn BOOLEAN, 
    has_river BOOLEAN,
    has_showdown BOOLEAN,
    
    -- Player filtering
    player_ids TEXT[],
    player_win_rates JSONB,  -- Map of player_id -> win_rate (mbb/h)
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for filtering by win rates
CREATE INDEX idx_player_win_rates ON hand_histories USING GIN (player_win_rates);