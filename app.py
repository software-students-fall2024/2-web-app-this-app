from dotenv import load_dotenv
import datetime
from flask import Flask, render_template, request, redirect, url_for
import pymongo
from bson.objectid import ObjectId
import os
from pymongo.mongo_client import MongoClient

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    db_uri = os.getenv("DB_URI")
    # Create a new client and connect to the server
    client = MongoClient(db_uri)
    db = client['bookstore']
    
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print("MongoDB connection error:", e)
        
    @app.route("/home", methods=["GET"])
    def home():
        return render_template('home.html')
        
    @app.route("/search")
    def search():
        """
        Search function to filter books based on title, author, genre, or date added.
        """
        query = {}
        
        #Get the query parameters from the request's query string
        title = request.args.get('title')
        author = request.args.get('author')
        genre = request.args.get('genre')
        date_added = request.args.get('date_added')
        price = request.args.get('price')
        
        #Build the query
        #Search for containment and case-insensitive
        if title:
            query['title'] = {'$regex': title, '$options':'i'}
        if author:
            query['author'] = {'$regex': author, '$options':'i'}
        if genre:
            query['genre'] = {'$regex': genre, '$options':'i'}
        if date_added:
            try:
                date_obj = datetime.datetime.strptime(date_added, "%Y-%m-%d")
                query['date_added'] = date_obj
            except ValueError:
                return "Invalid date format. Please use YYYY-MM-DD.", 400
       # Price filter: Search for books with price <= given value
        if price:
            try:
                price_value = float(price)  # Ensure valid float input
                query['price'] = {'$lte': price_value}
            except ValueError:
                return "Invalid price format. Please enter a valid number.", 400
            
            
        # Perform the search on the books collection
        results = db.books.find(query) if query else []
        
        #Render the search results
        return render_template('search.html', books=results)
    
    @app.route("/delete/<book_id>", methods=["POST"])
    def delete(book_id):
        """
        Route for POST requests to the delete page.
        Deletes the specified book from the database, and then redirects the browser to the home page.
        Args:
            book_id (str): The ID of the book to delete.
        Returns:
            redirect (Response): A redirect response to the home page.
        """
        db.books.delete_one({"_id": ObjectId(book_id)})
        return redirect(url_for("home"))
    
    @app.route("/add", methods=["POST"])
    def add():
        title = request.form.get('title')
        author = request.form.get('author')
        genre = request.form.get('genre')
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        date_added = datetime.datetime.utcnow()
        if not title or not author or not genre or not price or not quantity:
            return "All fields are required.", 400
        try:
            price = float(price)
            quantity = int(quantity)
        except ValueError:
            return "Price and quantity must be numbers.", 400
        
        if price <= 0 or quantity <= 0:
            return "Price and quantity must be positive values.", 400

        nbook = {
            "title": title,
            "author": author,
            "genre": genre,
            "price": price,
            "quantity": quantity,
            "date_added": date_added
        }
        result = db.books.insert_one(nbook)
        book_id = result.inserted_id
        return redirect(url_for("home"))
    
    @app.route("/show_inventory", methods=["GET"])
    def show_inventory():
        books = db.books.find({}, {"title": 1, "quantity": 1})
        list = list(books)
        return render_template('show_inventory.html', books=list)

    @app.route("/book_detail/<book_id>", methods=["GET"])
    def book_detail(book_id):
        book = db.books.find_one({"_id": ObjectId(book_id)})
        return render_template('book_detail.html', book=book)
    
    @app.route("/edit_price/<book_id>", methods=["POST"])
    def edit_price(book_id):
        price = request.form.get('price')
        try:
            price = float(price)
        except ValueError:
            return "Price must be numbers.", 400
        if price <= 0:
            return "Price must be a positive value.", 400

        db.books.update_one(
        {"_id": ObjectId(book_id)}, 
        {"$set": {"price": price}} )  

        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_quantity/<book_id>", methods=["POST"])
    def edit_quantity(book_id):
        quantity = request.form.get('quantity')
        try:
            quantity = int(quantity)
        except ValueError:
            return "Quantity must be numbers.", 400
        if quantity <= 0:
            return "Quantity must be a positive value.", 400
        
        db.books.update_one(
        {"_id": ObjectId(book_id)},
        {"$set": {"quantity": quantity}})

        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_title/<book_id>", methods=["POST"])
    def edit_title(book_id):
        title = request.form.get('title')
        if not title:
            return "Title cannot be empty.", 400
        db.books.update_one(
            {"_id": ObjectId(book_id)},
            {"$set": {"title": title}} )
        
        return redirect(url_for("book_detail", book_id=book_id))

    def edit_author(book_id):
        author = request.form.get('author')
        if not author:
            return "Author cannot be empty.", 400
        db.books.update_one(
            {"_id": ObjectId(book_id)}, 
            {"$set": {"author": author}})
        return redirect(url_for("book_detail", book_id=book_id))
    
    @app.route("/edit_genre/<book_id>", methods=["POST"])
    def edit_genre(book_id):    
        genre = request.form.get('genre')
        if not genre:
            return "Genre cannot be empty.", 400
        db.books.update_one(
            {"_id": ObjectId(book_id)},
            {"$set": {"genre": genre}})
        return redirect(url_for("book_detail", book_id=book_id))

    return app
            
    


if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    app = create_app()
    app.run(port=FLASK_PORT)