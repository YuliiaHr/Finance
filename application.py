import os
import re
import requests
import json
import re
import alert
   
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from sqlalchemy.engine.base import Transaction
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import time

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
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    user_id=session['user_id']
    transactions = db.execute("SELECT * FROM purchases WHERE buyer_id=:id", id=user_id)
    
    result = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)
   
    balance = round(result[0]['cash'], 2)
    
    grand_total=0 
    cash=0

    for transaction in transactions:
        price=transaction['price']
        quantity=transaction["quantity"]
               
        expense = quantity*price

        grand_total += expense
    
        cash=round((balance+grand_total), 2)
        
    shares_quantity_bought={}
    for transaction in transactions:
        if transaction['share_symbol'] in shares_quantity_bought:
            shares_quantity_bought[transaction['share_symbol']] += transaction['quantity']
        else:
            shares_quantity_bought[transaction['share_symbol']] = transaction['quantity']

    portfolio=[]
    total=0
    symbols_unique = list(shares_quantity_bought.keys())
    
    for symbol in symbols_unique:
        data = lookup(symbol)
        price=data["price"]
        quantity=shares_quantity_bought[symbol]
        total=price*quantity

        portfolioItem = {
            "symbol": symbol,
            "name": data['name'],
            "quantity": quantity,
            "price": price,
            "total": total
        }
        if quantity != 0:
            portfolio.append(portfolioItem)
        
    return render_template("index.html",   
    transactions=transactions,
    portfolio=portfolio,
    grand_total=grand_total,
    balance=balance,
    cash=cash)
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = (request.form.get("symbol")).upper()
        shares_quantity = int(request.form.get("shares_quantity"))
        if not symbol:
            return apology("must provide symbol", 403)
        elif not shares_quantity:
            return apology("must provide quantity of shares", 403)
        
        data = lookup(symbol)
      
        if data == None:
            return apology("Company name symbol does not exist")

        user_id=session['user_id']
        
        transaction_time=time.strftime('%Y-%m-%d %H:%M:%S')
        print(type(transaction_time))

        price = data["price"]
        
        print("PRICE", price)
        if data == None:
            return apology("Company name does not exist")

        result = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)
        cash=result[0]["cash"]
        print("BALANCE:", cash)

        new_balance=cash-shares_quantity*price

        if cash < shares_quantity*price:
            flash("Not enough cash. Please buy less!")
        else:  
            db.execute("UPDATE users SET cash =:cash WHERE id=:id", cash=new_balance, id=user_id) 
            db.execute("INSERT INTO purchases (buyer_id, share_symbol, quantity, price, transacted) VALUES(?, ?, ?, ?, ?)", user_id, symbol, shares_quantity, price, transaction_time ) 
            flash("Successfully bought!")

        return redirect("/")

    symbol=request.args.get('symbol')
        
    return render_template("buy.html", symbol=symbol)


@app.route("/history")
@login_required
def history():
    user_id=session['user_id']
    transactions = db.execute("SELECT * FROM purchases WHERE buyer_id=:id", id=user_id)

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username=request.form.get("username")
        password=request.form.get("password")
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        
        regex = r'^\w*$'    
        if not re.match(regex,username): 
           flash("Username must contain letters and numbers")

        if not len(username) >= 3 or len(username) <= 8:
            flash("Password length must be at least 6 characters")    

        if not len(password) >= 6:
          flash("Password length must be at least 6 characters")
        
        
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
 
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        flash("Successfully login!")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

       
@app.route("/password_reset", methods=["GET", "POST"])
def password_reset():
    if request.method == "GET":
        return render_template("password_reset")
    else:
        username=request.form.get("username")
        password_reset=request.form.get("password")
        password_again=request.form.get("password_again")

        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif password_reset != password_again:   
            return apology("Your password and confirmation password do not match", 403)
        
        result=db.execute("SELECT id FROM users WHERE username=?", username)
        user_id=result[0]['id']
       
        new_hash = generate_password_hash(password_reset)
        db.execute("UPDATE users SET hash =:new_hash WHERE id=:id", new_hash = new_hash, id=user_id) 
        
        session["user_id"] = user_id
        flash("Successfully changed password!")
       
    return redirect("/")

