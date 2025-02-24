from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
from PIL import Image
import random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import datetime
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = 'your_secret_key_here'  # استبدلها بمفتاح سري آمن
SPOONACULAR_API_KEY = 'your_spoonacular_api_key_here'  # استبدلها بمفتاح API خاص بك

# إعداد Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, is_premium=0):
        self.id = id
        self.username = username
        self.is_premium = is_premium

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT id, username, is_premium FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# دالة لإنشاء قاعدة البيانات (بدون حذف تلقائي)
def init_db():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS recipes 
                 (id INTEGER PRIMARY KEY, country TEXT, continent TEXT, name TEXT, ingredients TEXT, instructions TEXT, 
                  category TEXT, prep_time INTEGER, calories INTEGER, difficulty TEXT, servings INTEGER, season TEXT,
                  image_path TEXT, video_url TEXT, source TEXT, warnings TEXT, approved INTEGER DEFAULT 1, 
                  rating REAL DEFAULT 0, rating_count INTEGER DEFAULT 0, added_date TEXT, user_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_ratings 
                 (id INTEGER PRIMARY KEY, user_id TEXT, recipe_id INTEGER, rating INTEGER, comment TEXT, date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS favorites 
                 (id INTEGER PRIMARY KEY, user_id TEXT, recipe_id INTEGER, date_added TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cookbooks 
                 (id INTEGER PRIMARY KEY, user_id TEXT, recipe_id INTEGER, notes TEXT, date_added TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, is_premium INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS followers 
                 (id INTEGER PRIMARY KEY, follower_id TEXT, followed_id TEXT, date_followed TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS notifications 
                 (id INTEGER PRIMARY KEY, user_id TEXT, message TEXT, date TEXT, read INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS blog_posts 
                 (id INTEGER PRIMARY KEY, title TEXT, content TEXT, author_id TEXT, date TEXT, related_recipe_id INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS contests 
                 (id INTEGER PRIMARY KEY, title TEXT, start_date TEXT, end_date TEXT, winner_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS contest_entries 
                 (id INTEGER PRIMARY KEY, contest_id INTEGER, recipe_id INTEGER, user_id TEXT, votes INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS donations 
                 (id INTEGER PRIMARY KEY, user_id TEXT, amount REAL, date TEXT)''')
    
    # إضافة جدول community_posts لصفحة المجتمع
    c.execute('''CREATE TABLE IF NOT EXISTS community_posts 
                 (post_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, content TEXT, timestamp DATETIME, 
                  likes INTEGER DEFAULT 0, FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # إضافة بيانات افتراضية فقط إذا كانت القاعدة جديدة
    c.execute("SELECT COUNT(*) FROM recipes")
    if c.fetchone()[0] == 0:
        countries = [
            ("Afghanistan", "Asia", "Kabuli Pulao", "Rice, Lamb, Carrots, Raisins", "Cook lamb with spices, mix with rice", "Non-Vegetarian", 60, 600, "Medium", 4, "Winter", json.dumps(["uploads/kabuli_pulao.jpg"]), "", "Wikipedia", "Nut-free", "anonymous"),
            ("Albania", "Europe", "Tavë Kosi", "Lamb, Yogurt, Eggs", "Bake lamb with yogurt mixture", "Non-Vegetarian", 90, 700, "Medium", 6, "Spring", json.dumps(["uploads/tave_kosi.jpg"]), "", "Traditional Recipe", "", "anonymous"),
        ]
        
        for country in countries:
            c.execute("INSERT OR IGNORE INTO recipes (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, approved, added_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (*country, 1, datetime.datetime.now().strftime("%Y-%m-%d")))
        
        c.execute("INSERT OR IGNORE INTO blog_posts (title, content, author_id, date, related_recipe_id) VALUES (?, ?, ?, ?, ?)",
                  ("Best Spices for Asian Dishes", "Explore the top spices like turmeric and ginger...", "anonymous", datetime.datetime.now().strftime("%Y-%m-%d"), 1))
        
        c.execute("INSERT OR IGNORE INTO contests (title, start_date, end_date) VALUES (?, ?, ?)",
                  ("March Cooking Challenge", datetime.datetime.now().strftime("%Y-%m-%d"), (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")))
    
    conn.commit()
    conn.close()

# التحقق من وجود قاعدة البيانات وإنشائها إذا لم تكن موجودة
if not os.path.exists('recipes.db'):
    init_db()

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# تسجيل المستخدم
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

# تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        c.execute("SELECT id, username, password, is_premium FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            user_obj = User(user[0], user[1], user[3])
            login_user(user_obj)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

# تسجيل الخروج
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

# الصفحة الرئيسية
@app.route('/', methods=['GET', 'POST'])
def index():
    categories = ["Vegetarian", "Non-Vegetarian", "Gluten-Free", "Quick Meals"]
    difficulties = ["Easy", "Medium", "Hard"]
    continents = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"]
    seasons = ["Spring", "Summer", "Autumn", "Winter", "All Seasons"]
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    
    c.execute("SELECT id, country, name, rating, image_path FROM recipes WHERE approved = 1 ORDER BY added_date DESC LIMIT 6")
    latest_recipes_raw = c.fetchall()
    latest_recipes = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else []) for r in latest_recipes_raw]
    
    c.execute("SELECT id, country, name, rating, image_path FROM recipes WHERE approved = 1 ORDER BY rating DESC LIMIT 6")
    top_recipes_raw = c.fetchall()
    top_recipes = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else []) for r in top_recipes_raw]
    
    c.execute("SELECT id, country, name, rating, image_path FROM recipes WHERE approved = 1 ORDER BY RANDOM() LIMIT 6")
    featured_recipes_raw = c.fetchall()
    featured_recipes = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else []) for r in featured_recipes_raw]
    
    c.execute("SELECT id, country, name, rating, image_path FROM recipes WHERE approved = 1 ORDER BY RANDOM() LIMIT 1")
    daily_recipe_raw = c.fetchone()
    daily_recipe = (daily_recipe_raw[0], daily_recipe_raw[1], daily_recipe_raw[2], daily_recipe_raw[3], json.loads(daily_recipe_raw[4]) if daily_recipe_raw[4] and daily_recipe_raw[4] != '[]' and daily_recipe_raw[4] != '' else []) if daily_recipe_raw else None
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        category = request.form.get('category', '')
        difficulty = request.form.get('difficulty', '')
        continent = request.form.get('continent', '')
        season = request.form.get('season', '')
        max_time = request.form.get('max_time', type=int)
        min_calories = request.form.get('min_calories', type=int)
        max_calories = request.form.get('max_calories', type=int)
        
        query = "SELECT id, country, name, ingredients, category, image_path, rating FROM recipes WHERE approved = 1"
        params = []
        if country:
            query += " AND country LIKE ?"
            params.append(f"%{country}%")
        if category:
            query += " AND category = ?"
            params.append(category)
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        if continent:
            query += " AND continent = ?"
            params.append(continent)
        if season:
            query += " AND season = ?"
            params.append(season)
        if max_time:
            query += " AND prep_time <= ?"
            params.append(max_time)
        if min_calories:
            query += " AND calories >= ?"
            params.append(min_calories)
        if max_calories:
            query += " AND calories <= ?"
            params.append(max_calories)
        
        c.execute(query, params)
        recipes_raw = c.fetchall()
        recipes = [(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]) if r[5] and r[5] != '[]' and r[5] != '' else [], r[6]) for r in recipes_raw]
        conn.close()
        if recipes:
            return render_template('recipes.html', country=country, recipes=recipes)
        flash("No recipes found matching your criteria.", "warning")
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('index.html', categories=categories, difficulties=difficulties, continents=continents, seasons=seasons,
                         latest_recipes=latest_recipes, top_recipes=top_recipes, featured_recipes=featured_recipes, 
                         daily_recipe=daily_recipe)

# صفحة تفاصيل الوصفة
@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT id, country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, rating, user_id FROM recipes WHERE id = ?", (recipe_id,))
    recipe = c.fetchone()
    
    c.execute("SELECT rating, comment, date FROM user_ratings WHERE recipe_id = ? ORDER BY date DESC LIMIT 5", (recipe_id,))
    comments = c.fetchall()
    
    user_id = current_user.id if current_user.is_authenticated else "anonymous"
    c.execute("SELECT id FROM favorites WHERE user_id = ? AND recipe_id = ?", (user_id, recipe_id))
    is_favorite = bool(c.fetchone())
    
    c.execute("SELECT id FROM cookbooks WHERE user_id = ? AND recipe_id = ?", (user_id, recipe_id))
    in_cookbook = bool(c.fetchone())
    
    conn.close()
    
    if recipe:
        images = json.loads(recipe[12]) if recipe[12] and recipe[12] != '[]' and recipe[12] != '' else []
        shopping_list = recipe[4].split(", ")
        return render_template('recipe_detail.html', recipe=recipe, images=images, shopping_list=shopping_list, comments=comments, is_favorite=is_favorite, in_cookbook=in_cookbook)
    return redirect(url_for('index'))

# إضافة وصفة مع إشعارات للمتابعين
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    categories = ["Vegetarian", "Non-Vegetarian", "Gluten-Free", "Quick Meals"]
    difficulties = ["Easy", "Medium", "Hard"]
    continents = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"]
    seasons = ["Spring", "Summer", "Autumn", "Winter", "All Seasons"]
    
    if request.method == 'POST':
        country = request.form['country']
        continent = request.form['continent']
        name = request.form['name']
        ingredients = request.form['ingredients'].replace("pork", "chicken").replace("wine", "grape juice").replace("alcohol", "juice")
        instructions = request.form['instructions']
        category = request.form['category']
        prep_time = int(request.form['prep_time'])
        calories = int(request.form['calories'])
        difficulty = request.form['difficulty']
        servings = int(request.form['servings'])
        season = request.form['season']
        video_url = request.form.get('video_url', '')
        source = request.form.get('source', 'User Submitted')
        warnings = request.form.get('warnings', '')
        user_id = current_user.id
        
        image_paths = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(full_path)
                    image_paths.append(f"uploads/{filename}")
        
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        c.execute("INSERT INTO recipes (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, approved, added_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, json.dumps(image_paths), video_url, source, warnings, 1, datetime.datetime.now().strftime("%Y-%m-%d"), user_id))
        recipe_id = c.lastrowid
        
        c.execute("SELECT follower_id FROM followers WHERE followed_id = ?", (user_id,))
        followers = c.fetchall()
        for follower in followers:
            message = f"{current_user.username} added a new recipe: {name}"
            c.execute("INSERT INTO notifications (user_id, message, date) VALUES (?, ?, ?)",
                      (follower[0], message, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        flash("Recipe added successfully!", "success")
        return redirect(url_for('index'))
    return render_template('add.html', categories=categories, difficulties=difficulties, continents=continents, seasons=seasons)

# تقييم وصفة
@app.route('/rate/<int:recipe_id>', methods=['POST'])
@login_required
def rate_recipe(recipe_id):
    rating = int(request.form['rating'])
    comment = request.form.get('comment', '')
    user_id = current_user.id
    
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    
    c.execute("INSERT INTO user_ratings (user_id, recipe_id, rating, comment, date) VALUES (?, ?, ?, ?, ?)",
              (user_id, recipe_id, rating, comment, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    c.execute("SELECT rating, rating_count FROM recipes WHERE id = ?", (recipe_id,))
    current = c.fetchone()
    new_count = current[1] + 1
    new_rating = (current[0] * current[1] + rating) / new_count
    c.execute("UPDATE recipes SET rating = ?, rating_count = ? WHERE id = ?", (new_rating, new_count, recipe_id))
    
    conn.commit()
    conn.close()
    flash("Rating submitted successfully!", "success")
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

# إضافة إلى المفضلة
@app.route('/favorite/<int:recipe_id>', methods=['POST'])
@login_required
def add_to_favorites(recipe_id):
    user_id = current_user.id
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("INSERT INTO favorites (user_id, recipe_id, date_added) VALUES (?, ?, ?)",
              (user_id, recipe_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    flash("Recipe added to favorites!", "success")
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

# إزالة من المفضلة
@app.route('/unfavorite/<int:recipe_id>', methods=['POST'])
@login_required
def remove_from_favorites(recipe_id):
    user_id = current_user.id
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?", (user_id, recipe_id))
    conn.commit()
    conn.close()
    flash("Recipe removed from favorites!", "success")
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

# إضافة إلى كتاب الوصفات
@app.route('/add_to_cookbook/<int:recipe_id>', methods=['POST'])
@login_required
def add_to_cookbook(recipe_id):
    user_id = current_user.id
    notes = request.form.get('notes', '')
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("INSERT INTO cookbooks (user_id, recipe_id, notes, date_added) VALUES (?, ?, ?, ?)",
              (user_id, recipe_id, notes, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    flash("Recipe added to your cookbook!", "success")
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

# إزالة من كتاب الوصفات
@app.route('/remove_from_cookbook/<int:recipe_id>', methods=['POST'])
@login_required
def remove_from_cookbook(recipe_id):
    user_id = current_user.id
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("DELETE FROM cookbooks WHERE user_id = ? AND recipe_id = ?", (user_id, recipe_id))
    conn.commit()
    conn.close()
    flash("Recipe removed from your cookbook!", "success")
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

# عرض المفضلة
@app.route('/favorites')
@login_required
def favorites():
    user_id = current_user.id
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT r.id, r.country, r.name, r.rating, r.image_path FROM recipes r JOIN favorites f ON r.id = f.recipe_id WHERE f.user_id = ?", (user_id,))
    favorite_recipes_raw = c.fetchall()
    favorite_recipes = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else []) for r in favorite_recipes_raw]
    conn.close()
    return render_template('favorites.html', favorite_recipes=favorite_recipes)

# عرض كتاب الوصفات
@app.route('/cookbook')
@login_required
def cookbook():
    user_id = current_user.id
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT r.id, r.country, r.name, r.rating, r.image_path, c.notes FROM recipes r JOIN cookbooks c ON r.id = c.recipe_id WHERE c.user_id = ?", (user_id,))
    cookbook_recipes_raw = c.fetchall()
    cookbook_recipes = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else [], r[5]) for r in cookbook_recipes_raw]
    conn.close()
    return render_template('cookbook.html', cookbook_recipes=cookbook_recipes)

# مساعد ذكي مع بحث عبر الإنترنت
@app.route('/suggest', methods=['GET', 'POST'])
@login_required
def suggest():
    categories = ["Vegetarian", "Non-Vegetarian", "Gluten-Free", "Quick Meals"]
    difficulties = ["Easy", "Medium", "Hard"]
    
    if request.method == 'POST':
        preferences = request.form['preferences'].lower()
        max_time = request.form.get('max_time', type=int)
        category = request.form.get('category', '')
        difficulty = request.form.get('difficulty', '')
        
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        c.execute("SELECT id, country, name, ingredients, instructions, category, prep_time, difficulty, image_path FROM recipes WHERE approved = 1")
        recipes_raw = c.fetchall()
        recipes = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], json.loads(r[8]) if r[8] and r[8] != '[]' and r[8] != '' else []) for r in recipes_raw]
        
        recipe_texts = [f"{r[3]} {r[4]}" for r in recipes]
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(recipe_texts)
        user_vector = vectorizer.transform([preferences])
        similarities = cosine_similarity(user_vector, tfidf_matrix).flatten()
        top_indices = similarities.argsort()[-3:][::-1]
        
        suggestions = []
        for i in top_indices:
            r = recipes[i]
            if (not max_time or r[6] <= max_time) and (not category or r[5] == category) and (not difficulty or r[7] == difficulty):
                suggestions.append(r)
        
        if len(suggestions) < 3 or max(similarities) < 0.1:
            url = f"https://api.spoonacular.com/recipes/complexSearch?query={preferences}&apiKey={SPOONACULAR_API_KEY}&number=1&instructionsRequired=true&addRecipeInformation=true"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['results']:
                        result = data['results'][0]
                        new_recipe = (
                            None, "Unknown", "Unknown", result['title'], 
                            ", ".join([ing['name'] for ing in result['extendedIngredients']]), 
                            result['instructions'] or "Cook as desired", 
                            category or "Non-Vegetarian", result.get('readyInMinutes', 45), 
                            result.get('nutrition', {}).get('caloricContent', 500), 
                            difficulty or "Medium", 4, "All Seasons", 
                            [result.get('image', '')] if result.get('image') else [], "", "Spoonacular", "", current_user.id
                        )
                        suggestions.append(new_recipe)
                        c.execute("INSERT INTO recipes (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, approved, added_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (new_recipe[1], new_recipe[2], new_recipe[3], new_recipe[4], new_recipe[5], new_recipe[6], new_recipe[7], new_recipe[8], new_recipe[9], new_recipe[10], new_recipe[11], json.dumps(new_recipe[12]), new_recipe[13], new_recipe[14], new_recipe[15], 1, datetime.datetime.now().strftime("%Y-%m-%d"), new_recipe[16]))
            except:
                new_name = f"AI {preferences.capitalize()} Dish"
                new_ingredients = f"Chicken, {preferences}, Spices" if "vegetarian" not in preferences else f"Vegetables, {preferences}, Spices"
                new_instructions = f"Cook {preferences} with spices and chicken" if "vegetarian" not in preferences else f"Cook {preferences} with vegetables"
                new_category = category or ("Non-Vegetarian" if "vegetarian" not in preferences else "Vegetarian")
                new_difficulty = difficulty or "Medium"
                estimated_time = random.randint(30, 90) if not max_time else min(max_time, random.randint(30, 90))
                new_recipe = (None, "AI Suggested", "Unknown", new_name, new_ingredients, new_instructions, new_category, estimated_time, 500, new_difficulty, 4, "All Seasons", [], "", "AI Generated", "", current_user.id)
                suggestions.append(new_recipe)
                c.execute("INSERT INTO recipes (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, approved, added_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (new_recipe[1], new_recipe[2], new_recipe[3], new_recipe[4], new_recipe[5], new_recipe[6], new_recipe[7], new_recipe[8], new_recipe[9], new_recipe[10], new_recipe[11], json.dumps(new_recipe[12]), new_recipe[13], new_recipe[14], new_recipe[15], 1, datetime.datetime.now().strftime("%Y-%m-%d"), new_recipe[16]))
            
            side_name = f"{preferences.capitalize()} Side Dish"
            side_ingredients = f"Potatoes, {preferences}, Herbs" if "vegetarian" in preferences else f"Chicken, {preferences}, Herbs"
            side_instructions = f"Roast {preferences} with potatoes" if "vegetarian" in preferences else f"Grill {preferences} with chicken"
            side_recipe = (None, "AI Suggested", "Unknown", side_name, side_ingredients, side_instructions, "Quick Meals", 20, 300, "Easy", 2, "All Seasons", [], "", "AI Generated Side", "", current_user.id)
            suggestions.append(side_recipe)
            c.execute("INSERT INTO recipes (country, continent, name, ingredients, instructions, category, prep_time, calories, difficulty, servings, season, image_path, video_url, source, warnings, approved, added_date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (side_recipe[1], side_recipe[2], side_recipe[3], side_recipe[4], side_recipe[5], side_recipe[6], side_recipe[7], side_recipe[8], side_recipe[9], side_recipe[10], side_recipe[11], json.dumps(side_recipe[12]), side_recipe[13], side_recipe[14], side_recipe[15], 1, datetime.datetime.now().strftime("%Y-%m-%d"), side_recipe[16]))
            conn.commit()
        
        conn.close()
        return render_template('suggestions.html', suggestions=suggestions, preferences=preferences, categories=categories, difficulties=difficulties)
    return render_template('suggestions.html', suggestions=[], categories=categories, difficulties=difficulties)

# API لجلب قائمة التسوق
@app.route('/shopping_list/<int:recipe_id>')
@login_required
def shopping_list(recipe_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT ingredients FROM recipes WHERE id = ?", (recipe_id,))
    recipe = c.fetchone()
    conn.close()
    if recipe:
        shopping_list = recipe[0].split(", ")
        converted_list = [f"{item} (~{random.randint(50, 200)}g)" for item in shopping_list]
        return jsonify({"shopping_list": converted_list})
    return jsonify({"error": "Recipe not found"}), 404

# صفحة البحث المتقدم
@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    categories = ["Vegetarian", "Non-Vegetarian", "Gluten-Free", "Quick Meals"]
    difficulties = ["Easy", "Medium", "Hard"]
    continents = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"]
    seasons = ["Spring", "Summer", "Autumn", "Winter", "All Seasons"]
    
    if request.method == 'POST':
        keyword = request.form.get('keyword', '')
        country = request.form.get('country', '')
        continent = request.form.get('continent', '')
        category = request.form.get('category', '')
        difficulty = request.form.get('difficulty', '')
        season = request.form.get('season', '')
        max_time = request.form.get('max_time', type=int)
        
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        query = "SELECT id, country, name, ingredients, category, image_path, rating FROM recipes WHERE approved = 1"
        params = []
        if keyword:
            query += " AND (name LIKE ? OR ingredients LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if country:
            query += " AND country LIKE ?"
            params.append(f"%{country}%")
        if continent:
            query += " AND continent = ?"
            params.append(continent)
        if category:
            query += " AND category = ?"
            params.append(category)
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        if season:
            query += " AND season = ?"
            params.append(season)
        if max_time:
            query += " AND prep_time <= ?"
            params.append(max_time)
        
        c.execute(query, params)
        results_raw = c.fetchall()
        results = [(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]) if r[5] and r[5] != '[]' and r[5] != '' else [], r[6]) for r in results_raw]
        conn.close()
        return render_template('search_results.html', results=results, keyword=keyword)
    return render_template('search.html', categories=categories, difficulties=difficulties, continents=continents, seasons=seasons)

# API للبحث الديناميكي
@app.route('/api/search', methods=['GET'])
@login_required
def search_api():
    keyword = request.args.get('keyword', '')
    country = request.args.get('country', '')
    continent = request.args.get('continent', '')
    category = request.args.get('category', '')
    max_time = request.args.get('max_time', type=int)
    min_calories = request.args.get('min_calories', type=int)
    max_calories = request.args.get('max_calories', type=int)
    
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    query = "SELECT id, country, name, category, image_path FROM recipes WHERE approved = 1"
    params = []
    if keyword:
        query += " AND (name LIKE ? OR ingredients LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if country:
        query += " AND country LIKE ?"
        params.append(f"%{country}%")
    if continent:
        query += " AND continent = ?"
        params.append(continent)
    if category:
        query += " AND category = ?"
        params.append(category)
    if max_time:
        query += " AND prep_time <= ?"
        params.append(max_time)
    if min_calories:
        query += " AND calories >= ?"
        params.append(min_calories)
    if max_calories:
        query += " AND calories <= ?"
        params.append(max_calories)
    
    c.execute(query, params)
    results_raw = c.fetchall()
    results = [(r[0], r[1], r[2], r[3], json.loads(r[4]) if r[4] and r[4] != '[]' and r[4] != '' else []) for r in results_raw]
    conn.close()
    return jsonify([{'id': r[0], 'country': r[1], 'name': r[2], 'category': r[3], 'image': r[4][0] if r[4] and len(r[4]) > 0 else None} for r in results])

# API لجلب الوصفات
@app.route('/api/recipes')
@login_required
def get_recipes():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes WHERE approved = 1")
    recipes = c.fetchall()
    conn.close()
    return jsonify([{'id': r[0], 'name': r[1]} for r in recipes])

# خطة الوجبات الأسبوعية
@app.route('/meal_planner', methods=['GET', 'POST'])
@login_required
def meal_planner():
    if request.method == 'POST':
        plan = {}
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            plan[day] = request.form.get(f'{day}_recipe', '')
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        c.execute("SELECT id, name, ingredients FROM recipes WHERE id IN ({})".format(','.join(['?' for _ in plan.values() if plan.values()])), [v for v in plan.values() if v])
        recipes = c.fetchall()
        shopping_list = {}
        for recipe in recipes:
            for ing in recipe[2].split(', '):
                shopping_list[ing] = shopping_list.get(ing, 0) + 1
        conn.close()
        return render_template('meal_planner.html', plan=plan, shopping_list=shopping_list)
    return render_template('meal_planner.html', plan=None, shopping_list=None)

# صفحة المجتمع
@app.route('/community')
@login_required
def community():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT content, username, timestamp, post_id, likes, community_posts.user_id FROM community_posts JOIN users ON community_posts.user_id = users.id ORDER BY timestamp DESC")
    posts = c.fetchall()
    conn.close()
    return render_template('community.html', posts=posts)

@app.route('/add_community_post', methods=['POST'])
@login_required
def add_community_post():
    content = request.form['content']
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("INSERT INTO community_posts (user_id, content, timestamp, likes) VALUES (?, ?, ?, 0)", 
              (current_user.id, content, datetime.datetime.now()))
    conn.commit()
    conn.close()
    flash('Your cooking tip has been shared!', 'success')
    return redirect(url_for('community'))

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM community_posts WHERE post_id = ?", (post_id,))
    if c.fetchone()[0] == 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Post not found'}), 404
    c.execute("UPDATE community_posts SET likes = likes + 1 WHERE post_id = ?", (post_id,))
    conn.commit()
    c.execute("SELECT likes FROM community_posts WHERE post_id = ?", (post_id,))
    likes = c.fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'likes': likes})

@app.route('/edit_community_post/<int:post_id>', methods=['POST'])
@login_required
def edit_community_post(post_id):
    content = request.form['content']
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM community_posts WHERE post_id = ?", (post_id,))
    post = c.fetchone()
    if not post or str(post[0]) != str(current_user.id):
        conn.close()
        flash('You can only edit your own posts!', 'danger')
        return redirect(url_for('community'))
    c.execute("UPDATE community_posts SET content = ?, timestamp = ? WHERE post_id = ?", 
              (content, datetime.datetime.now(), post_id))
    conn.commit()
    conn.close()
    flash('Your cooking tip has been updated!', 'success')
    return redirect(url_for('community'))

@app.route('/delete_community_post/<int:post_id>', methods=['POST'])
@login_required
def delete_community_post(post_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM community_posts WHERE post_id = ?", (post_id,))
    post = c.fetchone()
    if not post or str(post[0]) != str(current_user.id):  # تحويل إلى نصوص لضمان التطابق
        conn.close()
        flash('You can only delete your own posts!', 'danger')
        return redirect(url_for('community'))
    c.execute("DELETE FROM community_posts WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()
    flash('Your cooking tip has been deleted!', 'success')
    return redirect(url_for('community'))

# متابعة مستخدم
@app.route('/follow/<user_id>', methods=['POST'])
@login_required
def follow(user_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("INSERT INTO followers (follower_id, followed_id, date_followed) VALUES (?, ?, ?)",
              (current_user.id, user_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    flash(f"You are now following user {user_id}!", "success")
    return redirect(url_for('community'))

# إلغاء متابعة مستخدم
@app.route('/unfollow/<user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("DELETE FROM followers WHERE follower_id = ? AND followed_id = ?", (current_user.id, user_id))
    conn.commit()
    conn.close()
    flash(f"You have unfollowed user {user_id}.", "success")
    return redirect(url_for('community'))

# تعليم الإشعار كمقروء
@app.route('/mark_notification_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?", (notif_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('community'))

# توصيات شخصية
@app.route('/recommendations')
@login_required
def recommendations():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    
    c.execute("SELECT ingredients FROM recipes WHERE user_id = ? OR id IN (SELECT recipe_id FROM favorites WHERE user_id = ?)", (current_user.id, current_user.id))
    user_recipes = c.fetchall()
    
    if not user_recipes:
        flash("Add some recipes or favorites to get personalized recommendations!", "info")
        return redirect(url_for('index'))
    
    user_ingredients = " ".join([r[0] for r in user_recipes])
    c.execute("SELECT id, country, name, ingredients, category, image_path FROM recipes WHERE approved = 1 AND user_id != ?", (current_user.id,))
    all_recipes_raw = c.fetchall()
    all_recipes = [(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]) if r[5] and r[5] != '[]' and r[5] != '' else []) for r in all_recipes_raw]
    
    recipe_texts = [f"{r[3]}" for r in all_recipes]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(recipe_texts)
    user_vector = vectorizer.transform([user_ingredients])
    similarities = cosine_similarity(user_vector, tfidf_matrix).flatten()
    top_indices = similarities.argsort()[-5:][::-1]
    
    recommendations = [all_recipes[i] for i in top_indices]
    conn.close()
    return render_template('recommendations.html', recommendations=recommendations)

# إنشاء رمز QR
@app.route('/qr/<int:recipe_id>')
@login_required
def generate_qr(recipe_id):
    url = url_for('recipe_detail', recipe_id=recipe_id, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# صفحة المدونة
@app.route('/blog')
def blog():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT b.id, b.title, b.content, u.username, b.date, b.related_recipe_id, r.name FROM blog_posts b JOIN users u ON b.author_id = u.id LEFT JOIN recipes r ON b.related_recipe_id = r.id")
    posts = c.fetchall()
    conn.close()
    is_owner = current_user.is_authenticated and current_user.username == "Mohammad Wissam AL_Zoubi 123"
    return render_template('blog.html', posts=posts, is_owner=is_owner)

# إضافة مقالة جديدة (للمالك فقط)
@app.route('/add_post', methods=['GET', 'POST'])
@login_required
def add_post():
    if current_user.username != "Mohammad Wissam AL_Zoubi 123":
        flash("Only the owner can add blog posts!", "danger")
        return redirect(url_for('blog'))
    
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM recipes WHERE approved = 1")
    recipes = c.fetchall()
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        related_recipe_id = request.form.get('related_recipe_id', '')
        if related_recipe_id == "":
            related_recipe_id = None
        
        c.execute("INSERT INTO blog_posts (title, content, author_id, date, related_recipe_id) VALUES (?, ?, ?, ?, ?)",
                  (title, content, current_user.id, datetime.datetime.now().strftime("%Y-%m-%d"), related_recipe_id))
        conn.commit()
        conn.close()
        flash("Blog post added successfully!", "success")
        return redirect(url_for('blog'))
    
    conn.close()
    return render_template('add_post.html', recipes=recipes)

# صفحة المسابقات
@app.route('/contests', methods=['GET', 'POST'])
@login_required
def contests():
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        recipe_id = request.form['recipe_id']
        contest_id = request.form['contest_id']
        c.execute("INSERT INTO contest_entries (contest_id, recipe_id, user_id) VALUES (?, ?, ?)", (contest_id, recipe_id, current_user.id))
        conn.commit()
    
    c.execute("SELECT id, title, start_date, end_date, winner_id FROM contests WHERE end_date > ?", (datetime.datetime.now().strftime("%Y-%m-%d"),))
    active_contests = c.fetchall()
    c.execute("SELECT ce.id, c.title, r.name, u.username, ce.votes, ce.recipe_id, r.image_path FROM contest_entries ce JOIN contests c ON ce.contest_id = c.id JOIN recipes r ON ce.recipe_id = r.id JOIN users u ON ce.user_id = u.id")
    entries_raw = c.fetchall()
    entries = [(e[0], e[1], e[2], e[3], e[4], e[5], json.loads(e[6]) if e[6] and e[6] != '[]' and e[6] != '' else []) for e in entries_raw]
    c.execute("SELECT id, name FROM recipes WHERE user_id = ?", (current_user.id,))
    user_recipes = c.fetchall()
    conn.close()
    return render_template('contests.html', active_contests=active_contests, entries=entries, user_recipes=user_recipes)

@app.route('/vote/<int:entry_id>', methods=['POST'])
@login_required
def vote(entry_id):
    conn = sqlite3.connect('recipes.db')
    c = conn.cursor()
    c.execute("UPDATE contest_entries SET votes = votes + 1 WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    flash("Your vote has been recorded!", "success")
    return redirect(url_for('contests'))

# صفحة التبرع
@app.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        conn = sqlite3.connect('recipes.db')
        c = conn.cursor()
        c.execute("INSERT INTO donations (user_id, amount, date) VALUES (?, ?, ?)",
                  (current_user.id, amount, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        flash(f"Thank you for your donation of ${amount}!", "success")
        return redirect(url_for('index'))
    return render_template('donate.html')

if __name__ == '__main__':
    app.run(debug=True)