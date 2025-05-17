# PokerStars Hand History Format

## Overview

The source data for the Poker-RL Data Pipeline consists of PokerStars hand history files. These files contain detailed records of poker games played on the PokerStars platform, capturing all actions, cards, and outcomes in a standardized text format. This document describes the structure and elements of this source data format.

## File Structure

Each file contains multiple hand histories, with each hand representing a complete poker hand from start to finish. Hands are separated by blank lines, and each hand follows a consistent structure:

```
PokerStars Hand #[HAND_ID]: [GAME_TYPE] ([BLINDS] [CURRENCY]) - [TIMESTAMP]
Table '[TABLE_NAME]' [TABLE_TYPE] Seat #[BUTTON_SEAT] is the button
[SEAT_INFORMATION]
[BLIND_POSTINGS]
*** HOLE CARDS ***
[PREFLOP_ACTIONS]
*** FLOP *** [COMMUNITY_CARDS]
[FLOP_ACTIONS]
*** TURN *** [FLOP_CARDS] [TURN_CARD]
[TURN_ACTIONS]
*** RIVER *** [FLOP_AND_TURN_CARDS] [RIVER_CARD]
[RIVER_ACTIONS]
*** SHOW DOWN ***
[SHOWDOWN_INFORMATION]
*** SUMMARY ***
[POT_AND_RAKE_INFORMATION]
[BOARD_INFORMATION]
[SEAT_RESULTS]
```

