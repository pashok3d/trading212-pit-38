# Stock Trading Tax Calculator 
Script to generate tax report for pit-38 based on transactions from Trading212 (Poland)

**Motivation**: It is not that straighforward to pay taxes for dividends and income from sold stocks in Trading212 app, especially when the chosen currency is EUR, but not PLN. The most painfull part is that you can't just use calulcated numbers from annual report from Trading212, because you need to convert partial incomes from EUR/USD to PLN using exchange rate at the moment of asset sale. While there is a paid tool https://kalkulatorgieldowy.pl that can calculate required numbers for your pit-38 declaration, I was not even able to use kalkulatorgieldowy - I found it so frustrating to see different errors when trying to upload statements from the app. Eventually, I gave up on using kalkulatorgieldowy and decided to make my own script. 

**DISCLAIMER**: I am not a tax advisor, and this script is not tax advice. This tool is specifically designed for Polish tax regulations and may not be applicable in other jurisdictions. 

The script is provided "as is", without warranty of any kind, express or implied. I am not responsible for any mistakes, errors, or inaccuracies in the script or for any damages resulting from its use.

Tax laws change frequently, and this script may not reflect the most current regulations. You are responsible for verifying all calculations before submitting any tax documents. This script does not replace professional tax software or advice.

Please consult with a qualified tax advisor before using the results of this script for your tax declaration.

## Basic Usage

To calculate taxes for all transactions in a CSV file:

```bash
python main.py --csv path/to/your/transactions.csv
```

or directory with CSV files:

```bash
python main.py --csv trading_212_exports/ --merge_split splits.jsonl
```

## Handling Stock Splits and Merges

### Creating a Splits/Merges File

Create a JSONL file (each line is a valid JSON object) with your split/merge events:

```json
{"Action": "Split", "Ticker": "TSLA", "Name": "Tesla Inc", "Time": "2022-08-25", "Ratio": 3, "Currency (Price / share)": "USD", "Currency (Total)": "USD", "Total": 0}
{"Action": "Split", "Ticker": "AMZN", "Name": "Amazon", "Time": "2022-06-03", "Ratio": 20, "Currency (Price / share)": "USD", "Currency (Total)": "USD", "Total": 0}
{"Action": "Split", "Ticker": "NGAS", "Name": "WisdomTree Natural Gas", "Time": "2023-10-31", "Ratio": 0.00056078, "Currency (Price / share)": "USD", "Currency (Total)": "USD", "Total": 0}
```

**Important Note About Split Ratios**: 
- For forward splits (1 share becomes more than 1 share), use the multiplier as the ratio (e.g., 3 for a 3:1 split)
- For reverse splits (multiple shares become 1 share), use a decimal ratio (e.g., 0.1 for a 10:1 reverse split)

### Using the Splits/Merges File

```bash
python main.py --csv path/to/your/transactions.csv --merge_split path/to/splits.jsonl
```

## Understanding the Output

The program will generate a detailed tax report file named `tax_report.txt`

The tax report includes:
- Total capital gains/losses
- Dividend and interest income
- Tax amount (at 19% rate, according to Polish tax law)
- Profit/loss summary by ticker
- Detailed breakdown of all sell transactions with matching buy transactions (FIFO)
- Current holdings (unsold shares)

## Troubleshooting

### Common Errors

1. **"Not enough shares to sell"**: This typically happens when there's a split that wasn't accounted for. Add the missing split to your splits.jsonl file.

2. **"No CSV files found"**: Verify the path to your CSV files and ensure they have a .csv extension.

### CSV Format Requirements

The program expects CSV files with the following columns:
- Action (e.g., "Market buy", "Market sell", "Dividend", etc.)
- Time (transaction datetime)
- Ticker (stock symbol)
- No. of shares (quantity)
- Price / share
- Currency (Price / share)
- Total (total amount)
- Currency (Total)
