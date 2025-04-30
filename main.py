import argparse
import glob
import os
import sys
from collections import defaultdict, deque
from functools import lru_cache
from typing import Literal

import arrow
import pandas as pd
import requests
from loguru import logger

# Tax rate in Poland
TAX_RATE = 0.19

# Known non-working days in Poland (holidays) for 2024
NON_WORKING_DAYS = [
    "2021-01-01",  # Nowy Rok, Świętej Bożej Rodzicielki Maryi (New Year's Day)
    "2021-01-06",  # Trzech Króli (Epiphany)
    "2021-04-04",  # Wielkanoc (Easter Sunday)
    "2021-04-05",  # Poniedziałek Wielkanocny (Easter Monday)
    "2021-05-01",  # Święto Pracy (Labor Day)
    "2021-05-03",  # Święto Konstytucji 3 Maja (Constitution Day)
    "2021-05-23",  # Zesłanie Ducha Świętego (Pentecost Sunday)
    "2021-06-03",  # Boże Ciało (Corpus Christi)
    "2021-08-15",  # Święto Wojska Polskiego, Wniebowzięcie Najświętszej Maryi Panny (Polish Army Day, Assumption of Mary)
    "2021-11-01",  # Wszystkich Świętych (All Saints' Day)
    "2021-11-11",  # Święto Niepodległości (Independence Day)
    "2021-12-25",  # Boże Narodzenie (pierwszy dzień) (Christmas Day)
    "2021-12-26",  # Boże Narodzenie (drugi dzień) (Second Day of Christmas)
    "2022-01-01",  # Nowy Rok, Świętej Bożej Rodzicielki Maryi (New Year's Day)
    "2022-01-06",  # Trzech Króli (Epiphany)
    "2022-04-17",  # Wielkanoc (Easter Sunday)
    "2022-04-18",  # Poniedziałek Wielkanocny (Easter Monday)
    "2022-05-01",  # Święto Pracy (Labor Day)
    "2022-05-03",  # Święto Konstytucji 3 Maja (Constitution Day)
    "2022-06-05",  # Zesłanie Ducha Świętego (Pentecost Sunday)
    "2022-06-16",  # Boże Ciało (Corpus Christi)
    "2022-08-15",  # Święto Wojska Polskiego, Wniebowzięcie Najświętszej Maryi Panny (Polish Army Day, Assumption of Mary)
    "2022-11-01",  # Wszystkich Świętych (All Saints' Day)
    "2022-11-11",  # Święto Niepodległości (Independence Day)
    "2022-12-25",  # Boże Narodzenie (pierwszy dzień) (Christmas Day)
    "2022-12-26",  # Boże Narodzenie (drugi dzień) (Second Day of Christmas)
    "2023-01-01",  # Nowy Rok (New Year's Day)
    "2023-01-06",  # Święto Trzech Króli (Epiphany)
    "2023-04-09",  # pierwszy dzień Wielkiej Nocy (Easter Sunday)
    "2023-04-10",  # drugi dzień Wielkiej Nocy (Easter Monday)
    "2023-05-01",  # Święto Państwowe (Labor Day)
    "2023-05-03",  # Święto Narodowe Trzeciego Maja (Constitution Day)
    "2023-05-28",  # Zielone Świątki (Pentecost Sunday)
    "2023-06-08",  # Boże Ciało (Corpus Christi)
    "2023-08-15",  # Wniebowzięcie Najświętszej Maryi Panny (Assumption of Mary)
    "2023-11-01",  # Wszystkich Świętych (All Saints' Day)
    "2023-11-11",  # Narodowe Święto Niepodległości (Independence Day)
    "2023-12-25",  # pierwszy dzień Bożego Narodzenia (Christmas Day)
    "2023-12-26",  # drugi dzień Bożego Narodzenia (Second Day of Christmas)
    "2024-01-01",  # Nowy Rok, Świętej Bożej Rodzicielki Maryi
    "2024-01-06",  # Trzech Króli (Objawienie Pańskie)
    "2024-03-31",  # Wielkanoc
    "2024-04-01",  # Poniedziałek Wielkanocny
    "2024-05-01",  # Święto Pracy
    "2024-05-03",  # Święto Konstytucji 3 Maja
    "2024-05-19",  # Zesłanie Ducha Świętego (Zielone Świątki)
    "2024-05-30",  # Boże Ciało
    "2024-08-15",  # Święto Wojska Polskiego, Wniebowzięcie Najświętszej Maryi Panny
    "2024-11-01",  # Wszystkich Świętych
    "2024-11-11",  # Święto Niepodległości
    "2024-12-25",  # Boże Narodzenie (pierwszy dzień)
    "2024-12-26",  # Boże Narodzenie (drugi dzień)
]


