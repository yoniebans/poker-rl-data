# PokerGPT Target Dataset Format

This document outlines the input and output format structure used for training the PokerGPT language model. The dataset is structured as prompt-response pairs, where the prompt provides poker game state information and the response contains the action taken by winning players.

## Input Prompt Format

The input prompts follow a structured format that provides comprehensive information about the poker game state:

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [6], Currency: USD, Blind value: [$0.50/$1.00], Order: [1, 2, 3, 4, 5, 6], Seat 3 is the button.

    My cards: ['Th', 'Ah'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 5]

    Stage: "FLOP", Public cards: ['Kh', '7d', '2s', '**', '**']
    My rank: ["Pair"], Money: [97.50], Action: ["post BB 1.00"]

    Seat 1: ['**', '**'], Money: [100.00], Action: ["fold"], Discard: [True]
    Seat 2: ['**', '**'], Money: [98.50], Action: ["call 2.00"], Discard: [False]
    Seat 3: ['**', '**'], Money: [99.00], Action: ["fold"], Discard: [True]
    Seat 4: ['**', '**'], Money: [95.00], Action: ["post SB 0.50", "fold"], Discard: [True]
    Seat 6: ['**', '**'], Money: [102.00], Action: ["raise 2.00"], Discard: [False]

The pot value is [10.50]

The actions can be: ["fold", "call", "re-raise", "all-in"]. What should I do? If I choose to "re-raise", then how much? Choose a number from [4.00, 6.00, 10.00, 20.00, 50.00].
```

### Structure Breakdown:

1. **Introduction**: Frames the context for the language model.

2. **Game Configuration**:

   - `Player amount`: Total number of players at the table
   - `Currency`: Type of currency used
   - `Blind value`: Small and big blind amounts
   - `Order`: Order of players around the table
   - `Button position`: Which seat has the dealer button

3. **Player's Hand**:

   - `My cards`: The player's private cards in standard poker notation
   - `Card characteristics`: Properties of the cards:
     - `suit`: If the cards are of the same suit
     - `high`: If any card is 9 or higher
     - `close`: If the card values are less than 5 apart
   - `My seat`: The player's position at the table

4. **Game State**:

   - `Stage`: Current betting round (PREFLOP, FLOP, TURN, or RIVER)
   - `Public cards`: Community cards showing ('\*\*' for unrevealed cards)
   - `My rank`: Hand rank based on current cards (High, Pair, Two Pair, etc.)
   - `Money`: Player's current stack size
   - `Action`: Player's previous actions in this hand

5. **Other Players' Information**:

   - `Cards`: Always shown as ['**', '**'] (hidden from the player)
   - `Money`: Current stack size
   - `Action`: Previous actions taken by this player
   - `Discard`: Whether the player has folded (True/False)

6. **Decision Context**:
   - `Pot value`: Current size of the pot
   - `Available actions`: List of possible actions to take (contextually determined)
   - `Bet/raise sizing options`: Available sizes if betting or raising, dynamically generated based on game state (all-in amount not included in this list)

## Context-Dependent Action Types and Bet Sizing

1. **Action Types**: The available actions change depending on the betting context:

   - If no one has bet in the current round: ["fold", "check", "bet", "all-in"]
   - If someone has bet but no raises: ["fold", "call", "raise", "all-in"]
   - If someone has already raised: ["fold", "call", "re-raise", "all-in"]

2. **Betting Terminology**:

   - Use "bet" only when you're the first to put money in a betting round
   - Use "raise" when increasing someone else's bet for the first time
   - Use "re-raise" when raising after someone has already raised

3. **Bet Sizing Options**:
   - The "Choose a number from [...]" section never includes the all-in amount
   - Bet/raise options are presented as multiples of the big blind or pot-related sizes
   - Options are determined by the game state and betting round

## Expected Output Format

The output should be concise and follow poker terminology:

```
call
```

OR

```
raise 5.00
```

OR

```
re-raise 10.00
```

OR

```
bet 4.00
```

OR

```
check
```

OR

```
fold
```

OR

```
all-in
```

### Output Structure Breakdown:

1. **Basic Actions (without amounts)**:

   - `check`: Pass the action without betting (only when no one has bet)
   - `fold`: Discard your hand and exit the hand
   - `all-in`: Commit your entire stack

2. **Actions with Amounts**:
   - `call X`: Match the current bet of X (only when someone has bet)
   - `bet X`: Make a new bet of X (only when no one has bet)
   - `raise X`: Increase the current bet to X (when someone has bet, but no one has raised)
   - `re-raise X`: Increase after someone has already raised (when there's been at least one raise)

## Example Prompt-Response Pairs

### Example 1 - Preflop with One Raise Already

**Input:**

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [6], Currency: USD, Blind value: [$0.50/$1.00], Order: [1, 2, 3, 4, 5, 6], Seat 3 is the button.

    My cards: ['As', 'Ac'], the characteristics of my cards: ["high", "close"], My seat: [Seat 5]

    Stage: "PREFLOP", Public cards: ['**', '**', '**', '**', '**']
    My rank: ["High"], Money: [100.00], Action: ["post BB 1.00"]

    Seat 1: ['**', '**'], Money: [99.00], Action: ["fold"], Discard: [True]
    Seat 2: ['**', '**'], Money: [98.00], Action: ["fold"], Discard: [True]
    Seat 3: ['**', '**'], Money: [100.00], Action: ["call"], Discard: [False]
    Seat 4: ['**', '**'], Money: [94.50], Action: ["post SB 0.50", "fold"], Discard: [True]
    Seat 6: ['**', '**'], Money: [97.00], Action: ["raise 2.00"], Discard: [False]

The pot value is [1.50]

The actions can be: ["fold", "call", "re-raise", "all-in"]. What should I do? If I choose to "re-raise", then how much? Choose a number from [3.00, 4.00, 7.00, 10.00, 20.00, 50.00].
```

