import os
import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# db = SQL("sqlite:///finance.db")
db = SQL("postgres://kymiimkbnzvoge:0bd5cbc822a45ed62c69aca7a8a68ed4ae4cf75b9244b0263e8ed1d54db94e08@ec2-54-156-85-145.compute-1.amazonaws.com:5432/d6ag3v9hksijr5")
# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    # Gets sum of all distinct shares of a ticker that user owns
    stocks_count = db.execute("SELECT SUM(shares) as num_shares, ticker, company_name FROM purchases WHERE id = ? GROUP BY ticker, company_name HAVING SUM(shares) > 0;", (session["user_id"])) # URGENT take out the ", company_name"
    print(stocks_count)

    # Variable for value of all stocks user owns
    total_stock_value = 0
    # Adds in price and total
    for stock in stocks_count:
        # Current stock price
        current = lookup(stock['ticker'])['price']
        stock['price'] = str(current)
        print(current)
        # Current total price of all shares
        total = float(stock['price']) * stock['num_shares']
        stock['total'] = usd(total)
        total_stock_value += total
        print(total)

    # Gets user's total cash to display
    user_cash = db.execute('SELECT cash FROM users WHERE id = ?', session["user_id"]) # (session["user_id"]) might not throw error
    cash = int(user_cash[0]['cash'])

    # Sets total to value of stocks + amount of cash
    total = usd(cash + total_stock_value)
    return render_template("portfolio.html", stocks_count = stocks_count, total = str(total), cash = usd(cash))



    """
    # Total stock value:
    value = 0

    # Gets all purchases that user made
    stocks = db.execute("SELECT * FROM purchases WHERE id = :id", id = session["user_id"])
    print(stocks)
    # Maps ticker with number of shares total
    tickers_indicies = {}

    iteration = 0
    # List of values to delete after
    deleting = []
    # Loops through purchases made by user
    for stock in stocks:
        # Changes stock price to current price, not bought at price
        price = lookup(stock['ticker'])['price']
        stock['price'] = str(price)

        # Adds the total (price * shares) to stock dictionary
        total = price * float(stock['shares'])
        stock['total'] = str(total)[0:6]

        # Combines purchases of same stock
        if stock['ticker'].upper() in tickers_indicies:
            tickers_indicies[stock['ticker'].upper()] += stock['shares']

            deleting.append(iteration)
        else:
            tickers_indicies[stock['ticker'].upper()] = stock['shares']

        iteration += 1

    # Adds the total number of shares per stock, and combines multiple purchases
    for i in range(0, len(stocks)):
        stocks[i]['shares'] = tickers_indicies[stocks[i]['ticker'].upper()]

    # Deletes duplicate rows
    stocks = [x for ind, x in enumerate(stocks) if ind not in deleting]

    # Deletes rows with 0 shares of stock
    for stock in range(0, len(stocks)):
        if stocks[stock]['shares'] == 0:
            del stocks[stock]
        else:
            value += float(stocks[stock]['total'])

    # Gets user's total cash to display
    user_cash = db.execute('SELECT cash FROM users WHERE id = ?', session["user_id"])
    cash = int(user_cash[0]['cash'])

    total = cash + value

    # Renders the portfolio template
    return render_template("portfolio.html", stocks = stocks, total = '$' + str(total), cash = '$' + str(cash)[0:6])
    """


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "GET":
        return render_template("buy.html")
    if request.method == "POST":
        ticker = request.form.get("ticker")
        quantity = request.form.get("quantity").replace(',', '')
        if not ticker or not lookup(ticker):
            return apology("Please enter a ticker symbol", 403)
        try:
            if int(quantity) < 1:
                return apology("Please enter a valid quantity", 403)
        except:
            return apology("Please enter a positive integer as the quantity", 403)

        looked_ticker = lookup(ticker)
        list_cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = list_cash[0]['cash']
        if cash - looked_ticker['price'] * int(quantity) >= 0:
            # Something with the square brackets below throws error.
            db.execute("INSERT INTO purchases (id, ticker, price, date, shares, company_name) VALUES (?,?,?,?,?,?)", session['user_id'], ticker.upper(), looked_ticker['price'], datetime.datetime.now(), quantity, looked_ticker['name'])
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - (looked_ticker['price'] * int(quantity)), session['user_id'])
            flash(f"You have bought {quantity} share{'s' if int(quantity) > 1 else ''} of {ticker.upper()}")
            return redirect("/")

        else:
            return apology("You don't have enough cash remaining")

