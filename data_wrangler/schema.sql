-- Hand histories table
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
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Player statistics table
CREATE TABLE players (
    player_id TEXT PRIMARY KEY,
    total_hands INTEGER,
    total_bb NUMERIC,
    mbb_per_hand NUMERIC,
    mbb_per_hour NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient filtering
CREATE INDEX idx_hand_histories_winner ON hand_histories(winner);
CREATE INDEX idx_players_mbb_per_hour ON players(mbb_per_hour);