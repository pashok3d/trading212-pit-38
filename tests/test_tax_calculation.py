from unittest import mock
import pytest

import main
from main import calculate_tax


# Define a simple mock exchange rate
def mock_get_exchange_rate(currency, time):
    """Return a fixed exchange rate for testing"""
    rates = {"EUR": 4.5, "PLN": 1.0}
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