@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    if request.method == "GET":
        return render_template("add_cash")
    else: 
        if not request.form.get("add_cash"):
            return apology("must provide desire cash amount to add", 403)
        else:
            add_cash=int(request.form.get("add_cash"))
            user_id=session["user_id"]
            
            result=db.execute("SELECT cash FROM users WHERE id=?", user_id)
        
            cash=result[0]["cash"]
            new_cash= add_cash+cash
            db.execute("UPDATE users SET cash =:new_cash WHERE id=:id", new_cash = new_cash, id=user_id) 
            
    return redirect("/")

           
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        # query = {"token": "pk_82d3992535964b8b9e7d370b21b8242a"}
        symbol = request.form.get("symbol")
        # response = requests.get("https://cloud.iexapis.com/stable/stock/"+symbol+"/quote", params= query)
        # response_json = response.json()
        # price = response_json['iexClose']
        data = lookup(symbol)
        print('data', data)

        if data == None:
            return apology("Company name does not exist")
                
        return render_template(
            "quoted.html",
            data=data 
        )
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    password_again = request.form.get("password_again")

    if request.method == "POST":
        
        # Ensure username, password was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif password != password_again:   
            return apology("Your password and confirmation password do not match", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Ensure username exists:
        if len(rows) == 1: 
            return apology("User already exists")
        # Remember which user has logged in
        else:
            hash = generate_password_hash(password)
            user_id = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash) 
                
            session["user_id"] = user_id
    else:
        return render_template("register.html")

    return redirect("/")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    symbol = request.form.get("symbol")
    
    user_id=session['user_id']
    transactions = db.execute("SELECT * FROM purchases WHERE buyer_id=:id", id=user_id)
    
    symbols=[]
    symbols_unigue=[]
    shares_quantity=[]

    for transaction in transactions:
        symbol= transaction['share_symbol']   
        symbols.append(symbol)
        symbols_unigue=list(set(symbols))
    
    if request.method == "POST":
        shares_quantity_bought={}

        for transaction in transactions:

            if transaction['share_symbol'] in shares_quantity_bought:
                shares_quantity_bought[transaction['share_symbol']] += transaction['quantity']
            else:
                shares_quantity_bought[transaction['share_symbol']] = transaction['quantity']

        shares_quantity = int(request.form.get("shares_quantity"))   
        symbol = request.form.get("symbol")

        print('shares_quantity_bought', shares_quantity_bought) 
        
        if not shares_quantity:
            return apology("must provide quantity of shares", 403)   
        if not symbol:
            return apology("must provide symbol", 403)

        if shares_quantity>shares_quantity_bought[symbol]:
            return apology("You may not sell more shares than you currently hold")

        if shares_quantity<0:
            return apology("must provide positive quantity of shares")

        data = lookup(symbol)
        print("DATA", data)  

        result = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)
        cash=result[0]["cash"]

        price=data["price"]
        new_balance=cash+shares_quantity*price

        transaction_time=time.strftime('%Y-%m-%d %H:%M:%S')
        name=data["name"]

        db.execute("INSERT INTO purchases (buyer_id, share_symbol, quantity, price, transacted) VALUES(?, ?, ?, ?, ?)", user_id, symbol, -(shares_quantity), price, transaction_time ) 
        flash("Successfully sold!")
        db.execute("UPDATE users SET cash =:cash WHERE id=:id", cash=new_balance, id=user_id) 
                    
        return redirect("/")
        
    symbol=request.args.get('symbol')

    return render_template("sell.html", symbols_unigue=symbols_unigue, symbol=symbol)
        
def errorhandler(e):
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
