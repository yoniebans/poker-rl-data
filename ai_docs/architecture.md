# Poker-RL Data Pipeline Architecture

## Overview

The Poker-RL Data Pipeline is a comprehensive data processing system designed to transform raw poker hand histories into high-quality training datasets for poker AI models. The system focuses on accurately identifying skilled players through sophisticated win rate calculations, and preparing structured data in formats optimized for reinforcement learning and language model training.

## System Context

The following diagram illustrates how the Poker-RL Data Pipeline interacts with external systems and users:

```mermaid
C4Context
title System Context: Poker-RL Data Pipeline

Person(dataEngineer, "Data Engineer", "Configures and runs the data pipeline")
Person(modelResearcher, "ML Researcher", "Uses the processed datasets for model training")

System(pokerRLData, "Poker-RL Data Pipeline", "Processes poker hand histories and prepares AI training datasets")

System_Ext(pokerStars, "PokerStars", "Source of hand history files")
System_Ext(postgres, "PostgreSQL", "Stores structured hand data and player statistics")
System_Ext(huggingface, "HuggingFace Hub", "Hosts the processed datasets")
System_Ext(pokerRL, "Poker-RL Models", "Consumes the datasets for training")

Rel(dataEngineer, pokerRLData, "Configures, runs")
Rel(pokerRLData, pokerStars, "Reads hand history files from")
Rel(pokerRLData, postgres, "Stores & queries data in")
Rel(pokerRLData, huggingface, "Exports datasets to")
Rel(modelResearcher, huggingface, "Downloads datasets from")
Rel(modelResearcher, pokerRL, "Trains")
Rel(pokerRL, huggingface, "Uses datasets from")
```

## Container Architecture

The pipeline consists of four primary containers, each handling specific aspects of the data processing workflow:

```mermaid
C4Container
title Container Architecture: Poker-RL Data Pipeline

Person(dataEngineer, "Data Engineer", "Configures and runs the data pipeline")

System_Boundary(pokerRLData, "Poker-RL Data Pipeline") {
    Container(handParser, "Hand Parser", "Python", "Parses raw hand history files into structured format")
    Container(winRateCalc, "Win Rate Calculator", "Python", "Calculates accurate player win rates using table-based approach")
    Container(pokerGPTFormatter, "PokerGPT Formatter", "Python", "Formats hand data into prompts for language model training")
    Container(datasetExporter, "Dataset Exporter", "Python", "Exports filtered datasets to HuggingFace format")
}

System_Ext(pokerStars, "PokerStars", "Source of hand history files")
System_Ext(postgres, "PostgreSQL", "Stores structured hand data and player statistics")
System_Ext(huggingface, "HuggingFace Hub", "Hosts the processed datasets")

Rel(dataEngineer, handParser, "Runs with input directory and DB connection")
Rel(dataEngineer, winRateCalc, "Runs with min hands threshold")
Rel(dataEngineer, datasetExporter, "Runs with filtering criteria")

Rel(handParser, pokerStars, "Reads hand history files from")
Rel(handParser, postgres, "Stores parsed hands in")
Rel(winRateCalc, postgres, "Reads hand data & updates player stats")
Rel(pokerGPTFormatter, postgres, "Reads hand and player data")
Rel(datasetExporter, postgres, "Queries filtered hand data")
Rel(datasetExporter, pokerGPTFormatter, "Uses to format prompts")
Rel(datasetExporter, huggingface, "Exports datasets to")
```

## Component Architecture

Each container consists of multiple components with specific responsibilities:

### Hand Parser Components

```mermaid
C4Component
title Component Architecture: Hand Parser

Container_Boundary(handParser, "Hand Parser") {
    Component(fileProcessor, "File Processor", "parse_poker_hands.py", "Processes hand history files with encoding handling")
    Component(handExtractor, "Hand Extractor", "parse_poker_hands.py", "Extracts individual hands from file content")
    Component(gameStageParser, "Game Stage Parser", "parse_poker_hands.py:_extract_stages", "Parses preflop, flop, turn, river, showdown stages")
    Component(actionParser, "Action Parser", "parse_poker_hands.py:_parse_actions", "Parses player actions, bet sizes, and all-ins")
    Component(dbInserter, "Database Inserter", "parse_poker_hands.py:insert_hand", "Inserts parsed hands into database")
}

System_Ext(fileSystem, "File System", "Contains hand history files")
System_Ext(postgres, "PostgreSQL", "Stores structured hand data")

Rel(fileProcessor, fileSystem, "Reads files from")
Rel(fileProcessor, handExtractor, "Passes file content to")
Rel(handExtractor, gameStageParser, "Extracts hands & passes to")
Rel(gameStageParser, actionParser, "Passes stage text to")
Rel(handExtractor, dbInserter, "Sends parsed hand to")
Rel(dbInserter, postgres, "Inserts data into")
```

### Win Rate Calculator Components

