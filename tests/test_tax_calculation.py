import os
from unittest import mock

import pytest

import main
from main import calculate_tax


# Define a simple mock exchange rate
def mock_get_exchange_rate(currency, time):
    """Return a fixed exchange rate for testing"""
    rates = {"EUR": 4.5, "PLN": 1.0, "USD": 3.8}
    return rates.get(currency, 1.0)


def test_basic_profit_calculation():
    """Test a simple buy-sell scenario with known expected profit"""

    test_csv = "tests/test_data.csv"

    # Mock the exchange rate function
    with mock.patch.object(
        main, "get_exchange_rate", side_effect=mock_get_exchange_rate
    ):
        # Run the calculator
        result = calculate_tax(test_csv)

    # Buy: 10 shares × 100 EUR/share × 4.5 PLN/EUR = 4,500 PLN
    # Sell: 10 shares × 120 EUR/share × 4.5 PLN/EUR = 5,400 PLN
    # Expected profit: 5,400 - 4,500 = 900 PLN
    expected_profit = 900.0

    # Check if the calculated profit matches our expected profit
    assert result["total_profit"] == pytest.approx(expected_profit, abs=0.01)

    # Check if the tax amount is 19% of the profit
    expected_tax = expected_profit * 0.19
    assert result["tax_amount"] == pytest.approx(expected_tax, abs=0.01)


def test_tesla_stock_split():
    """Test that Tesla stock split is handled correctly"""

    csv_file = (
        "tests/test_data_split.csv"  # Path to the CSV file with Tesla transactions
    )

    split_file = "tests/example_merges_splits.jsonl"  # Path to the CSV file with split information

    # Mock the exchange rate function
    with mock.patch.object(
        main, "get_exchange_rate", side_effect=mock_get_exchange_rate
    ):
        # Process with the split information
        result = calculate_tax(csv_file, merge_split_file=split_file)

    # Calculate expected values
    # Before split: 2 shares at $300 each = $600 total (2,280 PLN at 3.8 PLN/USD)
    # After split (3:1): 6 shares at $100 each = $600 total
    # Sold 3 shares at $105 each = $315 total (1,197 PLN at 3.8 PLN/USD)
    # Cost basis for 3 of the 6 shares = $300 (1,140 PLN)
    # Profit = 1,197 PLN - 1,140 PLN = 57 PLN

    # Manually calculated expected profit - accounting for the split
    initial_purchase_pln = (
        2 * 300 * 3.8
    )  # 2 shares * $300/share * 3.8 PLN/USD = 2,280 PLN
    per_share_cost_pln = (
        initial_purchase_pln / 6
    )  # After 3:1 split, cost basis is spread across 6 shares
    sold_shares_cost_pln = 3 * per_share_cost_pln  # Cost basis for the 3 shares sold
    sold_shares_revenue_pln = (
        3 * 105 * 3.8
    )  # 3 shares * $105/share * 3.8 PLN/USD = 1,197 PLN
    expected_profit = sold_shares_revenue_pln - sold_shares_cost_pln
    expected_tax = expected_profit * 0.19

    # Assertions
    assert len(result["transactions"]) == 1, "Should have one sell transaction"

    # Get the transaction and check details
    transaction = result["transactions"][0]
    assert transaction["ticker"] == "TSLA"
    assert transaction["shares"] == 3.0
    assert transaction["sell_price"] == 105.0

    # Check profit matches expected
    assert transaction["profit_pln"] == pytest.approx(expected_profit, abs=0.5)
    assert result["total_profit"] == pytest.approx(expected_profit, abs=0.5)
    assert result["tax_amount"] == pytest.approx(expected_tax, abs=0.5)

    # Check that we still have 3 shares remaining in holdings (6 after split - 3 sold)
    assert "TSLA" in result["current_holdings"]
    total_remaining_shares = sum(
        holding["shares"] for holding in result["current_holdings"]["TSLA"]
    )
    assert total_remaining_shares == pytest.approx(3.0, abs=0.01)
