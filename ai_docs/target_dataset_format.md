# PokerGPT Target Dataset Format

This document outlines the input and output format structure used for training the PokerGPT language model. The dataset is structured as prompt-response pairs, where the prompt provides poker game state information and the response contains the action taken by winning players.

## Input Prompt Format

The input prompts follow a structured format that provides comprehensive information about the poker game state:

```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [6], Currency: USD, Blind value: [$0.50/$1.00], Order: [1, 2, 3, 4, 5, 6], Seat 2 is the button.

    My cards: ['Th', 'Ah'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 3]

    Stage: "FLOP", Public cards: ['Kh', '7d', '2s', '**', '**']
    My rank: ["Pair"], Money: [97.50], Action: ["check"]
    
    Seat 1: ['**', '**'], Money: [100.00], Action: ["check"], Discard: [False]
    Seat 2: ['**', '**'], Money: [98.50], Action: ["call 1.00"], Discard: [False]
    Seat 4: ['**', '**'], Money: [95.00], Action: ["fold"], Discard: [True]
    Seat 5: ['**', '**'], Money: [102.00], Action: ["raise 2.00"], Discard: [False]
    Seat 6: ['**', '**'], Money: [99.00], Action: ["call 2.00"], Discard: [False]

The pot value is [10.50]

The actions can be: ["fold", "check", "call", "bet", "raise"]. What should I do? If I choose to "bet" or "raise", then how much? Choose a number from [0, 0.05, 0.15, 0.3, 0.5, 1, 2.5, 97.5].
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
   - `Public cards`: Community cards showing ('**' for unrevealed cards)
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
   - `Available actions`: List of possible actions to take
   - `Bet sizing options`: Available bet sizes if betting or raising

## Expected Output Format

The expected output format is the action taken by winning players in this situation, which serves as the target for training and the basis for the reward function. The output should be concise and follow a specific format:

```
call
```

OR

```
raise 1
```

OR

```
bet 0.5
```

OR

```
check
```

OR

```
fold
```

### Output Structure Breakdown:

1. **Basic Actions (without amounts)**:
   - `check`: Player passes the action without betting
   - `fold`: Player discards their hand and exits the hand

2. **Actions with Amounts**:
   - `call X`: Player matches the current bet of X
   - `bet X`: Player makes a new bet of X
   - `raise X`: Player increases the current bet to X

The output should contain just the action word followed by the amount if applicable, with no additional text, explanations, or commentary.

## Example Prompt-Response Pairs

### Example 1 - Preflop Decision

**Input:**
```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [6], Currency: USD, Blind value: [$0.50/$1.00], Order: [1, 2, 3, 4, 5, 6], Seat 3 is the button.

    My cards: ['As', 'Ac'], the characteristics of my cards: ["high", "close"], My seat: [Seat 5]

    Stage: "PREFLOP", Public cards: ['**', '**', '**', '**', '**']
    My rank: ["High"], Money: [100.00], Action: []
    
    Seat 1: ['**', '**'], Money: [99.00], Action: ["post SB 0.50"], Discard: [False]
    Seat 2: ['**', '**'], Money: [98.00], Action: ["post BB 1.00"], Discard: [False]
    Seat 3: ['**', '**'], Money: [100.00], Action: ["fold"], Discard: [True]
    Seat 4: ['**', '**'], Money: [95.00], Action: ["call 1.00"], Discard: [False]
    Seat 6: ['**', '**'], Money: [100.00], Action: [], Discard: [False]

The pot value is [2.50]

The actions can be: ["fold", "call", "raise"]. What should I do? If I choose to "bet" or "raise", then how much? Choose a number from [0, 0.05, 0.15, 0.3, 0.5, 1, 2.5, 5, 10, 100].
```

**Expected Output:**
```
raise 5
```

### Example 2 - Flop Decision

**Input:**
```
You are an experienced gambler. Now you need to assist me to make decisions in Texas Hold'em games. You have been provided with a series of observable information:

    Player amount: [4], Currency: USD, Blind value: [$1.00/$2.00], Order: [1, 2, 3, 4], Seat 1 is the button.

    My cards: ['Jh', 'Qh'], the characteristics of my cards: ["suit", "high", "close"], My seat: [Seat 2]

    Stage: "FLOP", Public cards: ['2h', '7h', 'Kd', '**', '**']
    My rank: ["Flush Draw"], Money: [196.00], Action: ["call 2.00"]
    
    Seat 1: ['**', '**'], Money: [198.00], Action: ["check"], Discard: [False]
    Seat 3: ['**', '**'], Money: [180.00], Action: ["bet 4.00"], Discard: [False]
    Seat 4: ['**', '**'], Money: [195.00], Action: ["fold"], Discard: [True]

The pot value is [14.00]

The actions can be: ["fold", "call", "raise"]. What should I do? If I choose to "bet" or "raise", then how much? Choose a number from [0, 0.5, 1, 2, 4, 8, 16, 32, 196].
```

**Expected Output:**
```
call 4
```

## Database Implementation

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