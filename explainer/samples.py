"""Sample scripts so a new user can click one button and see the app work."""

SAMPLES = {
    "Tip calculator (very short)": '''bill = 84.50
people = 3
tip_percent = 18

tip = bill * (tip_percent / 100)
total = bill + tip
each = total / people

print(f"Tip: ${tip:.2f}")
print(f"Total: ${total:.2f}")
print(f"Each person pays: ${each:.2f}")
''',
    "Expense report (functions + loops)": '''import csv
from collections import defaultdict


def load_expenses(path):
    """Read a CSV file of expenses into a list of dictionaries."""
    rows = []
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            row["amount"] = float(row["amount"])
            rows.append(row)
    return rows


def total_by_category(expenses):
    totals = defaultdict(float)
    for expense in expenses:
        totals[expense["category"]] += expense["amount"]
    return dict(totals)


def flag_over_budget(totals, budget=500.0):
    over = []
    for category, amount in totals.items():
        if amount > budget:
            over.append((category, amount - budget))
    return over


def main():
    expenses = load_expenses("expenses.csv")
    totals = total_by_category(expenses)

    print(f"Loaded {len(expenses)} expenses")
    for category, amount in sorted(totals.items()):
        print(f"  {category}: ${amount:,.2f}")

    problems = flag_over_budget(totals)
    if problems:
        for category, excess in problems:
            print(f"OVER BUDGET: {category} by ${excess:,.2f}")
    else:
        print("Everything is within budget.")


if __name__ == "__main__":
    main()
''',
    "Web request + retry (classes)": '''import time
import urllib.request


class PriceChecker:
    def __init__(self, url, retries=3):
        self.url = url
        self.retries = retries
        self.history = []

    def fetch(self):
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(self.url, timeout=5) as response:
                    body = response.read().decode("utf-8")
                self.history.append(len(body))
                return body
            except Exception as error:
                wait = 2 ** attempt
                print(f"Attempt {attempt + 1} failed ({error}). Waiting {wait}s.")
                time.sleep(wait)
        raise RuntimeError("Could not reach the site after several tries.")


checker = PriceChecker("https://example.com")
page = checker.fetch()
print(f"Downloaded {len(page)} characters")
''',
}