Not all sections are present in every hand - only the sections relevant to how far the hand progressed are included (e.g., a hand that ends preflop won't have flop, turn, or river sections).

## Detailed Format Description

### Header Information

The header of each hand contains basic metadata:

```
PokerStars Hand #254803218317:  Hold'em No Limit ($0.50/$1.00 USD) - 2025/02/10 18:53:59 WET [2025/02/10 13:53:59 ET]
Table 'Perseus III' 6-max Seat #3 is the button
```

Key elements:
- **Hand ID**: Unique identifier for the hand (e.g., `254803218317`)
- **Game Type**: Poker variant (e.g., `Hold'em No Limit`)
- **Blinds**: Small and big blind amounts (e.g., `$0.50/$1.00`)
- **Currency**: Currency used (e.g., `USD`)
- **Timestamp**: Date and time the hand was played, often in multiple time zones
- **Table Name**: Name of the virtual table (e.g., `'Perseus III'`)
- **Table Type**: Configuration of the table (e.g., `6-max`)
- **Button Position**: Seat number that has the dealer button (e.g., `Seat #3`)

### Seat Information

Following the header is the list of players at the table:

```
Seat 1: Supermegopro ($100 in chips) 
Seat 3: Xenicide ($100 in chips) 
Seat 5: michasia ($100 in chips)
```

Each line contains:
- **Seat Number**: Position at the table (e.g., `Seat 1`)
- **Player Name**: Username of the player (e.g., `Supermegopro`)
- **Stack Size**: Amount of chips the player has (e.g., `$100`)
- **Status** (optional): Players may have additional status indicators (e.g., `is sitting out`)

### Blind Postings

Before the hand begins, blinds are posted:

```
michasia: posts small blind $0.50
Supermegopro: posts big blind $1
```

Each line contains:
- **Player Name**: Who posted the blind
- **Blind Type**: Small blind or big blind
- **Amount**: How much was posted

### Hole Cards Section

The dealing of private cards is indicated by:

```
*** HOLE CARDS ***
```

No actual hole card information is provided in this section for the hand owner, but players' actions are recorded.

### Preflop Actions

After the hole cards section, preflop actions are listed:

```
Xenicide: folds 
michasia: raises $1.80 to $2.80
Supermegopro: raises $9.20 to $12
Xenicide: folds 
michasia: calls $9.20
```

Each action contains:
- **Player Name**: Who performed the action
- **Action Type**: The action taken (e.g., `folds`, `calls`, `raises`, `bets`, `checks`)
- **Amount** (for bets/raises/calls): How much was bet/raised/called
- **Total** (for raises): The total bet amount after the raise

### Flop Section

If the hand reaches the flop, it's indicated by:

```
*** FLOP *** [2s 4c Td]
```

This section includes:
- **FLOP marker**: Indicates the start of the flop section
- **Community Cards**: The three flop cards in brackets (e.g., `[2s 4c Td]`)

### Flop Actions

Similar to preflop actions, actions on the flop are listed:

```
Supermegopro: bets $12
michasia: calls $12
```

### Turn Section

If the hand reaches the turn, it's indicated by:

```
*** TURN *** [2s 4c Td] [4d]
```

This section includes:
- **TURN marker**: Indicates the start of the turn section
- **Flop Cards**: The three flop cards (e.g., `[2s 4c Td]`)
- **Turn Card**: The turn card in brackets (e.g., `[4d]`)

### Turn Actions

Actions on the turn are listed similarly to previous streets.

### River Section

If the hand reaches the river, it's indicated by:

```
*** RIVER *** [2s 4c Td 4d] [3h]
```

This section includes:
- **RIVER marker**: Indicates the start of the river section
- **Flop and Turn Cards**: The four previous community cards (e.g., `[2s 4c Td 4d]`)
- **River Card**: The river card in brackets (e.g., `[3h]`)

### River Actions

Actions on the river are listed similarly to previous streets.

### Showdown Section

If the hand reaches showdown, it's indicated by:

```
*** SHOW DOWN ***
Supermegopro: shows [Qh Qd] (two pair, Queens and Fours)
michasia: shows [As Ts] (two pair, Tens and Fours)
Supermegopro collected $200 from pot
```

This section includes:
- **SHOW DOWN marker**: Indicates the start of the showdown
- **Player Reveals**: Each player who shows their hand, with cards and hand description
- **Collection**: Who collected the pot and how much

### Summary Section

Every hand ends with a summary:

```
*** SUMMARY ***
Total pot $201 | Rake $1 
Board [2s 4c Td 4d 3h]
Seat 1: Supermegopro (small blind) showed [Qh Qd] and won ($200) with two pair, Queens and Fours
Seat 3: Xenicide (big blind) folded before Flop
Seat 5: michasia (button) showed [As Ts] and lost with two pair, Tens and Fours
```

This section includes:
- **SUMMARY marker**: Indicates the start of the summary
- **Pot Information**: Total pot size and rake amount
- **Board** (if applicable): Final community cards
- **Seat Results**: Outcome for each seat, including position, actions, and results

## Special Cases and Variations

### Early Hand Termination

If all players except one fold, the hand ends early. For example:

```
*** HOLE CARDS ***
Xenicide: folds 
michasia: folds 
Uncalled bet ($0.50) returned to Supermegopro
Supermegopro collected $1 from pot
Supermegopro: doesn't show hand 
*** SUMMARY ***
Total pot $1 | Rake $0 
Seat 1: Supermegopro (big blind) collected ($1)
Seat 3: Xenicide (button) folded before Flop (didn't bet)
Seat 5: michasia (small blind) folded before Flop
```

### All-In Situations

All-in situations are marked explicitly:

```
Supermegopro: bets $52.50 and is all-in
michasia: calls $52 and is all-in
Uncalled bet ($0.50) returned to Supermegopro
```

### Uncalled Bets

When a bet or raise isn't called, the uncalled portion is returned:

```
Uncalled bet ($1.25) returned to Xenicide
Xenicide collected $2.50 from pot
```

### Table Joins/Leaves

Players joining or leaving the table are noted:

```
Pon4uk.ua joins the table at seat #3 
Pon4uk.ua: sits out 
```

## Transformation Process

This raw hand history data undergoes several transformations in the Poker-RL Data Pipeline:

1. **Parsing**: The hand parser (`parse_poker_hands.py`) processes these text files to extract structured data
2. **JSON Conversion**: The structured data is converted to JSON format for database storage
3. **Analysis**: Win rates and other metrics are calculated for each player
4. **Formatting**: Hand data is reformatted into PokerGPT prompts for AI training

## Key Extraction Challenges

Several challenges must be addressed when parsing this format:

1. **Username Parsing**: Player names can contain spaces and special characters
2. **Action Identification**: Actions must be correctly attributed to players
3. **Card Extraction**: Cards must be properly parsed, especially for showdown hands
4. **Multi-Board Hands**: Some hands may involve running the board multiple times
5. **Encoding Issues**: Files may have encoding variations that need handling
6. **Edge Cases**: Various edge cases like disconnections, uncalled bets, etc.

## Examples of Complete Hands

### Example 1: Hand that goes to showdown

```
PokerStars Hand #254803223373:  Hold'em No Limit ($0.50/$1.00 USD) - 2025/02/10 18:54:17 WET [2025/02/10 13:54:17 ET]
Table 'Perseus III' 6-max Seat #5 is the button
Seat 1: Supermegopro ($100.50 in chips) 
Seat 3: Xenicide ($100 in chips) 
Seat 5: michasia ($100 in chips) 
Supermegopro: posts small blind $0.50
Xenicide: posts big blind $1
*** HOLE CARDS ***
michasia: raises $1.80 to $2.80
Supermegopro: raises $9.20 to $12
Xenicide: folds 
michasia: calls $9.20
*** FLOP *** [2s 4c Td]
Supermegopro: bets $12
michasia: calls $12
*** TURN *** [2s 4c Td] [4d]
Supermegopro: bets $24
michasia: calls $24
*** RIVER *** [2s 4c Td 4d] [3h]
Supermegopro: bets $52.50 and is all-in
michasia: calls $52 and is all-in
Uncalled bet ($0.50) returned to Supermegopro
*** SHOW DOWN ***
Supermegopro: shows [Qh Qd] (two pair, Queens and Fours)
michasia: shows [As Ts] (two pair, Tens and Fours)
Supermegopro collected $200 from pot
*** SUMMARY ***
Total pot $201 | Rake $1 
Board [2s 4c Td 4d 3h]
Seat 1: Supermegopro (small blind) showed [Qh Qd] and won ($200) with two pair, Queens and Fours
Seat 3: Xenicide (big blind) folded before Flop
Seat 5: michasia (button) showed [As Ts] and lost with two pair, Tens and Fours
```

### Example 2: Hand that ends preflop

```
PokerStars Hand #254803249903:  Hold'em No Limit ($0.50/$1.00 USD) - 2025/02/10 18:56:08 WET [2025/02/10 13:56:08 ET]
Table 'Perseus III' 6-max Seat #1 is the button
Seat 1: Supermegopro ($199 in chips) 
Seat 3: Xenicide ($100.50 in chips) 
Seat 5: michasia ($101.50 in chips) 
Xenicide: posts small blind $0.50
michasia: posts big blind $1
*** HOLE CARDS ***
Supermegopro: folds 
Xenicide: raises $2.50 to $3.50
michasia: calls $2.50
*** FLOP *** [6s Jh Ks]
Xenicide: checks 
michasia: bets $4.43
Xenicide: folds 
Uncalled bet ($4.43) returned to michasia
michasia collected $6.65 from pot
michasia: doesn't show hand 
*** SUMMARY ***
Total pot $7 | Rake $0.35 
Board [6s Jh Ks]
Seat 1: Supermegopro (button) folded before Flop (didn't bet)
Seat 3: Xenicide (small blind) folded on the Flop
Seat 5: michasia (big blind) collected ($6.65)
```

## Usage in the Pipeline

This source data is processed by the pipeline through these steps:

1. The `parse_poker_hands.py` script reads these raw text files
2. Regular expressions extract all relevant information
3. The data is converted to a structured JSON format and stored in the database
4. The win rate calculator analyzes player performance using this data
5. The PokerGPT formatter transforms the structured data into training prompts
6. The resulting dataset is exported in HuggingFace format

By understanding this source format, we can better appreciate the transformation process that produces the structured data needed for poker AI training.