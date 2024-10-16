from dotenv import load_dotenv
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymongo
from bson.objectid import ObjectId
import os
from pymongo.mongo_client import MongoClient
import re

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    app.secret_key = os.getenv("SECRET_KEY")  # actually, this is supposed to go into .env, but leave it for now
    
    db_uri = os.getenv("DB_URI")
    
    client = MongoClient(db_uri)
    db = client['bookstore']
    
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print("MongoDB connection error:", e)
    
    # Decorator to check if user is logged in
    def login_required(f):
        def wrapper(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__ 
        return wrapper
    
    @app.route("/login", methods=["GET", "POST"])
    def login():
        usersDB = db['users']

        if request.method == "POST": 
            username = request.form.get('username')
            password = request.form.get('password')

            user = usersDB.find_one({"username": username})

            if user and password == user['password']:
                session['logged_in'] = True
                session['username'] = user['username']
                return redirect(url_for("home"))
            else:
                return render_template("login.html", message="Invalid credentials.")

        return render_template("login.html", message="")
    
    @app.route("/register", methods = ["GET", "POST"])
    def register():
        usersDB = db['users']

        if request.method == "POST":
            username = request.form.get('username')
            password1 = request.form.get('password1')
            password2 = request.form.get('password2')
            
            user = usersDB.find_one({"username": username})

            if user:
                return render_template("register.html", message="Username already exists.")
            else:
                if password1 == password2:
                    user = {
                        "username": username,
                        "password": password1
                    }
                    usersDB.insert_one(user)
                    
                    db.create_collection(username)
                    
                    samplebook = {
                        "title": "Lorem ipsum",
                        "author": "Lorem ipsum",
                        "genre": "Lorem ipsum",
                        "price": "0",
                        "quantity": 1,
                        "date_added": datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    }
                    
                    db[username].insert_one(samplebook)
                    return redirect(url_for("login"))
                else:
                    return render_template("register.html", message="Passwords don't match.")
                
        return render_template("register.html", message="")
    

    @app.route("/", methods=["GET"])
    @login_required
    def root():
        return redirect(url_for("home"))
        
    @app.route("/home", methods=["GET"])
    @login_required
    def home():
        user = session['username']
        books = db[user].find({}, {"title": 1, "quantity": 1})
        book_lst = list(books)
        return render_template('home.html', user=user, books=book_lst)
        
    @app.route("/search", methods=["GET"])
    @login_required
    def search():
        """
        Search function to filter books based on title, author, genre, or date added.
        """
        query = {}
        price_filters = {}
        
        title = request.args.get('title')
        author = request.args.get('author')
        genre = request.args.get('genre')
        date_added = request.args.get('dateAdded')
        priceBelow = request.args.get('priceBelow')
        priceAbove = request.args.get('priceAbove')
        useRegex = request.args.get('regex')
        
        inputDict = {'title': "", 'author': "", 'genre': "", 'priceBelow': "", 'priceAbove': "", 'dateAdded': "", 'regex': ""}
        if useRegex:
            inputDict['regex'] = "checked"
        
        if not(title or author or genre or date_added or priceBelow or priceAbove):
            return render_template('search.html', message="", userInput=inputDict, books=[])
        
        if title:
            query['title'] = {'$regex': title, '$options':'i'} if useRegex else {'$regex': re.escape(title), '$options':'i'}
            inputDict['title'] = title
        if author:
            query['author'] = {'$regex': author, '$options':'i'} if useRegex else {'$regex': re.escape(author), '$options':'i'}
            inputDict['author'] =author
        if genre:
            query['genre'] = {'$regex': genre, '$options':'i'} if useRegex else {'$regex': re.escape(genre), '$options':'i'}
            inputDict['genre'] = genre
        if date_added:
            # query['date_added'] = {'$regex': re.escape(date_added), '$options':'i'}
            # inputDict['dateAdded'] = date_added
            date_obj = datetime.datetime.strptime(date_added, "%Y-%m-%d")
            query['date_added'] = date_obj
            inputDict['dateAdded'] = date_added
        # Price filter: Search for books with price <= given value
         # Handle price filters by combining them in a single query
        try:
            if priceBelow:
                price_filters['$lte'] = float(priceBelow)
                inputDict['priceBelow'] = priceBelow
            if priceAbove:
                price_filters['$gte'] = float(priceAbove)
                inputDict['priceAbove'] = priceAbove
        except ValueError:
            msg = "Invalid price format. Please enter a valid number."
            return render_template('search.html', message=msg, userInput=inputDict, books=[])

        if price_filters:
            query['price'] = price_filters

        results = list(db[session['username']].find(query)) if query else []
        for book in results:
            book["date_added"] = book["date_added"].strftime("%Y-%m-%d")

        return render_template('search.html', message="", userInput=inputDict, books=results)
    
    @app.route("/delete_book/<book_id>", methods=["POST"])
    @login_required
    def delete_book(book_id):
        """
        Route for POST requests to the delete page.
        Deletes the specified book from the base, and then redirects the browser to the home page.
        Args:
            book_id (str): The ID of the book to delete.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        db[session['username']].delete_one({"_id": ObjectId(book_id)})
        return redirect(url_for("home"))
    
    @app.route("/add", methods=["GET", "POST"])
    @login_required
    def add():
        if request.method == "GET":
            inputDict = {'title': "", 'author': "", 'genre': "", 'price': "", 'quantity': ""}
            return render_template('add.html', message="", userInput=inputDict)
        
        title = request.form.get('title')
        author = request.form.get('author')
        genre = request.form.get('genre')
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        date_added = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)  # only preserve the date
        inputDict = {'title': title, 'author': author, 'genre': genre, 'price': price, 'quantity': quantity}
        if not title or not author or not genre or not price or not quantity:
            return render_template("add.html", message="All fields are required.", userInput=inputDict)
        try:
            price = float(price)
            quantity = int(quantity)
        except ValueError:
            return render_template("add.html", message="Price and quantity must be numbers.", userInput=inputDict)
        
        if price < 0 or quantity < 0:
            return render_template("add.html", message="Price and quantity must be non-negative values.", userInput=inputDict)

        nbook = {
            "title": title,
            "author": author,
            "genre": genre,
            "price": price,
            "quantity": quantity,
            "date_added": date_added
        }
        userdb = session['username']
        result = db[userdb].insert_one(nbook)
        book_id = result.inserted_id
        return redirect(url_for("home"))

    @app.route("/book_detail/<book_id>", methods=["GET"])
    @login_required
    def book_detail(book_id):
        userdb = session['username']
        book = db[userdb].find_one({"_id": ObjectId(book_id)})
        return render_template('book_detail.html', book=book)
    
    @app.route("/edit/<book_id>", methods=["GET", "POST"])
    @login_required
    def edit(book_id):
        userdb = session['username']
        if request.method == "POST":  
            title = request.form.get('title')
            author = request.form.get('author')
            genre = request.form.get('genre')
            price = request.form.get('price')
            quantity = request.form.get('quantity')
            book = db[userdb].find_one({"_id": ObjectId(book_id)})
            inputDict = {'title': title, 'author': author, 'genre': genre, 'price': price, 'quantity': quantity}
            try:
                price = float(price)
                quantity = int(quantity)
            except ValueError:
                return render_template("edit.html", message="Price and quantity must be numbers.", userInput=inputDict,book=book)
        
            if price < 0 or quantity < 0:
                return render_template("edit.html", message="Price and quantity must be non-negative values.", userInput=inputDict,book=book)


            db[userdb].update_one(
                {"_id": ObjectId(book_id)},
                {"$set": {
                    "title": title,
                    "author": author,
                    "genre": genre,
                    "price": price,
                    "quantity": quantity
                }}
            )
            return redirect(url_for("book_detail", book_id=book_id))

        book = db[userdb].find_one({"_id": ObjectId(book_id)})
        return render_template('edit.html', book=book)

    '''
    @app.route("/edit_price/<book_id>", methods=["POST"])
    @login_required
    def edit_price(book_id):
        price = request.form.get('price')
        inputDict = {"price": price}
        try:
            price = float(price)
        except ValueError:
            return render_template("edit.html", message="Price must be a number.", userInput=inputDict)
        if price <= 0:
            return render_template("edit.html", message="Price must be a positive value.", userInput=inputDict)

        userdb = session['username']
        db[userdb].update_one(
        {"_id": ObjectId(book_id)}, 
        {"$set": {"price": price}} )  

        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_quantity/<book_id>", methods=["POST"])
    @login_required
    def edit_quantity(book_id):
        quantity = request.form.get('quantity')
        inputDict = {"quantity": quantity}
        try:
            quantity = int(quantity)
        except ValueError:
            return render_template("edit.html", message="Quantity must be a number.", userInput=inputDict)
        if quantity <= 0:
            return render_template("edit.html", message="Quantity must be a positive value.", userInput=inputDict)

        
        userdb = session['username']
        db[userdb].update_one(
        {"_id": ObjectId(book_id)},
        {"$set": {"quantity": quantity}})

        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_title/<book_id>", methods=["POST"])
    @login_required
    def edit_title(book_id):
        title = request.form.get('title')
        inputDict = {"title": title}
        if not title:
            return render_template("edit.html", message="Title cannot be empty.", userInput=inputDict)
        userdb = session['username']
        db[userdb].update_one(
            {"_id": ObjectId(book_id)},
            {"$set": {"title": title}} )
        
        return redirect(url_for("book_detail", book_id=book_id))

    @app.route("/edit_author/<book_id>", methods=["POST"])
    def edit_author(book_id):
        author = request.form.get('author') 
        inputDict = {"author": author}
        if not author:
            return render_template("edit.html", message="Author cannot be empty.", userInput=inputDict)
        userdb = session['username']
        db[userdb].update_one(
            {"_id": ObjectId(book_id)}, 
            {"$set": {"author": author}})
        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_genre/<book_id>", methods=["POST"])
    @login_required
    def edit_genre(book_id):    
        genre = request.form.get('genre')
        inputDict = {"genre": genre}
        if not genre:
            return render_template("edit.html", message="Genre cannot be empty.", userInput=inputDict)
        userdb = session['username']
        db[userdb].update_one(
            {"_id": ObjectId(book_id)},
            {"$set": {"genre": genre}})
        return redirect(url_for("book_detail", book_id=book_id))
    '''
    
    @app.route('/logout', methods=["GET"])
    def logout():
        session.pop('logged_in', None)
        session.pop('username', None)
        return redirect(url_for('login'))

    
    return app
            
    



if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    app = create_app()
    app.run(port=FLASK_PORT)