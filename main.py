import argparse
import pandas as pd
from collections import deque
from datetime import timedelta
import requests
import arrow
import sys

TAX_RATE = 0.19

NON_WORKING_DAYS = [
    "2023-06-08",
    "2023-08-15",
    "2023-11-01",
    "2023-12-23",
    "2023-12-24",
    "2023-12-25",
    "2023-12-26",
    "2023-12-30",
    "2023-12-31",
    "2024-01-01",
]


def get_eur_pln_rate(time: pd.Timestamp) -> float:
    """
    Get the exchange rate of EUR to PLN from NBP API for a given date

    Raises:
        Exception: If the API request fails
    """
    day_before = arrow.get(time).shift(days=-1)

    while day_before.strftime("%Y-%m-%d") in NON_WORKING_DAYS:
        # Skip the weekends and holidays
        day_before = day_before.shift(days=-1)

    if day_before.isoweekday() in [6, 7]:
        if day_before.isoweekday() == 6:
            day_before = day_before.shift(days=-1)
        elif day_before.isoweekday() == 7:
            day_before = day_before.shift(days=-2)

    url = f"http://api.nbp.pl/api/exchangerates/rates/a/eur/{day_before.strftime('%Y-%m-%d')}/?format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        price = data["rates"][0]["mid"]
        return price
    else:
        raise Exception(
            f"Failed to fetch EUR-PLN exchange rate from NBP API. Status code: {response.status_code}"
        )


def calculate_profit(df):
    stocks = {}
    total_profit = 0
    total_dividend = 0
    total_interest = 0

    for _, row in df.iterrows():
        operation = row.to_dict()
        action, time, id, no_of_shares, price_per_share, total = (
            operation["Action"],
            operation["Time"],
            operation["Ticker"],
            operation["No. of shares"],
            operation["Price / share"],
            operation["Total"],
        )

        if action == "Market buy":
            if id not in stocks:
                stocks[id] = deque()
            # Append the number of shares, price per share, and time to the deque of the stock
            stocks[id].append((no_of_shares, price_per_share, time))

        elif action == "Market sell":
            sell_value_pln = no_of_shares * price_per_share * get_eur_pln_rate(time)
            cost_value_pln = 0

            while no_of_shares > sys.float_info.epsilon:
                try:
                    # Get the leftmost buy operation from the deque to follow FIFO rule in tax calculation
                    buy_no_of_shares, buy_price_per_share, buy_time = stocks[id][0]
                except IndexError:
                    raise Exception(
                        f"Number of shares to sell can't be greater than the number of shares bought. Ticker: {id}, Date: {time}. Make sure that: 1. all operations of action 'Market buy' for {id} are included in data, 2. Required merge and split events are provided for {id}."
                    )
                except KeyError:
                    raise Exception(
                        f"Sell action can't be executed without preceding buy action. Ticker: {id}, Date: {time}. Make sure all operations of action 'Market buy' for {id} are included in data."
                    )

                if buy_no_of_shares <= no_of_shares:
                    # Leftmost buy order is completely consumed by the sell order
                    cost_value_pln += (
                        buy_no_of_shares
                        * buy_price_per_share
                        * get_eur_pln_rate(buy_time)
                    )
                    # Subtract leftmost buy order from sell order
                    no_of_shares -= buy_no_of_shares
                    # Remove leftmost buy order from the deque
                    stocks[id].popleft()
                else:
                    # Leftmost buy order is partially consumed by the sell order
                    cost_value_pln += (
                        no_of_shares * buy_price_per_share * get_eur_pln_rate(buy_time)
                    )
                    # Update number of shares in the leftmost buy order
                    stocks[id][0] = (
                        buy_no_of_shares - no_of_shares,
                        buy_price_per_share,
                        buy_time,
                    )
                    break

            profit = sell_value_pln - cost_value_pln
            total_profit += profit

        elif action == "Split" and id in stocks:
            # Multiply the number of shares and divide the price by ratio
            for i in range(len(stocks[id])):
                stocks[id][i] = (
                    stocks[id][i][0] / no_of_shares,
                    stocks[id][i][1] * no_of_shares,
                    stocks[id][i][2],
                )

        elif action == "Merge" and id in stocks:
            # Divide the number of shares and multiply the price by ratio
            for i in range(len(stocks[id])):
                stocks[id][i] = (
                    stocks[id][i][0] * no_of_shares,
                    stocks[id][i][1] / no_of_shares,
                    stocks[id][i][2],
                )
        elif action.startswith("Interest"):
            total_interest += total * get_eur_pln_rate(time)
        elif action.startswith("Dividend"):
            total_dividend = total * get_eur_pln_rate(time)

    return total_profit, total_dividend, total_interest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to the data file exported from trading212 in csv format",
    )
    parser.add_argument(
        "--merge_split_events",
        type=str,
        help="Path to the merge/split events of the stocks in jsonl format",
    )
    args = parser.parse_args()

    # Load the data
    df = pd.read_csv(args.data)

    # Remove duplicates
    df.drop_duplicates(subset=["ID"], inplace=True)

    # Load the merge/split events and include them in the main data
    if args.merge_split_events:
        merge_split_events = pd.read_json(args.merge_split_events, lines=True)

        # Rename columns to match the main data
        merge_split_events.rename(columns={"Ratio": "No. of shares"}, inplace=True)
        # Add a dummy to match the main data
        merge_split_events["Price / share"] = None

        df = pd.concat([df, merge_split_events], ignore_index=True)

    # Convert the time column to datetime and sort the values
    df["Time"] = pd.to_datetime(df["Time"], format="ISO8601")
    df.sort_values("Time", inplace=True)

    total_profit, total_dividend, total_interest = calculate_profit(df)
    tax = max(0, (total_profit + total_dividend + total_interest) * TAX_RATE)

    profit_loss_output = (
        f"Profit: {total_profit:.6f} PLN."
        if total_profit >= 0
        else f"Loss: {total_profit:.6f} PLN."
    )
    dividend_output = f" Dividend: {total_dividend:.6f} PLN."
    interest_output = f" Interest: {total_interest:.6f} PLN."
    print(
        profit_loss_output
        + dividend_output
        + interest_output
        + f" Tax to be paid: {tax:.6f} PLN."
    )
