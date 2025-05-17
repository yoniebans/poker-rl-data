# PokerGPT Prompt Format Fixes - Accurate Action Options & Bet Sizing

## High Level Objective

- **Purpose**: Ensure the bet sizes and action options in PokerGPT prompts exactly match the specifications in target_dataset_format.md
- **Problem solved**: Current implementation provides incorrect action types and bet sizing options that don't follow the documented rules
- **Project alignment**: Ensures training data accurately represents realistic poker decision points

## Class/Type Changes

1. **PokerGPTFormatter**

   ```python
   # data_wrangler/pokergpt_formatter.py
   class PokerGPTFormatter:
       """
       Transform structured poker hand data into the PokerGPT prompt format
       as described in the research paper.
       """
       # Various method improvements focused on action types and bet sizing
   ```

## Method Changes

1. **Action Type Determination**
   - `_determine_available_actions()`: New method to correctly determine available action types based on betting context
   - Implementation follows target_dataset_format.md rules for action types:
     - No bet in current round: ["fold", "check", "bet", "all-in"]
     - Bet exists but no raises: ["fold", "call", "raise", "all-in"]
     - Raise exists: ["fold", "call", "re-raise", "all-in"]

2. **Bet Sizing Generation**
   - `_generate_bet_sizing_options()`: New method to generate proper bet/raise sizes
   - Follows rules from documentation:
     - Present options as multiples of big blind or pot-related sizes
     - Never include all-in amount in options list
     - Vary options based on game state and betting round

3. **Prompt Formatting Improvements**
   - `format_hand_to_pokergpt_prompt()`: Update to use the new action type and bet sizing methods
   - Fixes the way actions are listed in the prompt
   - Uses consistent terminology (bet vs. raise vs. re-raise)

## Interface Updates

1. **PokerGPT Prompt Generation Interface**
   - Action type determination logic will now follow the rules in target_dataset_format.md
   - Bet sizing options will be dynamically generated based on game context
   - Prompt structure remains consistent but with fixed content

## Documentation Updates

- Update method docstrings to clearly describe action type determination and bet sizing logic
- Add explanation of terminology conventions (bet vs. raise vs. re-raise)
- Add examples of correct output for different betting scenarios

## Implementation Approach

1. Branch: `feat/fix-pokergpt-prompt-format`
2. Development steps:
   1. Implement `_determine_available_actions()` method following the rules from the documentation
   2. Implement `_generate_bet_sizing_options()` method for dynamic bet size generation
   3. Update `format_hand_to_pokergpt_prompt()` to use the new methods
   4. Add comprehensive tests for all betting scenarios
   5. Validate output against example prompts in the documentation

## Benefits

- **Primary**: Generated prompts will accurately represent real poker decisions with correct action options
- **Technical**: Improved consistency and realism in training data for better model performance

## Dependencies

- No new package requirements
- Internal dependencies: Existing schema and data processing pipeline

This feature aligns with our principles by ensuring the dataset accurately represents poker decision-making processes, following the exact specifications laid out in the documentation. The improved action types and bet sizing options will create more realistic training data, ultimately leading to a more effective PokerGPT model.

## Current Implementation Analysis

The current implementation in `pokergpt_formatter.py` has the following issues:

1. **Action Type Determination** (Line 411-424):
   - Uses a simplified approach that doesn't correctly handle all betting scenarios
   - Doesn't distinguish between "bet", "raise", and "re-raise" based on the betting context
   - Always includes ["fold", "check", "call", "bet", "raise"] then removes some conditionally
   - Doesn't correctly identify when re-raises have occurred

2. **Bet Sizing Options** (Line 428-437):
   - Uses fixed percentage values [0, 0.05, 0.15, 0.3, 0.5, 1, 2.5] instead of dynamic sizes
   - Incorrectly includes all-in amount in options list
   - Doesn't scale options based on big blind or pot size
   - Doesn't distinguish between bet/raise/re-raise sizing contexts

3. **Action Terminology** (Line 426-436):
   - Doesn't follow the specific terminology rules:
     - "bet" only when first to put money in a betting round
     - "raise" when increasing someone's bet for the first time
     - "re-raise" when raising after someone has already raised

## Required Changes Implementation

### 1. Add Betting Context Analysis

We need to create a new method to analyze the betting context:

```python
def _analyze_betting_context(self, stage_actions):
    """
    Analyze the betting context of the current stage.
    
    Args:
        stage_actions: List of actions in the current betting stage
        
    Returns:
        Dictionary with betting context information:
        - has_bet: Whether anyone has bet in this round
        - has_raise: Whether anyone has raised in this round
        - facing_all_in: Whether player is facing an all-in
    """
    context = {
        'has_bet': False,
        'has_raise': False,
        'facing_all_in': False
    }
    
    for action in stage_actions:
        action_type = action.get('action', '')
        
        # Check for bets
        if action_type in ['bets', 'raises']:
            if not context['has_bet']:
                context['has_bet'] = True
            else:
                # If there's already a bet and someone raises, mark as raise
                context['has_raise'] = True
                
        # Check for all-ins
        if 'all-in' in action_type.lower():
            context['facing_all_in'] = True
    
    return context
```

