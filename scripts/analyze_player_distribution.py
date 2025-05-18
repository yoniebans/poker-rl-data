#!/usr/bin/env python3
import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from dotenv import load_dotenv

# Load environment variables (for DB connection)
load_dotenv()

def analyze_player_distribution():
    """
    Analyze and visualize the distribution of hands played per player
    to determine if certain players dominate the dataset.
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
        
        # Query to get player hand counts
        query = """
        SELECT 
            player_id,
            total_hands,
            total_bb,
            mbb_per_hand,
            mbb_per_hour,
            active_hours,
            tables,
            table_sessions
        FROM
            players
        WHERE
            total_hands > 0
        ORDER BY
            total_hands DESC
        """
        
        # Load the data into a pandas DataFrame
        df = pd.read_sql(query, conn)
        
        # Print basic statistics
        print(f"Total number of players: {len(df)}")
        print("\nHands played distribution:")
        print(df['total_hands'].describe())
        
        # Print top players by hand count
        print("\nTop 10 players by number of hands:")
        print(df.head(10)[['player_id', 'total_hands', 'mbb_per_hour']])
        
        # Calculate what percentage of hands the top players account for
        total_hands = df['total_hands'].sum()
        top_10_hands = df.head(10)['total_hands'].sum()
        top_player_hands = df.iloc[0]['total_hands']
        
        print(f"\nTotal hands across all players: {total_hands}")
        print(f"Top 10 players account for: {top_10_hands} hands ({(top_10_hands/total_hands)*100:.2f}%)")
        print(f"Top player accounts for: {top_player_hands} hands ({(top_player_hands/total_hands)*100:.2f}%)")
        
        # Create visualizations
        plt.figure(figsize=(12, 8))
        
        # 1. Histogram of hands played distribution
        plt.subplot(2, 2, 1)
        sns.histplot(df['total_hands'], bins=30, kde=True)
        plt.title('Distribution of Hands Played per Player')
        plt.xlabel('Number of Hands')
        plt.ylabel('Count of Players')
        
        # 2. CDF plot to show cumulative distribution
        plt.subplot(2, 2, 2)
        sorted_counts = np.sort(df['total_hands'])
        y_vals = np.arange(1, len(sorted_counts) + 1) / len(sorted_counts)
        plt.plot(sorted_counts, y_vals)
        plt.title('Cumulative Distribution of Hands Played')
        plt.xlabel('Number of Hands')
        plt.ylabel('Cumulative Proportion')
        plt.grid(True)
        
        # 3. Lorenz curve to visualize inequality in hand distribution
        plt.subplot(2, 2, 3)
        df_sorted = df.sort_values('total_hands')
        cum_hands = df_sorted['total_hands'].cumsum() / total_hands
        plt.plot(np.linspace(0, 1, len(df)), np.linspace(0, 1, len(df)), 'r--')  # Line of equality
        plt.plot(np.linspace(0, 1, len(df)), cum_hands)
        plt.title('Lorenz Curve of Hand Distribution')
        plt.xlabel('Cumulative Proportion of Players')
        plt.ylabel('Cumulative Proportion of Hands')
        plt.grid(True)
        
        # 4. Bar chart of top 20 players (horizontal bars for better readability)
        plt.subplot(2, 2, 4)
        top_20 = df.head(20).copy()
        top_20['player_id'] = top_20['player_id'].apply(lambda x: x[:10] + '...' if len(x) > 10 else x)
        # Swap x and y for horizontal bar chart
        sns.barplot(data=top_20, y='player_id', x='total_hands')
        plt.title('Top 20 Players by Hands Played')
        plt.ylabel('Player ID')
        plt.xlabel('Number of Hands')
        plt.tight_layout()
        
        # Calculate Gini coefficient for hand distribution
        sorted_hands = df['total_hands'].sort_values()
        cum_hands = sorted_hands.cumsum() / sorted_hands.sum()
        n = len(cum_hands)
        B = (np.sum(cum_hands) / n)
        gini = 1 - 2 * B
        print(f"\nGini coefficient for hand distribution: {gini:.4f}")
        print("(0 = perfect equality, 1 = perfect inequality)")
        
        # 5. Create an additional figure for win rate vs. hands played
        # Swap axes: Win rate on x-axis, hands played on y-axis
        plt.figure(figsize=(10, 6))
        plt.scatter(df['mbb_per_hour'], df['total_hands'], alpha=0.5)
        plt.title('Hands Played vs. Win Rate')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Total Hands Played')
        plt.grid(True)
        
        # Add a second plot with log scale for better distribution visibility
        plt.figure(figsize=(10, 6))
        plt.scatter(df['mbb_per_hour'], df['total_hands'], alpha=0.5)
        plt.yscale('log')  # Use log scale for y-axis (hands played)
        plt.title('Hands Played vs. Win Rate (Log Scale)')
        plt.xlabel('Win Rate (mbb/hour)')
        plt.ylabel('Total Hands Played (Log Scale)')
        plt.grid(True)
        
        # Save plots to separate files
        plt.figure(1)  # First figure with the 4 subplots
        plt.savefig('player_distribution_summary.png')
        
        plt.figure(2)  # Second figure with win rate vs hands
        plt.savefig('win_rate_vs_hands.png')
        
        plt.figure(3)  # Third figure with log scale
        plt.savefig('win_rate_vs_hands_log.png')
        
        print("\nPlots saved to:")
        print("- player_distribution_summary.png")
        print("- win_rate_vs_hands.png")
        print("- win_rate_vs_hands_log.png")
        
        # Close database connection
        conn.close()
        
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_player_distribution()