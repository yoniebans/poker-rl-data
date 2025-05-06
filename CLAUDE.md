# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a data processing pipeline for poker hand histories, specifically designed to support poker-rl training. The pipeline:

1. Parses PokerStars hand history files
2. Stores data in a PostgreSQL database
3. Calculates player win rates using a table-based approach
4. Exports filtered datasets to HuggingFace format for training

## Commands

### Setup and Installation

```bash
# Create and activate conda environment
conda create -n poker-data python=3.10
conda activate poker-data

# Install package and dependencies
pip install -e .
```

### Database Initialization

```bash
# Create PostgreSQL database
createdb poker_db

# Initialize schema
psql -d poker_db -f data_wrangler/schema.sql
```

### Data Processing Pipeline

```bash
# 1. Parse hand histories
parse-hands --input-dir /path/to/hand/histories --db-connection "postgresql://user:pass@localhost:5432/poker_db"

# 2. Calculate player win rates
calculate-win-rates --db-connection "postgresql://user:pass@localhost:5432/poker_db" --min-hands 50

# 3. Export dataset for poker-rl
export-dataset --db-connection "postgresql://user:pass@localhost:5432/poker_db" --min-win-rate 500 --dataset-name "poker_winning_players"
```

### Development Commands

```bash
# Run linting
black data_wrangler/  # auto-format code
isort data_wrangler/  # sort imports
flake8 data_wrangler/  # lint for errors

# Run tests (when implemented)
pytest 
```

## Key Architecture Components

### Database Schema

The project uses two primary tables:

1. `hand_histories` - Stores individual poker hands with structured data
   - Contains raw text, structured JSON, player info, and game state flags
   - Has a table-based structure for accurate time tracking and win rate calculation

2. `players` - Stores player statistics
   - Tracks win rates in mbb/hand and mbb/hour
   - Contains table-based metrics for accurate multi-table tracking
   - Stores session data for advanced analytics

### Core Components

1. **Hand Parser** (`parse_poker_hands.py`)
   - Parses PokerStars hand history files with regex pattern matching
   - Extracts table names, timestamps, and player actions
   - Converts to structured JSON format for later analysis
   - Handles encoding issues and edge cases robustly

2. **Win Rate Calculator** (`player_win_rates.py`)
   - Implements a novel table-based approach for accurate win rate calculation
   - Identifies when players join and leave specific tables
   - Creates a timeline to handle multi-tabling correctly 
   - Calculates true active hours for accurate hourly metrics

3. **Dataset Exporter** (`export_to_hf.py`)
   - Filters hands based on player skill level (win rate)
   - Exports to HuggingFace datasets format
   - Supports pushing to HuggingFace Hub

### Table-Based Win Rate Calculation

The project uses a sophisticated approach for win rate calculation:
- Identifies distinct table sessions for each player
- Properly handles players leaving and rejoining tables
- Creates a timeline of active play to correctly account for multi-tabling
- Calculates win rates based on actual active time rather than elapsed time