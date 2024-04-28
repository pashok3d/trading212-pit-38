import argparse 
import pandas as pd
from collections import deque
from datetime import timedelta
import requests

TAX_RATE = 0.19

def get_eur_pln_rate(date: pd.Timestamp) -> float:
    """
    Get the exchange rate of EUR to PLN from NBP API for a given date
    
    Raises:
        Exception: If the API request fails
    """
    date_str = date.strftime('%Y-%m-%d')
    url = f"http://api.nbp.pl/api/exchangerates/rates/a/eur/{date_str}/?format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        price = data['rates'][0]['mid']
        return price
    else:
        raise Exception(f"Failed to fetch EUR-PLN exchange rate from NBP API. Status code: {response.status_code}")

def calculate_profit(df):
    stocks = {}
    total_profit = 0

    for _, row in df.iterrows():
        action, time, id, no_of_shares, price_per_share = row
        
        if action == 'Market buy':
            if id not in stocks:
                stocks[id] = deque()
            # Append the number of shares, price per share, and time to the deque of the stock
            stocks[id].append((no_of_shares, price_per_share, time))
        
        elif action == 'Market sell':
            sell_value_pln = no_of_shares * price_per_share * get_eur_pln_rate(time - timedelta(days=1))
            cost_value_pln = 0

            while no_of_shares > 0:
                try:
                    # Get the leftmost buy operation from the deque to follow FIFO rule in tax calculation
                    buy_no_of_shares, buy_price_per_share, buy_time = stocks[id][0]
                except IndexError:
                    raise Exception(f"Number of shares to sell can't be greater than the number of shares bought. ISIN: {id}, Date: {time}. Make sure that: 1. all operations of action 'Market buy' for {id} are included in data, 2. Required merge/split events are provided for {id}.") 
                except KeyError:
                    raise Exception(f"Sell action can't be executed without preceding buy action. ISIN: {id}, Date: {time}. Make sure all operations of action 'Market buy' for {id} are included in data.")
                
                if buy_no_of_shares <= no_of_shares:
                    # Leftmost buy order is completely consumed by the sell order
                    cost_value_pln += buy_no_of_shares * buy_price_per_share * get_eur_pln_rate(buy_time - timedelta(days=1))
                    # Subtract leftmost buy order from sell order
                    no_of_shares -= buy_no_of_shares
                    # Remove leftmost buy order from the deque
                    stocks[id].popleft()
                else:
                    # Leftmost buy order is partially consumed by the sell order
                    cost_value_pln += no_of_shares * buy_price_per_share * get_eur_pln_rate(buy_time - timedelta(days=1))
                    # Update number of shares in the leftmost buy order
                    stocks[id][0] = (buy_no_of_shares - no_of_shares, buy_price_per_share, buy_time)
                    break

            profit = sell_value_pln - cost_value_pln
            total_profit += profit

        elif action == 'Split':
            # Multiply the number of shares and divide the price by ratio
            for i in range(len(stocks[id])):
                stocks[id][i] = (stocks[id][i][0] * no_of_shares, stocks[id][i][1] / no_of_shares, stocks[id][i][2])

        elif action == 'Merge':
            # Divide the number of shares and multiply the price by ratio
            for i in range(len(stocks[id])):
                stocks[id][i] = (stocks[id][i][0] / no_of_shares, stocks[id][i][1] * no_of_shares, stocks[id][i][2])


    return total_profit

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, required=True, help='Path to the data file exported from trading212 in csv format')
    parser.add_argument('--merge_split_events', type=str, help='Path to the merge/split events of the stocks in jsonl format')
    args = parser.parse_args()

    # Load the data
    df = pd.read_csv(args.data)

    # Start preprocessing the data
    df = df.drop_duplicates(subset=['ID'])
    df = df[df['Action'].isin(['Market buy', 'Market sell'])]

    # Keep only those actions where ISIN participated in Market sell
    df = df[df['ISIN'].isin(df[df['Action'] == 'Market sell']['ISIN'])]

    df['Time'] = pd.to_datetime(df['Time'])
    df['No. of shares'] = df['No. of shares'].astype(float)
    df['Price / share'] = df['Price / share'].astype(float)

    # Keep only those columns that are needed
    df = df[['Action', 'Time', 'ISIN', 'No. of shares', 'Price / share']]

    # Load the merge/split events and include them in the main data
    if args.merge_split_events:
        merge_split_events = pd.read_json(args.merge_split_events, lines=True)
        merge_split_events['Time'] = pd.to_datetime(merge_split_events['Time'])

        # Rename columns to match the main data
        merge_split_events.rename(columns={'Ratio': 'No. of shares'}, inplace=True)
        # Add a dummy to match the main data
        merge_split_events['Price / share'] = None  

        df = pd.concat([df, merge_split_events], ignore_index=True)

    df = df.sort_values(by='Time')

    profit = calculate_profit(df)
    tax = max(0, profit * TAX_RATE)

    profit_loss_output = f'Profit: {profit:.6f} PLN.' if profit >= 0 else f'Loss: {profit:.6f} PLN.'
    print(profit_loss_output + f' Tax to be paid: {tax:.6f} PLN.')