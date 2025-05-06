# PokerGPT Data Processing

Tools for processing poker hand histories and preparing training data for PokerGPT.

## Components

- **parse_poker_hands.py**: Parse PokerStars hand histories and store in database
- **player_win_rates.py**: Calculate win rates for players
- **export_to_hf.py**: Export filtered datasets to HuggingFace format
- **migrate_database.py**: Migrate database schema to the new structure
- **check_db_schema.py**: Verify database schema and statistics

## Usage

See each script's help output for detailed usage instructions:

```bash
python -m data_wrangler.parse_poker_hands --help
python -m data_wrangler.player_win_rates --help
python -m data_wrangler.export_to_hf --help
```