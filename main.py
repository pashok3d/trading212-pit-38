import argparse
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
    currency: Literal["PLN", "EUR", "GBP"], time: pd.Timestamp
) -> float:
    """
    Get the exchange rate for a given currency to PLN on the day before the transaction

    Raises:
        Exception: If the API request fails
    """
    if currency == "PLN":
        return 1.0

    day_before = arrow.get(time).shift(days=-1)

    # Skip non-working holidays
    while day_before.strftime("%Y-%m-%d") in NON_WORKING_DAYS:
        day_before = day_before.shift(days=-1)

    # Skip weekends
    if day_before.isoweekday() in [6, 7]:
        if day_before.isoweekday() == 6:
            day_before = day_before.shift(days=-1)
        elif day_before.isoweekday() == 7:
            day_before = day_before.shift(days=-2)

    url = f"http://api.nbp.pl/api/exchangerates/rates/a/eur/{day_before.strftime('%Y-%m-%d')}/?format=json"
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


def calculate_tax(csv_file, year=None, merge_split_file=None):
    """
    Calculate tax based on the trading activity in the CSV file
    using FIFO method as required by Polish tax law
    """
    # Read the CSV file
    logger.info(f"Reading transactions from {csv_file}...")
    df = pd.read_csv(csv_file)

    # Convert the time column to datetime
    df["Time"] = pd.to_datetime(df["Time"])

    # Filter transactions for the specified year if provided
    if year:
        df = df[df["Time"].dt.year == year]
        logger.info(f"Found {len(df)} transactions for {year}")

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

    # Track totals
    total_profit = 0
    total_dividend = 0
    total_interest = 0

    # Process transactions in chronological order
    for _, row in df.iterrows():
        action = row["Action"]
        ticker = row["Ticker"]
        name = row.get("Name", ticker)  # Use ticker as fallback if name not present
        transaction_time = row["Time"]

        try:
            shares = float(row["No. of shares"])
            price_per_share = (
                float(row["Price / share"]) if pd.notna(row["Price / share"]) else 0
            )
            currency = row["Currency (Price / share)"]
            total_amount = float(row["Total"]) if pd.notna(row["Total"]) else 0

            # Skip if necessary fields are missing
            if pd.isna(currency) and action in ["Market buy", "Market sell"]:
                raise ValueError("Missing currency")

            # Get exchange rate for the transaction date for relevant currencies
            exchange_rate_to_pln = get_exchange_rate(currency, transaction_time)

            # Handle different types of actions
            if action == "Market buy":
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
                remaining_shares = shares
                total_cost_pln = 0
                matching_buys = []

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
                total_profit += profit_pln
                profit_by_ticker[ticker] += profit_pln

                # Record the sell transaction with profit information
                sell_transactions.append(
                    {
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
                )

                logger.info(
                    f"Processed sale of {shares} {ticker} with profit/loss: {profit_pln:.2f} PLN"
                )

            elif action == "Split" and ticker in buy_queues:
                # For a split, multiply shares and divide price by ratio
                for i in range(len(buy_queues[ticker])):
                    buy = buy_queues[ticker][i]
                    # Update shares and price while keeping the product the same
                    new_shares = (
                        buy["shares"] / shares if shares != 0 else buy["shares"]
                    )
                    new_price = (
                        buy["price_per_share"] * shares
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
                dividend_pln = total_amount * exchange_rate_to_pln
                total_dividend += dividend_pln
                logger.info(f"Processed dividend for {ticker}: {dividend_pln:.2f} PLN")

            elif action.startswith("Interest"):
                # Process interest income
                interest_pln = total_amount * exchange_rate_to_pln
                total_interest += interest_pln
                logger.info(f"Processed interest: {interest_pln:.2f} PLN")

        except Exception as e:
            raise Exception(
                f"Failed to process transaction for {ticker} ({name}) on {transaction_time}: {e}"
            ) from e

    # Calculate tax amount (19% on positive profit only)
    taxable_income = (
        total_profit + total_dividend + total_interest
    )  # Including dividends and interest
    tax_amount = max(0, taxable_income * TAX_RATE)

    # Prepare results
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

    logger.info(f"\nSummary:")
    logger.info(f"Total Capital Gain/Loss: {total_profit:.2f} PLN")
    if total_dividend > 0:
        logger.info(f"Total Dividends: {total_dividend:.2f} PLN")
    if total_interest > 0:
        logger.info(f"Total Interest: {total_interest:.2f} PLN")
    logger.info(f"Total Taxable Income: {taxable_income:.2f} PLN")
    logger.info(f"Tax Amount (19%): {tax_amount:.2f} PLN")

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
        help="CSV file with transaction data from Trading212",
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
        # Mock the exchange rate function for testing (to avoid API calls)
        if args.test:

            def mock_get_exchange_rate(currency, time):
                # Return mock exchange rates for testing
                if currency == "EUR":
                    return 4.3
                elif currency == "USD":
                    return 3.9
                elif currency == "GBP":
                    return 5.0
                elif currency == "GBX":
                    return 0.05
                else:
                    return 1.0

            # Save original function and replace with mock
            original_get_exchange_rate = get_exchange_rate
            get_exchange_rate = mock_get_exchange_rate
            logger.info("Using mock exchange rates for testing")

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