```mermaid
C4Component
title Component Architecture: Win Rate Calculator

Container_Boundary(winRateCalc, "Win Rate Calculator") {
    Component(tableSessionIdentifier, "Table Session Identifier", "player_win_rates.py:identify_player_table_sessions", "Identifies when players join/leave tables")
    Component(timelineAnalyzer, "Timeline Analyzer", "player_win_rates.py:calculate_player_table_stats", "Creates timeline of player activity")
    Component(multiTableHandler, "Multi-Table Handler", "player_win_rates.py:calculate_player_table_stats", "Handles overlapping play at multiple tables")
    Component(metricsCalculator, "Metrics Calculator", "player_win_rates.py:calculate_win_rates", "Calculates mbb/hand and mbb/hour metrics")
}

System_Ext(postgres, "PostgreSQL", "Stores hand and player data")

Rel(tableSessionIdentifier, postgres, "Queries hand histories from")
Rel(tableSessionIdentifier, timelineAnalyzer, "Provides session data to")
Rel(timelineAnalyzer, multiTableHandler, "Creates timeline for")
Rel(multiTableHandler, metricsCalculator, "Provides active time to")
Rel(metricsCalculator, postgres, "Updates player stats in")
```

### PokerGPT Formatter Components

```mermaid
C4Component
title Component Architecture: PokerGPT Formatter

Container_Boundary(pokerGPTFormatter, "PokerGPT Formatter") {
    Component(cardExtractor, "Card Extractor", "pokergpt_formatter.py:_extract_private_cards", "Extracts player's private cards")
    Component(handEvaluator, "Hand Evaluator", "poker_hand_evaluator.py", "Evaluates hand strength")
    Component(cardCharacterizer, "Card Characterizer", "pokergpt_formatter.py:_get_card_characteristics", "Analyzes card characteristics")
    Component(promptGenerator, "Prompt Generator", "pokergpt_formatter.py:format_hand_to_pokergpt_prompt", "Generates PokerGPT-formatted prompts")
}

System_Ext(postgres, "PostgreSQL", "Stores hand data")

Rel(cardExtractor, postgres, "Reads hand data from")
Rel(cardExtractor, handEvaluator, "Provides cards to")
Rel(cardExtractor, cardCharacterizer, "Provides cards to")
Rel(handEvaluator, promptGenerator, "Provides hand rank to")
Rel(cardCharacterizer, promptGenerator, "Provides characteristics to")
```

### Dataset Exporter Components

```mermaid
C4Component
title Component Architecture: Dataset Exporter

Container_Boundary(datasetExporter, "Dataset Exporter") {
    Component(queryBuilder, "Query Builder", "export_to_hf.py:export_winning_player_dataset", "Builds SQL queries with filters")
    Component(batchProcessor, "Batch Processor", "export_to_hf.py:export_dataset", "Processes data in batches")
    Component(datasetCardGenerator, "Dataset Card Generator", "export_to_hf.py:_create_dataset_card", "Creates HuggingFace dataset cards")
    Component(hfExporter, "HuggingFace Exporter", "export_to_hf.py:export_dataset", "Exports to HuggingFace format")
}

System_Ext(postgres, "PostgreSQL", "Stores hand and player data")
System_Ext(huggingface, "HuggingFace Hub", "Hosts the processed datasets")
Container_Ext(pokerGPTFormatter, "PokerGPT Formatter", "Formats hand data into prompts")

Rel(queryBuilder, postgres, "Queries filtered data from")
Rel(queryBuilder, batchProcessor, "Provides filtered data to")
Rel(batchProcessor, pokerGPTFormatter, "Sends hand data to")
Rel(batchProcessor, datasetCardGenerator, "Provides dataset info to")
Rel(batchProcessor, hfExporter, "Provides processed data to")
Rel(datasetCardGenerator, hfExporter, "Provides dataset card to")
Rel(hfExporter, huggingface, "Uploads dataset to")
```

## Process Flow

The following sequence diagram illustrates the high-level flow through the Poker-RL Data Pipeline:

```mermaid
sequenceDiagram
    participant User as Data Engineer
    participant Parser as Hand Parser
    participant DB as PostgreSQL
    participant WinRate as Win Rate Calculator
    participant GPTFormatter as PokerGPT Formatter
    participant Exporter as Dataset Exporter
    participant HF as HuggingFace Hub

    User->>Parser: Run parse-hands with input directory
    Parser->>Parser: Process hand history files
    Parser->>DB: Insert structured hand data
    Parser-->>User: Report processing complete

    User->>WinRate: Run calculate-win-rates
    WinRate->>DB: Query hand histories
    WinRate->>WinRate: Identify table sessions
    WinRate->>WinRate: Calculate timeline
    WinRate->>WinRate: Handle multi-tabling
    WinRate->>DB: Update player statistics
    WinRate-->>User: Report win rates calculated

    User->>Exporter: Run export-dataset with filters
    Exporter->>DB: Query filtered hands
    Exporter->>GPTFormatter: Format hands as prompts
    GPTFormatter-->>Exporter: Return formatted prompts
    Exporter->>Exporter: Create dataset
    Exporter->>Exporter: Generate dataset card
    Exporter->>HF: Push dataset (optional)
    Exporter-->>User: Report export complete
```

