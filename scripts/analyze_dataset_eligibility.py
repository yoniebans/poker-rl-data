#!/usr/bin/env python3
import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def analyze_dataset_statistics():
    """
    Analyze the poker dataset to determine:
    1. Total number of hands in the database
    2. Total number of hands with a winning action
    3. Total number of hands that qualify for the dataset based on criteria
    """
    # Get database connection from environment variable
    db_connection = os.environ.get("DB_CONNECTION")
    if not db_connection:
        print("Error: DB_CONNECTION environment variable not set")
        print("Please set your database connection string in .env file")
        return
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_connection)
        cursor = conn.cursor()
        
        # 1. Total number of hands in the database
        cursor.execute("SELECT COUNT(*) FROM hand_histories")
        total_hands = cursor.fetchone()[0]
        
        # 2. Total number of hands with a winning action
        # Hands where the winner is known and there's a valid winning action
        cursor.execute("""
        SELECT COUNT(*) FROM hand_histories 
        WHERE winner IS NOT NULL 
        AND pokergpt_format::text LIKE '%"outcomes"%'
        """)
        hands_with_winning_action = cursor.fetchone()[0]
        
        # 3. Total number of hands that qualify for the dataset
        # Based on common eligibility criteria from code analysis:
        # - Has showdown (for visible cards)
        # - Winner has a minimum win rate
        # - Hand has proper structure
        
        cursor.execute("""
        SELECT COUNT(*) FROM hand_histories
        WHERE has_showdown = TRUE 
        AND raw_text LIKE '%shows [%'
        AND EXISTS (
            SELECT 1 FROM players p
            WHERE 
                p.player_id = winner
                AND p.mbb_per_hour >= 200
                AND p.total_hands >= 50
        )
        """)
        qualifying_hands = cursor.fetchone()[0]
        
        # Additional breakdowns by game stages
        cursor.execute("""
        SELECT 
            SUM(CASE WHEN has_preflop THEN 1 ELSE 0 END) as preflop_hands,
            SUM(CASE WHEN has_flop THEN 1 ELSE 0 END) as flop_hands,
            SUM(CASE WHEN has_turn THEN 1 ELSE 0 END) as turn_hands,
            SUM(CASE WHEN has_river THEN 1 ELSE 0 END) as river_hands,
            SUM(CASE WHEN has_showdown THEN 1 ELSE 0 END) as showdown_hands
        FROM hand_histories
        """)
        stage_counts = cursor.fetchone()
        
        # Check if dataset_records table exists and query it
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'dataset_records'
        )
        """)
        
        has_dataset_records = cursor.fetchone()[0]
        
        dataset_records_count = 0
        dataset_with_action_count = 0
        
        if has_dataset_records:
            # Get count of records in dataset_records
            cursor.execute("SELECT COUNT(*) FROM dataset_records")
            dataset_records_count = cursor.fetchone()[0]
            
            # Get count of records with winning action
            cursor.execute("""
            SELECT COUNT(*) FROM dataset_records
            WHERE winning_action IS NOT NULL 
            AND LENGTH(TRIM(winning_action)) > 0
            """)
            dataset_with_action_count = cursor.fetchone()[0]
            
        # Display results
        print("==== Poker Dataset Statistics ====")
        print(f"Total hands in database: {total_hands:,}")
        print(f"Hands with winning action: {hands_with_winning_action:,} ({hands_with_winning_action/total_hands*100:.2f}%)")
        print(f"Hands qualifying for dataset: {qualifying_hands:,} ({qualifying_hands/total_hands*100:.2f}%)")
        
        if has_dataset_records:
            print(f"Hands in actual dataset: {dataset_records_count:,} ({dataset_records_count/total_hands*100:.2f}%)")
            print(f"Dataset hands with winning action: {dataset_with_action_count:,} ({dataset_with_action_count/dataset_records_count*100:.2f}% of dataset)")
        
        print("\n--- Game Stage Breakdowns ---")
        if stage_counts:
            print(f"Hands with preflop: {stage_counts[0]} ({stage_counts[0]/total_hands*100:.2f}%)")
            print(f"Hands with flop: {stage_counts[1]} ({stage_counts[1]/total_hands*100:.2f}%)")
            print(f"Hands with turn: {stage_counts[2]} ({stage_counts[2]/total_hands*100:.2f}%)")
            print(f"Hands with river: {stage_counts[3]} ({stage_counts[3]/total_hands*100:.2f}%)")
            print(f"Hands with showdown: {stage_counts[4]} ({stage_counts[4]/total_hands*100:.2f}%)")
        
        # Get counts of hands per variant - with more detailed breakdown
        cursor.execute("""
        SELECT 
            has_preflop, has_flop, has_turn, has_river, has_showdown,
            COUNT(*) as hand_count
        FROM hand_histories
        GROUP BY has_preflop, has_flop, has_turn, has_river, has_showdown
        ORDER BY has_preflop, has_flop, has_turn, has_river, has_showdown
        """)
        
        variant_counts = cursor.fetchall()
        print("\n--- Detailed Stage Distribution ---")
        print("Preflop | Flop | Turn | River | Showdown | Count | Percentage")
        print("--------|------|------|-------|----------|-------|----------")
        
        # Create a summary of stage combinations
        stage_combinations = {}
        for has_preflop, has_flop, has_turn, has_river, has_showdown, count in variant_counts:
            # Calculate number of stages
            stages_count = has_preflop + has_flop + has_turn + has_river + has_showdown
            
            # Add to stage_combinations summary
            if stages_count not in stage_combinations:
                stage_combinations[stages_count] = 0
            stage_combinations[stages_count] += count
            
            # Print the detailed breakdown
            preflop = "Yes" if has_preflop else "No"
            flop = "Yes" if has_flop else "No"
            turn = "Yes" if has_turn else "No"
            river = "Yes" if has_river else "No"
            showdown = "Yes" if has_showdown else "No"
            
            print(f"{preflop:^8}|{flop:^6}|{turn:^6}|{river:^7}|{showdown:^10}|{count:7,}|{count/total_hands*100:8.2f}%")
        
        # Print the summary of stages count
        print("\n--- Hand Length Summary (Number of Stages) ---")
        for stages_count in sorted(stage_combinations.keys()):
            count = stage_combinations[stages_count]
            print(f"Hands with {stages_count} stages: {count:,} ({count/total_hands*100:.2f}%)")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_dataset_statistics()