**Expected Output:**

```
re-raise 3.00
```

### Example 2 - Facing an Initial Bet

**Input:**

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [4], Currency: USD, Blind value: [$1.00/$2.00], Order: [1, 2, 3, 4], Seat 4 is the button.

    My cards: ['Jh', 'Qh'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 2]

    Stage: "FLOP", Public cards: ['2h', '7h', 'Kd', '**', '**']
    My rank: ["Flush Draw"], Money: [196.00], Action: ["post BB 2.00"]

    Seat 1: ['**', '**'], Money: [199.00], Action: ["post SB 1.00", "call"], Discard: [False]
    Seat 3: ['**', '**'], Money: [176.00], Action: ["bet 4.00"], Discard: [False]
    Seat 4: ['**', '**'], Money: [198.00], Action: ["fold"], Discard: [True]

The pot value is [14.00]

The actions can be: ["fold", "call", "raise", "all-in"]. What should I do? If I choose to "raise", then how much? Choose a number from [8.00, 12.00, 20.00, 40.00, 80.00].
```

**Expected Output:**

```
call
```

### Example 3 - Facing an All-In (Limited Options)

**Input:**

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [3], Currency: USD, Blind value: [$2.00/$5.00], Order: [1, 2, 3], Seat 2 is the button.

    My cards: ['Ks', 'Kd'], the characteristics of my cards: ["high", "close"], My seat: [Seat 3]

    Stage: "PREFLOP", Public cards: ['**', '**', '**', '**', '**']
    My rank: ["High"], Money: [85.00], Action: ["post SB 2.00"]

    Seat 1: ['**', '**'], Money: [83.00], Action: ["post BB 2.00", "fold"], Discard: [True]
    Seat 2: ['**', '**'], Money: [0.00], Action: ["all-in 150.00"], Discard: [False]

The pot value is [157.00]

The actions can be: ["fold", "call"]. What should I do?
```

**Expected Output:**

```
call
```