### 2. Implement Proper Action Type Determination

Replace the current action determination with:

```python
def _determine_available_actions(self, stage_actions):
    """
    Determine available actions based on betting context.
    
    Args:
        stage_actions: List of actions in the current betting stage
        
    Returns:
        List of available action types following poker terminology
    """
    context = self._analyze_betting_context(stage_actions)
    
    # Handle special case: facing all-in with just two players
    if context['facing_all_in'] and self._is_heads_up(stage_actions):
        return ["fold", "call"]
    
    # Regular action determination following the rules
    if context['has_raise']:
        # Someone has already raised
        return ["fold", "call", "re-raise", "all-in"]
    elif context['has_bet']:
        # Someone has bet but no raises yet
        return ["fold", "call", "raise", "all-in"]
    else:
        # No one has bet yet
        return ["fold", "check", "bet", "all-in"]
```

### 3. Generate Proper Bet Sizing Options

Replace the current bet sizing with:

```python
def _generate_bet_sizing_options(self, action_type, game_state):
    """
    Generate appropriate bet sizing options based on action type and game state.
    
    Args:
        action_type: The type of action (bet, raise, re-raise)
        game_state: Current game state with pot size, big blind, etc.
        
    Returns:
        List of formatted bet size options
    """
    big_blind = float(game_state.get('big_blind', 1.0))
    pot_size = float(game_state.get('pot_size', 1.0))
    player_stack = float(game_state.get('player_stack', 100.0))
    
    # Common betting patterns from poker strategy
    if action_type == "bet":
        # First to put money in this round
        options = [
            round(big_blind * 2, 2),        # 2x BB (min bet)
            round(pot_size * 0.5, 2),       # Half pot
            round(pot_size * 0.75, 2),      # 3/4 pot
            round(pot_size, 2),             # Full pot
            round(pot_size * 1.5, 2),       # 1.5x pot
            round(pot_size * 2, 2)          # 2x pot
        ]
    elif action_type == "raise":
        # Raising someone's bet
        current_bet = float(game_state.get('current_bet', big_blind * 2))
        min_raise = current_bet * 2
        options = [
            round(min_raise, 2),            # Min raise (2x current bet)
            round(current_bet + pot_size * 0.5, 2),  # Current bet + half pot
            round(current_bet + pot_size * 0.75, 2), # Current bet + 3/4 pot
            round(current_bet + pot_size, 2),        # Current bet + pot
            round(pot_size * 2, 2)          # 2x pot
        ]
    elif action_type == "re-raise":
        # Re-raising after someone has already raised
        current_bet = float(game_state.get('current_bet', big_blind * 4))
        min_reraise = current_bet * 2
        options = [
            round(min_reraise, 2),          # Min re-raise
            round(current_bet + pot_size * 0.75, 2), # Current bet + 3/4 pot
            round(current_bet + pot_size, 2),        # Current bet + pot
            round(pot_size * 2, 2),         # 2x pot
            round(pot_size * 3, 2)          # 3x pot
        ]
    else:
        # No bet sizing needed for fold, check, call, all-in
        return []
    
    # Filter to ensure options are within player stack and unique
    valid_options = []
    for opt in options:
        # Round to 2 decimal places for cleaner display
        rounded_opt = round(opt, 2)
        if rounded_opt < player_stack and rounded_opt not in valid_options:
            valid_options.append(rounded_opt)
    
    # Sort in ascending order
    return sorted(valid_options)
```

### 4. Update the Prompt Generation

Update the prompt generation in `format_hand_to_pokergpt_prompt()` method:

```python
# Replace lines 410-438 with:
# Determine available actions based on game state
available_actions = self._determine_available_actions(stages.get(stage, {}).get('actions', []))

# Add pot value and available actions
prompt += f"\nThe pot value is [{pot_value:.2f}]\n"

# Generate formatted action prompt
action_prompt = f"The actions can be: {available_actions}. What should I do?"

# Add bet sizing options if applicable
bet_action_types = {"bet", "raise", "re-raise"} & set(available_actions)
if bet_action_types:
    # Get the appropriate action type for sizing options
    sizing_action = list(bet_action_types)[0]
    
    # Generate sizing options
    game_state = {
        'big_blind': blinds.split('/')[1].strip('$'),
        'pot_size': pot_value,
        'player_stack': player_stacks.get(player_perspective, default_stack),
        'current_bet': self._get_current_bet(stages.get(stage, {}).get('actions', []))
    }
    
    sizing_options = self._generate_bet_sizing_options(sizing_action, game_state)
    
    if sizing_options:
        action_prompt += f" If I choose to \"{sizing_action}\", then how much? Choose a number from {sizing_options}."

prompt += action_prompt
```

These changes will ensure the action types and bet sizing options in the prompts correctly follow the rules set out in the target_dataset_format.md documentation.