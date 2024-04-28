import argparse 
import pandas as pd
from collections import deque
from datetime import timedelta
import requests

def get_eur_pln_rate(date) -> float:
    date_str = date.strftime('%Y-%m-%d')
    url = f"http://api.nbp.pl/api/exchangerates/rates/a/eur/{date_str}/?format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        price = data['rates'][0]['mid']
        return price
    else:
        raise Exception(f"Failed to fetch data from NBP API. Status code: {response.status_code}")

def calculate_profit(df):
    # Convert the 'Time' column to datetime format
    df['Time'] = pd.to_datetime(df['Time'])
    
    # Convert the 'No. of shares' and 'Price / share' columns to float
    df['No. of shares'] = df['No. of shares'].astype(float)
    df['Price / share'] = df['Price / share'].astype(float)

    # Keep only those columns that are needed
    df = df[['Action', 'Time', 'ISIN', 'No. of shares', 'Price / share']]

    # Initialize an empty dictionary to store the stocks
    stocks = {}
    
    # Initialize a variable to store the total profit
    total_profit = 0

    # Iterate over the rows of the DataFrame
    for _, row in df.iterrows():
        action, time, id, no_of_shares, price_per_share = row
        
        # If the action is 'Market buy'
        if action == 'Market buy':
            # If the stock is not in the dictionary, add it
            if id not in stocks:
                stocks[id] = deque()
            # Append the number of shares, price per share, and time to the deque of the stock
            stocks[id].append((no_of_shares, price_per_share, time))
        
        # If the action is 'Market sell'
        elif action == 'Market sell':
            # Calculate the sell value in PLN
            sell_value_pln = no_of_shares * price_per_share * get_eur_pln_rate(time - timedelta(days=1))
            
            # Initialize a variable to store the cost value in PLN
            cost_value_pln = 0

            # While there are shares to sell
            while no_of_shares > 0:
                # Get the number of shares, price per share, and time of the first buy action of the stock
                buy_no_of_shares, buy_price_per_share, buy_time = stocks[id][0]
                
                # If the number of shares of the buy action is less than or equal to the number of shares to sell
                if buy_no_of_shares <= no_of_shares:
                    # Add the cost value in PLN of the buy action to the cost value in PLN
                    cost_value_pln += buy_no_of_shares * buy_price_per_share * get_eur_pln_rate(buy_time - timedelta(days=1))
                    # Subtract the number of shares of the buy action from the number of shares to sell
                    no_of_shares -= buy_no_of_shares
                    # Remove the buy action from the deque of the stock
                    stocks[id].popleft()
                else:
                    # Add the cost value in PLN of the number of shares to sell to the cost value in PLN
                    cost_value_pln += no_of_shares * buy_price_per_share * get_eur_pln_rate(buy_time - timedelta(days=1))
                    # Update the number of shares of the buy action
                    stocks[id][0] = (buy_no_of_shares - no_of_shares, buy_price_per_share, buy_time)
                    # Set the number of shares to sell to 0
                    no_of_shares = 0

            # Calculate the profit
            profit = sell_value_pln - cost_value_pln
            # Add the profit to the total profit
            total_profit += profit

    return total_profit

if __name__ == '__main__':
    # Parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, help='Path to the data file exported from trading212')
    args = parser.parse_args()

    # Load the data
    df = pd.read_csv(args.data)

    # Only interested in Market buy and Market sell actions
    df = df[df['Action'].isin(['Market buy', 'Market sell'])]

    # Keep only those actions where ISIN participated in Market sell
    df = df[df['ISIN'].isin(df[df['Action'] == 'Market sell']['ISIN'])]

    # Calculate the tax
    profit = calculate_profit(df)

    # Calculate the tax
    tax = max(0, profit * 0.19)

    print(f'Profit: {profit:.6f} PLN.\nTax to be paid: {tax:.6f} PLN.')