(Note: Here we're implicitly calling the full amount we have, effectively going all-in to call)

### Example 4 - Being First to Act (Check/Bet)

**Input:**

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [5], Currency: USD, Blind value: [$1.00/$2.00], Order: [1, 2, 3, 4, 5], Seat 1 is the button.

    My cards: ['9c', 'Tc'], the characteristics of my cards: ["suit", "close"], My seat: [Seat 4]

    Stage: "FLOP", Public cards: ['3c', '8c', 'Jh', '**', '**']
    My rank: ["Flush Draw"], Money: [198.00], Action: ["call"]

    Seat 1: ['**', '**'], Money: [200.00], Action: ["fold"], Discard: [True]
    Seat 2: ['**', '**'], Money: [199.00], Action: ["post SB 1.00", "call", "check"], Discard: [False]
    Seat 3: ['**', '**'], Money: [200.00], Action: ["post BB 2.00", "check"], Discard: [False]
    Seat 5: ['**', '**'], Money: [200.00], Action: ["fold"], Discard: [True]

The pot value is [6.00]

The actions can be: ["fold", "check", "bet", "all-in"]. What should I do? If I choose to "bet", then how much? Choose a number from [2.00, 5.00, 10.00, 15.00, 30.00, 60.00, 120.00].
```

**Expected Output:**

```
bet 5.00
```

### Example 5 - Facing a Raise (Re-raising opportunity)

**Input:**

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [4], Currency: USD, Blind value: [$2.00/$5.00], Order: [1, 2, 3, 4], Seat 1 is the button.

    My cards: ['Ad', 'Kd'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 3]

    Stage: "TURN", Public cards: ['7d', 'Td', '2c', 'Qh', '**']
    My rank: ["Flush Draw"], Money: [180.00], Action: ["post BB 5.00", "bet 15.00"]

    Seat 1: ['**', '**'], Money: [200.00], Action: ["fold"], Discard: [True]
    Seat 2: ['**', '**'], Money: [135.00], Action: ["post SB 2.00", "call", "raise 45.00"], Discard: [False]
    Seat 4: ['**', '**'], Money: [195.00], Action: ["fold"], Discard: [True]

The pot value is [85.00]

The actions can be: ["fold", "call", "re-raise", "all-in"]. What should I do? If I choose to "re-raise", then how much? Choose a number from [90.00, 135.00].
```

**Expected Output:**

```
call
```

## Database Implementation Guidelines

In the project codebase, these prompt-response pairs are generated from the structured poker hand data through the following process:

1. The `pokergpt_formatter.py` module contains the `format_hand_to_pokergpt_prompt` method that transforms structured hand data into the input prompt format.

2. The `format_batch_for_training` method in the same file creates the prompt-response pairs by:

   - Generating the prompt using `format_hand_to_pokergpt_prompt`
   - Extracting the winning player's action as the expected output

3. The extracted action is stored in the dataset alongside the prompt in the format:

   ```python
   {
       'prompt': formatted_prompt,
       'action': winning_action  # e.g., "raise 2.5" or "check"
   }
   ```

4. When exporting to HuggingFace, these pairs are preserved in the dataset structure for direct use in training.

Considerations for implementing this dataset format:

1. **Action Type Determination**:

   ```python
   def determine_available_actions(game_state):
       # Check if anyone has bet in this round
       current_bet_exists = any_active_bets_in_current_round(game_state)

       # Check if there has already been a raise in this round
       raise_exists = any_raises_in_current_round(game_state)

       # Check if we're in a heads-up situation with opponent all-in
       heads_up_vs_allin = (
           count_active_players(game_state) == 2 and
           opponent_is_allin(game_state)
       )

       if heads_up_vs_allin:
           # In heads-up vs all-in, we can only fold or call
           return ["fold", "call"]
       elif raise_exists:
           # Someone has already raised, we can fold, call, re-raise, or go all-in
           return ["fold", "call", "re-raise", "all-in"]
       elif current_bet_exists:
           # Someone has bet but no raises yet, we can fold, call, raise, or go all-in
           return ["fold", "call", "raise", "all-in"]
       else:
           # No one has bet, we can fold, check, bet, or go all-in
           return ["fold", "check", "bet", "all-in"]
   ```

2. **Blind and Button Position Validation**:

   ```python
   def validate_positions(game_state):
       button_seat = game_state["button_seat"]

       # Calculate expected SB and BB positions (clockwise from button)
       expected_sb_seat = (button_seat % game_state["player_count"]) + 1
       expected_bb_seat = (expected_sb_seat % game_state["player_count"]) + 1

       # Verify positions match expected order
       actual_sb_seat = find_seat_with_action(game_state, "post SB")
       actual_bb_seat = find_seat_with_action(game_state, "post BB")

       if actual_sb_seat != expected_sb_seat or actual_bb_seat != expected_bb_seat:
           raise ValueError(f"Invalid blind positions: SB should be seat {expected_sb_seat}, BB should be seat {expected_bb_seat}")
   ```

3. **Bet Sizing Generation**:

   ```python
   def generate_bet_sizes(game_state, action_type):
       big_blind = game_state["big_blind"]
       pot_size = game_state["pot_size"]
       min_bet = big_blind * 2  # Typical minimum opening bet

       if action_type == "bet":
           # Common bet sizes as multiples of BB or pot fractions
           return [
               round(big_blind * 2),       # 2x BB
               round(pot_size * 0.5),      # Half pot
               round(pot_size * 0.75),     # 3/4 pot
               round(pot_size),            # Full pot
               round(pot_size * 2),        # 2x pot
           ]
       elif action_type in ["raise", "re-raise"]:
           current_bet = game_state["current_bet"]
           min_raise = current_bet * 2     # Minimum raise is typically 2x current bet

           # Ensure min raise respects the previous raise amount
           prev_raise_amount = get_previous_raise_amount(game_state)
           if prev_raise_amount:
               min_raise = current_bet + prev_raise_amount

           # Generate standard raise sizings
           return [
               min_raise,
               round(min_raise * 1.5),
               round(pot_size),
               round(pot_size * 1.5),
               round(pot_size * 2.5)
           ]

       return []  # No sizing needed for check/fold/call/all-in
   ```

## Reward Function Basis

The reward function used for reinforcement learning evaluates model outputs based on how closely they match the winning player's action. Two primary components are considered:

1. **Action Match Reward**: Scores based on matching the action type (fold, check, call, bet, raise)

   - Exact match: 1.0
   - Action type match (e.g., bet vs. raise): 0.7
   - Related action match (e.g., aggressive vs. passive): 0.5

2. **Bet Sizing Reward**: For bet/raise actions, scores based on how closely the bet amount matches
   - Perfect match: 1.0
   - Scores decrease linearly as deviation increases
   - Zero score beyond max deviation threshold (default 50%)

These components are combined in the `CombinedPokerReward` with configurable weights (default: 60% action, 40% sizing) to produce the final reward signal for training.