@app.route("/history")
@login_required
def history():
    transactions = db.execute('SELECT * FROM purchases WHERE id = :id', id = session['user_id'])
    return render_template('history.html', transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/buy")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template('change_password.html')
    if request.method == "POST":
        new_password = request.form.get('new_password')
        entered_current_password = request.form.get('current_password')
        actual_password = db.execute('SELECT hash FROM users WHERE id = ?', session['user_id'])[0]['hash']

        # Checks that inputed password is user's actual password
        if not check_password_hash(actual_password, entered_current_password):
            return apology('Make sure your entered existing password matches your actual password', 403)
        # Makes sure the user inputs a new password
        if not new_password:
            return apology("Please provide a new password.", 403)
        # Checks that the new password equals the new password confirmation
        if request.form.get("confirmation") != new_password:
            return apology("Make sure the new password matches with the confirmation password.", 403)
        # Checks that the new password isn't the user's current password
        if new_password == entered_current_password:
            return apology("Please enter a different password to change to", 403)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_password), session['user_id'])
        flash("Your password has been changed")
        return redirect("/")
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    ticker = request.form.get("ticker")
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        if not ticker:
            return apology("Please type in a stock ticker.")
        else:
            try:
                looked = lookup(ticker)
                print("\n")
                print(looked)
                return render_template("quoted.html", name = looked["name"], symbol = looked["symbol"], price = looked["price"])
            except:
                pass
            try:
                looked = lookup(ticker)

                return render_template("quoted_crypto.html", symbol = looked["symbol"], price = looked["latestPrice"])
            except:
                return apology("Please enter a valid ticker symbol")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        starting_cash = request.form.get("cash").replace(',', '')
        if not name and not password:
            return apology("Please provide a name and a password.", 403)
        elif not name:
            return apology("Please provide a name.", 403)
        elif db.execute("SELECT username FROM users WHERE username = ?", name):
            return apology("That username is taken.")
        elif not password:
            return apology("Please provide a password.", 403)
        if request.form.get("confirmation") != password:
            return apology("Make sure the password matches with the confirmation password.", 403)

        # If user didn't input starting_cash
        if not starting_cash:
            starting_cash = '100000'

        # If starting_cash isn't an integer
        try:
            int(starting_cash)
        except:
            return apology("Please enter a valid value for your starting cash")


        try:
            db.execute("INSERT INTO users (username, hash, cash) VALUES (?,?,?)", name, generate_password_hash(password), starting_cash)
            rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]
            # Displays confirmation banner
            flash("You have been registered")
            # Redirect user to home page
            return redirect("/")



        except:
            return apology("This username has been taken.", 403)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == 'GET':

        # Gets dict of stock tickers that user bought
        tickers = db.execute("SELECT ticker FROM purchases WHERE id = ? GROUP BY ticker HAVING SUM(shares) > 0;", session["user_id"])
        print(tickers)

        # List of stocks the user owns
        stocks = []
        # Turns dict of tickers to list
        for i in range(0, len(tickers)):
            ticker = tickers[i]['ticker']
            stocks.append(ticker.upper())

        return render_template('sell.html', stocks = stocks)

    # After form submission
    if request.method == 'POST':
        # Checks that inputted quantity is a positive integer
        try:
            if int(request.form.get('shares').replace(',', '')) < 0:
                return apology("Please enter a valid quantity", 403)
        except:
            return apology("Please enter a positive integer as the quantity", 403)

        shares = int(request.form.get('shares').replace(',', ''))
        stock = request.form.get('stocks')
        # If user doesn't select a stock
        if not stock:
            return apology("Please select a stock to sell")

        # Dict of shares they own of the stock
        owned_shares = db.execute('SELECT SUM(shares) FROM purchases WHERE id = ? AND ticker = ?', session["user_id"], stock)

        # Number of shares user owns of stock
        num_shares = int(owned_shares[0]['SUM(shares)'])

        # If user doesn't own the stock
        if num_shares < 0:
            return apology('You do not own that stock')
        # If they don't have enough shares to sell the amount they entered.
        if num_shares < shares:
            return apology('Too many shares')
        # If user didn't input number of shares
        if not shares:
            return apology("Please enter a quantity of shares", 403)
        try:
            if int(shares) < 0:
                return apology("Please enter a valid quantity of shares", 403)
        except:
            return apology("Please enter a positive integer as the quantity of shares", 403)

        # Stock, shares
        looked_ticker = lookup(stock)

        list_cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = int(list_cash[0]['cash'])

        db.execute("INSERT INTO purchases (id, ticker, price, date, shares, company_name) VALUES (?,?,?,?,?,?)", session['user_id'], stock.upper(), looked_ticker['price'], datetime.datetime.now(), shares * -1, looked_ticker['name'])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + int(looked_ticker['price']) * int(shares), session['user_id'])
        flash(f"You have sold {shares} shares of {stock.upper()}")
        return redirect("/")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