## Component Details

### 1. Hand Parser (`parse_poker_hands.py`)

The Hand Parser is responsible for converting raw poker hand history text files into structured database records.

**Key Responsibilities:**
- Process hand history files with robust encoding handling
- Extract individual hands using regex pattern matching
- Parse game stages (preflop, flop, turn, river, showdown)
- Extract player actions, cards, and bet amounts
- Handle special cases like multi-board hands
- Store structured data in PostgreSQL

**Design Considerations:**
- Uses regex patterns for reliable text parsing
- Implements error handling for problematic hands
- Tracks diagnostic information for parser issues
- Batches database operations for efficiency

### 2. Win Rate Calculator (`player_win_rates.py`)

The Win Rate Calculator implements a sophisticated table-based approach to accurately measure player skill levels.

**Key Responsibilities:**
- Identify distinct table sessions for each player
- Detect when players join and leave specific tables
- Create a timeline of active play accounting for multi-tabling
- Calculate precise active playing time
- Compute win rates in mbb/hand and mbb/hour

**Design Considerations:**
- Uses timeline analysis to handle overlapping table sessions
- Accounts for breaks between sessions
- Normalizes win rates based on actual active time
- Maintains detailed table session data for analysis

### 3. PokerGPT Formatter (`pokergpt_formatter.py`)

The PokerGPT Formatter transforms structured hand data into prompts formatted for language model training.

**Key Responsibilities:**
- Extract player private cards from showdown hands
- Evaluate hand strength using the poker hand evaluator
- Analyze card characteristics (high cards, suited, connected)
- Generate prompts following the PokerGPT paper format
- Support action extraction for supervised training

**Design Considerations:**
- Follows the exact prompt structure from PokerGPT research
- Provides card and hand analysis
- Formats stage-specific information
- Presents appropriate action options

### 4. Dataset Exporter (`export_to_hf.py`)

The Dataset Exporter filters hand data by player skill and prepares datasets for HuggingFace.

**Key Responsibilities:**
- Build SQL queries with filtering criteria
- Process data in batches to handle large datasets
- Generate formatted prompts using the PokerGPT Formatter
- Create comprehensive dataset cards
- Export to HuggingFace Dataset format
- Push datasets to HuggingFace Hub

**Design Considerations:**
- Supports multiple filtering options (win rate, hands played)
- Creates specialized datasets (winning players, preflop decisions)
- Handles authentication with HuggingFace Hub
- Provides detailed dataset documentation

## Data Model

The system uses two primary database tables:

### `hand_histories` Table

Stores individual poker hands with structured data:
- `hand_id`: Unique identifier
- `raw_text`: Original hand history text
- `pokergpt_format`: JSON representation
- `game_type`: Type of poker game
- `blinds`: Array of small/big blind values
- `big_blind`: Big blind amount
- `player_count`: Number of players
- `winner`: Player who won the hand
- `bb_won`: Amount won in big blinds
- Game state flags (`has_preflop`, `has_flop`, etc.)
- `player_ids`: Array of player identifiers
- `table_name`: Name of the poker table
- Various position and timestamp information

### `players` Table

Stores player statistics with an emphasis on table-based metrics:
- `player_id`: Unique identifier
- `total_hands`: Total number of hands played
- `total_bb`: Total big blinds won/lost
- `mbb_per_hand`: Win rate in milli-big blinds per hand
- `mbb_per_hour`: Win rate in milli-big blinds per hour
- `hands_per_hour`: Average hands played per hour
- `active_hours`: Total time actively playing
- `tables`: Number of distinct tables played
- `table_sessions`: Number of distinct table sessions
- `table_data`: JSONB array of table session details
- Timestamp information

## Technical Implementation

The pipeline is implemented in Python with the following key dependencies:
- `psycopg2`: PostgreSQL database connectivity
- `pandas`: Data manipulation
- `datasets`: HuggingFace dataset creation
- `huggingface-hub`: HuggingFace Hub integration

Command-line interfaces are provided for each major component:
- `parse-hands`: Parse hand history files
- `calculate-win-rates`: Calculate player win rates
- `export-dataset`: Export filtered datasets
- `create-pokergpt-dataset`: Create specialized PokerGPT datasets

## Future Considerations

1. **Scalability Improvements**:
   - Implement parallel processing for hand parsing
   - Add support for incremental updates to the database
   - Optimize database queries for larger datasets

2. **Feature Enhancements**:
   - Support for additional poker variants
   - Enhanced player skill metrics beyond win rate
   - Strategic decision point identification

3. **Integration Options**:
   - Direct integration with poker AI training pipelines
   - Real-time processing capabilities
   - API for programmatic access to processed data