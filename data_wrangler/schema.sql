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
    winning_action TEXT,    -- Stores the winner's final action (extracted from stages)
    formatted_winning_action TEXT,  -- Stores the formatted version of the winning action
    winner_cards TEXT[],    -- Stores the winner's cards as an array of card codes
    
    -- Game states
    has_preflop BOOLEAN,
    has_flop BOOLEAN,
    has_turn BOOLEAN, 
    has_river BOOLEAN,
    has_showdown BOOLEAN,
    
    -- Player filtering
    player_ids TEXT[],
    
    -- Table information
    table_name TEXT,
    
    -- Positions
    dealer_position INTEGER,
    dealer_player TEXT,
    small_blind_player TEXT,
    big_blind_player TEXT,
    
    -- Summary information
    pot_total NUMERIC,
    rake NUMERIC,
    board TEXT[],
    
    -- Timestamp information
    played_at TIMESTAMP,
    
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
    hands_per_hour NUMERIC,
    
    -- Table-based metrics
    active_hours NUMERIC,
    tables INTEGER,
    table_sessions INTEGER,
    table_data JSONB,
    
    -- Timestamp information
    first_hand_at TIMESTAMP,
    last_hand_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Dataset records table for HuggingFace export review
CREATE TABLE dataset_records (
    id SERIAL PRIMARY KEY,
    hand_id TEXT REFERENCES hand_histories(hand_id),
    
    -- Basic hand info
    winner TEXT,
    bb_won NUMERIC,
    game_type TEXT,
    big_blind NUMERIC,
    game_stage TEXT,  -- PREFLOP, FLOP, TURN, RIVER
    
    -- Card evaluations
    evaluator_rank TEXT,  -- Result from our poker_hand_evaluator
    description TEXT,  -- Description from summary/showdown
    
    -- PokerGPT dataset fields
    pokergpt_format JSONB, -- Complete structured JSON representation of the hand
    pokergpt_prompt TEXT,  -- The formatted prompt
    winning_action TEXT,   -- The winning action
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient filtering
CREATE INDEX idx_hand_histories_winner ON hand_histories(winner);
CREATE INDEX idx_hand_histories_played_at ON hand_histories(played_at);
CREATE INDEX idx_hand_histories_table_name ON hand_histories(table_name);
CREATE INDEX idx_hand_histories_winning_action ON hand_histories(winning_action);
CREATE INDEX idx_players_mbb_per_hour ON players(mbb_per_hour);
CREATE INDEX idx_dataset_records_hand_id ON dataset_records(hand_id);