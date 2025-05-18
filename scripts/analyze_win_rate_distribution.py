#!/usr/bin/env python3
import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def analyze_win_rate_distribution():
    """
    Analyze and visualize the distribution of player win rates
    to understand the skill distribution across the dataset.
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
        
        # Query to get player win rates
        query = """
        SELECT 
            player_id,
            total_hands,
            total_bb,
            mbb_per_hand,
            mbb_per_hour,
            active_hours
        FROM
            players
        WHERE
            total_hands >= 50  -- Minimum hands threshold for meaningful win rate
        ORDER BY
            mbb_per_hour DESC
        """
        
        # Load the data into a pandas DataFrame
        df = pd.read_sql(query, conn)
        
        # Print basic statistics
        print(f"Total number of players: {len(df)}")
        print("\nWin rate distribution (mbb/hour):")
        print(df['mbb_per_hour'].describe([0.1, 0.25, 0.5, 0.75, 0.9]))
        
        # Print top players by win rate
        print("\nTop 10 players by win rate (at least 50 hands):")
        print(df.head(10)[['player_id', 'mbb_per_hour', 'total_hands']])
        
        # Create visualizations
        plt.figure(figsize=(15, 10))
        
        # 1. Histogram of win rates
        plt.subplot(2, 2, 1)
        sns.histplot(df['mbb_per_hour'], bins=30, kde=True)
        plt.title('Distribution of Player Win Rates')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Count of Players')
        
        # 2. Win rate vs hands with size proportional to total BB won/lost
        # Calculate marker sizes based on absolute BB won/lost (scaled)
        sizes = np.abs(df['total_bb']) / df['total_bb'].abs().max() * 100
        
        plt.subplot(2, 2, 2)
        plt.scatter(df['mbb_per_hour'], df['total_hands'], s=sizes, alpha=0.5)
        plt.title('Win Rate vs. Hands Played')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Total Hands Played')
        plt.grid(True)
        
        # 3. Win rate by player volume (divide into quantiles)
        plt.subplot(2, 2, 3)
        # Create quantiles based on number of hands played
        df['hands_quantile'] = pd.qcut(df['total_hands'], 5, labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'])
        sns.boxplot(x='hands_quantile', y='mbb_per_hour', data=df)
        plt.title('Win Rate by Player Volume')
        plt.xlabel('Player Volume (Hands Played)')
        plt.ylabel('Win Rate (mbb/hour)')
        
        # 4. Win rate CDF
        plt.subplot(2, 2, 4)
        sorted_rates = np.sort(df['mbb_per_hour'])
        y_vals = np.arange(1, len(sorted_rates) + 1) / len(sorted_rates)
        plt.plot(sorted_rates, y_vals)
        plt.axvline(x=0, color='r', linestyle='--', label='Breakeven')
        plt.title('Cumulative Distribution of Win Rates')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Cumulative Proportion')
        plt.grid(True)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig('win_rate_distribution.png')
        
        # Additional plots - log scale for better visualization
        plt.figure(figsize=(12, 10))
        
        # 1. Win rate distribution with trimmed outliers (focus on the majority)
        q_low = df['mbb_per_hour'].quantile(0.05)
        q_high = df['mbb_per_hour'].quantile(0.95)
        trimmed_df = df[(df['mbb_per_hour'] >= q_low) & (df['mbb_per_hour'] <= q_high)]
        
        plt.subplot(2, 1, 1)
        sns.histplot(trimmed_df['mbb_per_hour'], bins=30, kde=True)
        plt.axvline(x=0, color='r', linestyle='--', label='Breakeven')
        plt.title('Win Rate Distribution (5-95 percentile range)')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Count of Players')
        plt.legend()
        
        # 2. Win rate by volume (bubble chart) - use log scale for win rates
        plt.subplot(2, 1, 2)
        volume_groups = df.groupby('hands_quantile').agg({
            'mbb_per_hour': 'mean',
            'total_hands': 'mean',
            'player_id': 'count'
        }).reset_index()
        
        bubble_sizes = volume_groups['player_id'] / volume_groups['player_id'].max() * 500
        
        plt.scatter(
            volume_groups['mbb_per_hour'], 
            volume_groups['total_hands'],
            s=bubble_sizes,
            alpha=0.7
        )
        
        # Add labels to the bubbles
        for i, row in volume_groups.iterrows():
            plt.annotate(
                row['hands_quantile'],
                (row['mbb_per_hour'], row['total_hands']),
                ha='center'
            )
            
        plt.title('Average Win Rate by Player Volume')
        plt.xlabel('Average Win Rate (mbb/hour)')
        plt.ylabel('Average Hands Played')
        plt.grid(True)
        
        plt.tight_layout()
        plt.savefig('win_rate_by_volume.png')
        
        # Calculate percentage of winning players
        winning_players = len(df[df['mbb_per_hour'] > 0])
        winning_pct = (winning_players / len(df)) * 100
        
        print(f"\nWinning players: {winning_players} out of {len(df)} ({winning_pct:.2f}%)")
        print(f"Median win rate: {df['mbb_per_hour'].median():.2f} mbb/hour")
        
        print("\nPlots saved to:")
        print("- win_rate_distribution.png")
        print("- win_rate_by_volume.png")
        
        # Close database connection
        conn.close()
        
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_win_rate_distribution()