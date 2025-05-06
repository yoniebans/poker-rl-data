# PokerGPT Data Processing Pipeline

A comprehensive toolkit for processing poker hand histories and preparing high-quality training data for PokerGPT, focusing on accurate player win rate calculation using a table-based approach.

## Overview

This project provides a data processing pipeline for poker hand histories that:

1. Parses PokerStars hand history files with robust error handling
2. Stores structured data in a PostgreSQL database
3. Calculates accurate player win rates using a table-based approach
4. Exports filtered datasets for PokerGPT training based on player skill level

The pipeline is designed to support the methodology described in the PokerGPT paper, which requires identifying high-skill players for training data selection.

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL database
- Conda (optional but recommended)

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/poker-rl-data.git
   cd poker-rl-data
   ```

2. Create and activate a conda environment:

   ```bash
   conda create -n poker-data python=3.10
   conda activate poker-data
   ```

3. Install the package and dependencies:
   ```bash
   pip install -e .
   ```

## Database Schema

The project uses two main tables:

### hand_histories

Stores individual poker hands with the following key fields:

- `hand_id`: Unique identifier for each hand
- `raw_text`: Original hand history text
- `pokergpt_format`: Structured JSON representation
- `player_ids`: Array of player identifiers in the hand
- `table_name`: Name of the poker table
- `played_at`: Timestamp when the hand was played
- `winner`: Player who won the hand
- `bb_won`: Amount won in big blinds

### players

Stores player statistics with an emphasis on table-based metrics:

- `player_id`: Unique identifier for each player
- `total_hands`: Total number of hands played
- `total_bb`: Total big blinds won/lost
- `mbb_per_hand`: Win rate in milli-big blinds per hand
- `mbb_per_hour`: Win rate in milli-big blinds per hour
- `active_hours`: Total time actively playing at tables
- `tables`: Number of distinct tables played
- `table_sessions`: Number of distinct table sessions (including rejoins)
- `table_data`: JSONB array of recent table session details

### Data Model Diagram

```mermaid
erDiagram
    hand_histories {
        string hand_id PK
        text raw_text
        jsonb pokergpt_format
        string game_type
        numeric[2] blinds
        numeric big_blind
        integer player_count
        string winner
        numeric bb_won
        boolean has_preflop
        boolean has_flop
        boolean has_turn
        boolean has_river
        boolean has_showdown
        string[] player_ids
        string table_name
        timestamp played_at
        timestamp created_at
        timestamp updated_at
    }
    
    players {
        string player_id PK
        integer total_hands
        numeric total_bb
        numeric mbb_per_hand
        numeric mbb_per_hour
        numeric hands_per_hour
        numeric active_hours
        integer tables
        integer table_sessions
        jsonb table_data
        timestamp first_hand_at
        timestamp last_hand_at
        timestamp created_at
        timestamp updated_at
    }
    
    hand_histories ||--o{ players : "tracked_in"
    
    players ||--o{ hand_histories : "participates_in"
```

The diagram shows the relationship between the two main tables. Each player can participate in many hand histories, and each hand history tracks multiple players through the `player_ids` array. The relationship between tables is managed programmatically rather than through explicit foreign key constraints, providing flexibility for the table-based win rate calculation approach.

## Core Components

### 1. Hand Parser (`parse_poker_hands.py`)

Parses PokerStars hand history files and stores structured data in the database. The parser:

- Extracts hand details including table name and timestamp
- Creates a structured JSON representation
- Handles encoding issues gracefully
- Supports batch processing of multiple files

### 2. Win Rate Calculator (`player_win_rates.py`)

Calculates accurate player win rates using a table-based approach that:

- Identifies distinct table sessions (when players join and leave tables)
- Accounts for players leaving and rejoining the same table
- Properly handles multi-tabling by tracking a timeline of active tables
- Calculates precise active playing time for accurate hourly rates

### 3. Dataset Exporter (`export_to_hf.py`)

Exports filtered datasets for PokerGPT training based on:

- Player skill level (minimum win rate)
- Minimum number of hands played
- Game stages (e.g., preflop decisions)

## Usage

### 1. Initialize the Database

```bash
# Create the database
createdb poker_db

# Apply the schema
psql -d poker_db -f data_wrangler/schema.sql
```

### 2. Parse Hand Histories

```bash
parse-hands --input-dir /path/to/hand/histories --db-connection "postgresql://user:pass@localhost:5432/poker_db"
```

### 3. Calculate Player Win Rates

```bash
calculate-win-rates --db-connection "postgresql://user:pass@localhost:5432/poker_db" --min-hands 50
```

### 4. Export Dataset for PokerGPT

```bash
export-dataset --db-connection "postgresql://user:pass@localhost:5432/poker_db" --min-win-rate 500
```

## Table-Based Win Rate Calculation

This project implements a novel table-based approach to win rate calculation that addresses key challenges in poker analysis:

### Key Features

1. **Accurate Session Tracking**: Identifies when players join and leave specific tables
2. **Join/Leave Detection**: Detects when players leave and rejoin the same table by tracking presence in each hand
3. **Multi-Table Support**: Creates a timeline of active play that accounts for playing at multiple tables simultaneously
4. **Precise Active Time**: Calculates win rates based on actual active playing time, not total elapsed time

### How It Works

1. For each player, the system:

   - Identifies all tables they've played at
   - For each table, determines all hands played at that table
   - Detects when the player appears in and disappears from the player list
   - Creates distinct table sessions for each continuous span of play

2. For each table session, the system calculates:

   - Duration (difference between first and last hand timestamps)
   - Hands per hour
   - Win/loss in big blinds
   - Win rate (mbb/hour)

3. It then aggregates these metrics accounting for multi-tabling:
   - Creates a timeline of when the player was active at any table
   - Calculates true active hours based on this timeline
   - Computes the overall win rate weighted by actual playing time

This approach yields far more accurate win rates than simplistic calculations, particularly for players with sporadic playing patterns.

## References

This project supports the methodology described in the PokerGPT paper, which uses player win rates to identify high-quality training data for poker AI development.