@lru_cache
def get_exchange_rate(
    currency: Literal["PLN", "EUR", "GBP", "GBX"], time: pd.Timestamp
) -> float:
    """
    Get the exchange rate for a given currency to PLN on the day before the transaction

    Raises:
        Exception: If the API request fails
    """
    if currency == "PLN":
        return 1.0

    if currency == "GBX":
        # Get GBP rate and divide by 100
        gbp_rate = get_exchange_rate("GBP", time)
        return gbp_rate / 100.0

    day_before = arrow.get(time).shift(days=-1)

    # Skip non-working holidays and weekends
    while day_before.strftime(
        "%Y-%m-%d"
    ) in NON_WORKING_DAYS or day_before.isoweekday() in [6, 7]:
        day_before = day_before.shift(days=-1)

    url = f"http://api.nbp.pl/api/exchangerates/rates/a/{currency}/{day_before.strftime('%Y-%m-%d')}/?format=json"
    response = requests.get(url)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise Exception(
            f"Failed to fetch {currency}-PLN exchange rate from NBP API. Status code: {response.status_code}"
        ) from e
    else:
        data = response.json()
        price = data["rates"][0]["mid"]
        return price


def load_csv_files(path: str) -> pd.DataFrame:
    """
    Load and merge CSV files from a directory or a single CSV file

    Args:
        path: Path to a CSV file or directory containing CSV files

    Returns:
        DataFrame with merged transaction data

    Raises:
        Exception: If no CSV files are found or if there are issues loading the files
    """
    if os.path.isdir(path):
        # If path is a directory, find all CSV files
        csv_files = glob.glob(os.path.join(path, "*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in directory: {path}")

        logger.info(f"Found {len(csv_files)} CSV files in {path}")

        # Create an empty list to store dataframes
        dfs = []

        # Load each CSV file and append to list
        for csv_file in csv_files:
            try:
                logger.info(f"Reading transactions from {csv_file}...")
                df = pd.read_csv(csv_file)
                dfs.append(df)
                logger.info(
                    f"Loaded {len(df)} transactions from {os.path.basename(csv_file)}"
                )
            except Exception as e:
                logger.error(f"Error loading {csv_file}: {e}")
                raise Exception(f"Failed to load CSV file {csv_file}: {e}") from e

        # Merge all dataframes
        merged_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Total transactions after merging: {len(merged_df)}")

        return merged_df

    elif os.path.isfile(path):
        # If path is a single CSV file
        try:
            logger.info(f"Reading transactions from {path}...")
            df = pd.read_csv(path)
            logger.info(f"Loaded {len(df)} transactions")
            return df
        except Exception as e:
            raise Exception(f"Failed to load CSV file {path}: {e}") from e

    else:
        raise FileNotFoundError(
            f"Invalid path: {path}. Must be a CSV file or a directory containing CSV files."
        )


def calculate_tax(csv_path, year=None, merge_split_file=None):
    """
    Calculate tax based on the trading activity in the CSV files
    using FIFO method as required by Polish tax law

    Args:
        csv_path: Path to a CSV file or directory containing CSV files
        year: Optional year to filter taxable events (sell transactions, dividends, interest)
              Note: All buy transactions are processed regardless of year to maintain FIFO
        merge_split_file: Optional path to file with merge/split events
    """
    # Read the CSV file
    logger.info(f"Reading transactions from {csv_path}...")
    df = load_csv_files(csv_path)

    # Convert the time column to datetime
    df["Time"] = pd.to_datetime(df["Time"], format="mixed")

    # Remove duplicates if they exist
    df.drop_duplicates(subset=["ID"], inplace=True)

    # Load merge/split events if provided
    if merge_split_file:
        try:
            merge_split_events = pd.read_json(merge_split_file, lines=True)

            # Convert the time column to datetime
            merge_split_events["Time"] = pd.to_datetime(merge_split_events["Time"])

            # Rename columns to match the main data
            merge_split_events.rename(columns={"Ratio": "No. of shares"}, inplace=True)
            # Add dummy fields to match the main data schema
            merge_split_events["Price / share"] = None

            # Combine with main data
            df = pd.concat([df, merge_split_events], ignore_index=True)
            logger.info(f"Added merge/split events from {merge_split_file}")
        except Exception as e:
            raise Exception(f"Failed to read merge/split events: {e}") from e

    # Sort by time for chronological processing
    df.sort_values("Time", inplace=True)

    # Dictionary to store buy transactions using deque for FIFO
    buy_queues = defaultdict(deque)

    # List to store processed sell transactions with calculated profit
    sell_transactions = []

    # Dictionary to track profit by ticker
    profit_by_ticker = defaultdict(float)

    # Track totals by year
    yearly_profit = defaultdict(float)
    yearly_dividend = defaultdict(float)
    yearly_interest = defaultdict(float)
    yearly_sell_transactions = defaultdict(list)
    yearly_profit_by_ticker = defaultdict(lambda: defaultdict(float))

    # Process transactions in chronological order
    for _, row in df.iterrows():
        action = row["Action"]
        ticker = row["Ticker"]
        name = row.get("Name", ticker)  # Use ticker as fallback if name not present
        transaction_time = row["Time"]
        transaction_year = transaction_time.year

        try:
            shares = float(row["No. of shares"])
            price_per_share = (
                float(row["Price / share"]) if pd.notna(row["Price / share"]) else 0
            )
            currency = row["Currency (Price / share)"]
            currency_total = row["Currency (Total)"]
            total_amount = float(row["Total"]) if pd.notna(row["Total"]) else 0

            # Skip if necessary fields are missing
            if pd.isna(currency) and action in ["Market buy", "Market sell"]:
                raise ValueError("Missing currency")

            # Handle different types of actions
            if action == "Market buy":
                exchange_rate_to_pln = get_exchange_rate(currency, transaction_time)

                # Add buy transaction to the queue
                buy_queues[ticker].append(
                    {
                        "time": transaction_time,
                        "shares": shares,
                        "price_per_share": price_per_share,
                        "price_pln": price_per_share * exchange_rate_to_pln,
                        "currency": currency,
                        "exchange_rate": exchange_rate_to_pln,
                    }
                )

            elif action == "Market sell":

                if ticker == "TSLA" and transaction_time == pd.Timestamp(
                    "2023-09-15 14:46:41"
                ):
                    pass
                remaining_shares = shares
                total_cost_pln = 0
                matching_buys = []

                exchange_rate_to_pln = get_exchange_rate(currency, transaction_time)

                # Calculate sell price in PLN
                sell_price_pln = price_per_share * exchange_rate_to_pln
                total_sell_pln = shares * sell_price_pln

                # Follow FIFO principle to match buy transactions
                while (
                    remaining_shares > sys.float_info.epsilon
                ):  # Use epsilon to handle floating point precision
                    try:
                        # Get the leftmost buy operation from the queue
                        oldest_buy = buy_queues[ticker][0]
                    except IndexError as e:
                        raise Exception(
                            f"Not enough shares to sell. Attempting to sell {remaining_shares} more shares than available. "
                            "Make sure all prior buy transactions are included in the data."
                        ) from e

                    used_shares = min(remaining_shares, oldest_buy["shares"])

                    matching_buys.append(
                        {
                            "buy_time": oldest_buy["time"],
                            "shares": used_shares,
                            "buy_price": oldest_buy["price_per_share"],
                            "buy_price_pln": oldest_buy["price_pln"],
                            "currency": oldest_buy["currency"],
                            "exchange_rate": oldest_buy["exchange_rate"],
                        }
                    )

                    # Calculate cost in PLN for the portion being sold
                    portion_cost_pln = used_shares * oldest_buy["price_pln"]
                    total_cost_pln += portion_cost_pln

                    remaining_shares -= used_shares

                    if abs(used_shares - oldest_buy["shares"]) < sys.float_info.epsilon:
                        # If we used all shares from this buy order, remove it
                        buy_queues[ticker].popleft()
                    else:
                        # Otherwise, update the shares count in the buy order
                        buy_queues[ticker][0]["shares"] -= used_shares

                # Calculate profit in PLN
                profit_pln = total_sell_pln - total_cost_pln

                # Store the sell transaction with profit information
                sell_record = {
                    "ticker": ticker,
                    "name": name,
                    "sell_time": transaction_time,
                    "shares": shares,
                    "sell_price": price_per_share,
                    "sell_currency": currency,
                    "sell_price_pln": sell_price_pln,
                    "sell_total_pln": total_sell_pln,
                    "cost_basis_pln": total_cost_pln,
                    "profit_pln": profit_pln,
                    "exchange_rate": exchange_rate_to_pln,
                    "matching_buys": matching_buys,
                }

                # Add to total and yearly records
                yearly_profit[transaction_year] += profit_pln
                yearly_sell_transactions[transaction_year].append(sell_record)
                yearly_profit_by_ticker[transaction_year][ticker] += profit_pln

                sell_transactions.append(sell_record)
                profit_by_ticker[ticker] += profit_pln

                logger.info(
                    f"Processed sale of {shares} {ticker} with profit/loss: {profit_pln:.2f} PLN"
                )

            elif action == "Split":
                if ticker in buy_queues:
                    # For a split, multiply shares and divide price by ratio
                    for i in range(len(buy_queues[ticker])):
                        buy = buy_queues[ticker][i]
                        # Update shares and price while keeping the product the same
                        new_shares = (
                            buy["shares"] * shares if shares != 0 else buy["shares"]
                        )
                        new_price = (
                            buy["price_per_share"] / shares
                            if shares != 0
                            else buy["price_per_share"]
                        )
                        new_price_pln = new_price * buy["exchange_rate"]

                        buy_queues[ticker][i] = {
                            "time": buy["time"],
                            "shares": new_shares,
                            "price_per_share": new_price,
                            "price_pln": new_price_pln,
                            "currency": buy["currency"],
                            "exchange_rate": buy["exchange_rate"],
                        }

                    logger.info(f"Processed split for {ticker} with ratio {shares}")
                else:
                    logger.warning(
                        f"Split event for {ticker} with ratio {shares} but no matching buy transactions found."
                    )

            elif action == "Merge" and ticker in buy_queues:
                # For a merge, divide shares and multiply price by ratio
                for i in range(len(buy_queues[ticker])):
                    buy = buy_queues[ticker][i]
                    # Update shares and price while keeping the product the same
                    new_shares = (
                        buy["shares"] * shares if shares != 0 else buy["shares"]
                    )
                    new_price = (
                        buy["price_per_share"] / shares
                        if shares != 0
                        else buy["price_per_share"]
                    )
                    new_price_pln = new_price * buy["exchange_rate"]

                    buy_queues[ticker][i] = {
                        "time": buy["time"],
                        "shares": new_shares,
                        "price_per_share": new_price,
                        "price_pln": new_price_pln,
                        "currency": buy["currency"],
                        "exchange_rate": buy["exchange_rate"],
                    }

                logger.info(f"Processed merge for {ticker} with ratio {shares}")

            elif action.startswith("Dividend"):
                # Process dividend income
                exchange_rate_to_pln = get_exchange_rate(currency, transaction_time)

                dividend_pln = total_amount * exchange_rate_to_pln
                yearly_dividend[transaction_year] += dividend_pln
                logger.info(f"Processed dividend for {ticker}: {dividend_pln:.2f} PLN")

            elif action.startswith("Interest"):

                if action == "Interest on cash":
                    exchange_rate_to_pln = get_exchange_rate(
                        currency_total, transaction_time
                    )
                else:
                    # Process interest income
                    exchange_rate_to_pln = get_exchange_rate(currency, transaction_time)

                interest_pln = total_amount * exchange_rate_to_pln
                yearly_interest[transaction_year] += interest_pln
                logger.info(f"Processed interest: {interest_pln:.2f} PLN")

            elif action.startswith("Lending"):
                # Process share lending interest income
                exchange_rate_to_pln = get_exchange_rate(
                    currency_total, transaction_time
                )

                lending_interest_pln = total_amount * exchange_rate_to_pln
                yearly_interest[transaction_year] += interest_pln
                logger.info(
                    f"Processed share lending interest: {lending_interest_pln:.2f} PLN"
                )

            elif action == "Deposit":
                pass

            else:
                logger.warning(
                    f"Unknown action '{action}' for {ticker} on {transaction_time}. Skipping."
                )

        except Exception as e:
            raise Exception(
                f"Failed to process transaction for {ticker} ({name}) on {transaction_time}: {e}"
            ) from e

    # Prepare results based on whether a specific year was requested
    if year:
        # Filter results for the specified year
        year_profit = yearly_profit.get(year, 0)
        year_dividend = yearly_dividend.get(year, 0)
        year_interest = yearly_interest.get(year, 0)
        year_transactions = yearly_sell_transactions.get(year, [])
        year_profit_by_ticker = yearly_profit_by_ticker.get(year, {})

        # Calculate tax amount (19% on positive profit only for the specified year)
        taxable_income = year_profit + year_dividend + year_interest
        tax_amount = max(0, taxable_income * TAX_RATE)

        logger.info(f"\nSummary for year {year}:")
        logger.info(f"Total Capital Gain/Loss: {year_profit:.2f} PLN")
        if year_dividend > 0:
            logger.info(f"Total Dividends: {year_dividend:.2f} PLN")
        if year_interest > 0:
            logger.info(f"Total Interest: {year_interest:.2f} PLN")
        logger.info(f"Total Taxable Income: {taxable_income:.2f} PLN")
        logger.info(f"Tax Amount (19%): {tax_amount:.2f} PLN")

        results = {
            "tax_amount": tax_amount,
            "total_profit": year_profit,
            "total_dividend": year_dividend,
            "total_interest": year_interest,
            "transactions": year_transactions,
            "profit_by_ticker": year_profit_by_ticker,
            "current_holdings": {
                ticker: list(queue) for ticker, queue in buy_queues.items() if queue
            },
        }
    else:
        # Calculate totals for all years
        total_profit = sum(yearly_profit.values())
        total_dividend = sum(yearly_dividend.values())
        total_interest = sum(yearly_interest.values())

        # Calculate tax amount (19% on positive profit only)
        taxable_income = total_profit + total_dividend + total_interest
        tax_amount = max(0, taxable_income * TAX_RATE)

        logger.info(f"\nSummary for all years:")
        logger.info(f"Total Capital Gain/Loss: {total_profit:.2f} PLN")
        if total_dividend > 0:
            logger.info(f"Total Dividends: {total_dividend:.2f} PLN")
        if total_interest > 0:
            logger.info(f"Total Interest: {total_interest:.2f} PLN")
        logger.info(f"Total Taxable Income: {taxable_income:.2f} PLN")
        logger.info(f"Tax Amount (19%): {tax_amount:.2f} PLN")

        results = {
            "tax_amount": tax_amount,
            "total_profit": total_profit,
            "total_dividend": total_dividend,
            "total_interest": total_interest,
            "transactions": sell_transactions,
            "profit_by_ticker": profit_by_ticker,
            "current_holdings": {
                ticker: list(queue) for ticker, queue in buy_queues.items() if queue
            },
        }

    return results


def generate_tax_report(result, year=None):
    """
    Generate a human-readable tax report based on calculation results
    """
    year_text = f" for Year {year}" if year else ""
    report = []
    report.append(f"Tax Report{year_text}")
    report.append("=" * 80)

    if not result["transactions"]:
        report.append("No sell transactions found for this period.")
        return "\n".join(report)

    # Format numbers with commas as thousands separators
    total_profit_formatted = f"{result['total_profit']:,.2f}"
    tax_amount_formatted = f"{result['tax_amount']:,.2f}"

    report.append(f"Total Capital Gain/Loss (PLN): {total_profit_formatted}")
    report.append(f"Total Dividends (PLN): {result['total_dividend']:.2f}")
    report.append(f"Total Interest (PLN): {result['total_interest']:.2f}")
    report.append(
        f"Total Taxable Income (PLN): {result['total_profit'] + result['total_dividend'] + result['total_interest']:.2f}"
    )
    report.append(f"Tax Amount (19%, PLN): {tax_amount_formatted}")
    report.append("")

    # Summary by ticker
    report.append("Profit/Loss Summary by Ticker:")
    report.append("-" * 80)
    for ticker, profit in sorted(
        result["profit_by_ticker"].items(), key=lambda x: abs(x[1]), reverse=True
    ):
        report.append(f"{ticker}: {profit:,.2f} PLN")

    report.append("")
    report.append("Detailed Sell Transactions:")
    report.append("-" * 80)

    for i, t in enumerate(result["transactions"], 1):
        report.append(f"{i}. {t['ticker']} - {t['name']}")
        report.append(f"   Sell Date: {t['sell_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"   Shares Sold: {t['shares']}")
        report.append(
            f"   Sell Price: {t['sell_price']:.4f} {t['sell_currency']}/share"
        )
        report.append(
            f"   Exchange Rate: 1 {t['sell_currency']} = {t['exchange_rate']:.4f} PLN"
        )
        report.append(f"   Sell Price (PLN): {t['sell_price_pln']:,.4f} PLN/share")
        report.append(f"   Sell Total (PLN): {t['sell_total_pln']:,.2f} PLN")
        report.append(f"   Cost Basis (PLN): {t['cost_basis_pln']:,.2f} PLN")
        report.append(f"   Profit/Loss (PLN): {t['profit_pln']:,.2f} PLN")
        report.append("")
        report.append("   Matching Buy Transactions (FIFO):")

        for j, buy in enumerate(t["matching_buys"], 1):
            report.append(
                f"      {j}. Buy Date: {buy['buy_time'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            report.append(f"         Shares: {buy['shares']}")
            report.append(
                f"         Buy Price: {buy['buy_price']:.4f} {buy['currency']}/share"
            )
            report.append(
                f"         Exchange Rate: 1 {buy['currency']} = {buy['exchange_rate']:.4f} PLN"
            )
            report.append(
                f"         Buy Price (PLN): {buy['buy_price_pln']:,.4f} PLN/share"
            )

        report.append("-" * 80)

    # Current holdings section
    report.append("")
    report.append("Current Holdings (Unsold Shares):")
    report.append("-" * 80)

    if not result["current_holdings"]:
        report.append("No unsold shares.")
    else:
        for ticker, buys in result["current_holdings"].items():
            total_shares = sum(buy["shares"] for buy in buys)
            report.append(f"{ticker}: {total_shares:,.6f} shares")
            for i, buy in enumerate(buys, 1):
                report.append(
                    f"   {i}. Buy Date: {buy['time'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
                report.append(f"      Shares: {buy['shares']}")
                report.append(
                    f"      Buy Price: {buy['price_per_share']:.4f} {buy['currency']}/share"
                )
                report.append(
                    f"      Buy Price (PLN): {buy['price_pln']:,.4f} PLN/share"
                )
            report.append("")

    return "\n".join(report)


# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate tax on stock trades for Polish tax reporting"
    )
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="CSV file or directory containing CSV files with transaction data",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Year to calculate taxes for (optional, defaults to all years)",
    )
    parser.add_argument(
        "--merge_split", type=str, help="JSONL file with merge/split events (optional)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use mock exchange rates instead of API calls (for testing)",
    )

    args = parser.parse_args()

    try:
        if os.path.isdir(args.csv):
            logger.info(f"Processing CSV files from directory: {args.csv}...")
        else:
            logger.info(f"Processing CSV file: {args.csv}...")

        year_str = f" for year {args.year}" if args.year else ""
        logger.info(f"Calculating tax{year_str}...")

        result = calculate_tax(args.csv, args.year, args.merge_split)
        report = generate_tax_report(result, args.year)

        # Save to file
        year_suffix = f"_{args.year}" if args.year else ""
        output_file = f"tax_report{year_suffix}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"\nDetailed report saved to {output_file}")

        # Display critical information in case of positive gains
        if result["tax_amount"] > 0:
            logger.info(f"TAX TO PAY: {result['tax_amount']:.2f} PLN")

    except Exception as e:
        logger.exception(e)
