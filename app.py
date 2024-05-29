from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import sqlite3 as sql
import json
import requests

app = Flask(__name__)

DATABASE_FILE = "database.db"
BUGGY_RACE_SERVER_URL = "https://rhul.buggyrace.net"
API_KEY = "9B5135151EC1C57F"
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_FILE}'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # New attribute for admin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with open('defaults.json') as f:
    default_values = json.load(f)

with open('specs.json') as f:
    options2 = json.load(f)

def load_options():
    global options2
    if options2 is None:
        with open('specs.json') as f:
            options2 = json.load(f)
    return options2

def calculate_total_cost(options, armour, power_type, attack, special, tyres):
    total_cost = 0
    if armour in options['armour']:
        total_cost += options['armour'][armour]['cost']
    if power_type in options['power_type']:
        total_cost += options['power_type'][power_type]['cost']
    if attack in options['attack']:
        total_cost += options['attack'][attack]['cost']
    if special in options['special']:
        total_cost += options['special'][special]['cost']
    if tyres in options['tyres']:
        total_cost += options['tyres'][tyres]['cost']
    return total_cost

def validate_buggy_data(data, options):
    qty_wheels = int(data['qty_wheels'])
    qty_tyres = int(data['qty_tyres'])
    power_type = data['power_type']
    power_units = int(data['power_units'])
    flag_color = data['flag_color']
    flag_color_secondary = data['flag_color_secondary']

    if qty_wheels < 4 or qty_wheels % 2 != 0:
        return "Number of wheels must be an even number and at least 4."
    if qty_tyres < qty_wheels:
        return "Number of tyres must be equal to or greater than the number of wheels."
    if power_type == 'none':
        return "Primary motive power must not be none."
    if power_units < 1:
        return "Number of primary motive power units must be at least 1."
    if flag_color == flag_color_secondary:
        return "Flag color and secondary color must be different."
    
    return None

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/index', methods=['GET'])
@login_required
def index():
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    if current_user.is_admin:
        cur.execute("SELECT * FROM buggies")
    else:
        cur.execute("SELECT * FROM buggies WHERE user_id = ?", (current_user.id,))
    buggies = cur.fetchall()
    return render_template('index.html', server_url=BUGGY_RACE_SERVER_URL, buggies=buggies)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data['username']
        password = data['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return jsonify({"message": "Login successful"}), 200
        return jsonify({"message": "Invalid credentials"}), 401
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(username=username, email=email, password=password)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error during signup: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 400

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/new', methods=['POST', 'GET'])
@login_required
def create_buggy():
    if request.method == 'GET':
        options = load_options()
        return render_template("buggy-form.html", options=options, edit_mode=False)
    elif request.method == 'POST':
        data = request.form.to_dict()
        msg = validate_buggy_data(data, load_options())
        if msg:
            options = load_options()
            return render_template("buggy-form.html", msg=msg, options=options, **data, edit_mode=False)

        name = data['name']
        qty_wheels = data['qty_wheels']
        flag_color = data['flag_color']
        flag_color_secondary = data['flag_color_secondary']
        flag_pattern = data.get('flag_pattern', 'plain')
        armour = data.get('armour', 'none')
        power_type = data['power_type']
        power_units = data['power_units']
        attack = data.get('attack', 'none')
        tyres = data['tyres']
        qty_tyres = data['qty_tyres']
        fireproof = 'fireproof' in data
        insulated = 'insulated' in data
        antibiotic = 'antibiotic' in data
        banging = 'banging' in data
        algo = data['algo']

        options = load_options()
        total_cost = calculate_total_cost(
            options, armour=armour, power_type=power_type, attack=attack, special='none', tyres=tyres
        )

        try:
            with sql.connect(DATABASE_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    """INSERT INTO buggies (user_id, name, qty_wheels, flag_color, flag_color_secondary, flag_pattern, 
                    armour, power_type, power_units, attack, tyres, qty_tyres, total_cost, fireproof, insulated, antibiotic, banging, algo) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (current_user.id, name, qty_wheels, flag_color, flag_color_secondary, flag_pattern, armour, power_type, power_units, attack, tyres, qty_tyres, total_cost, fireproof, insulated, antibiotic, banging, algo)
                )
                con.commit()
                msg = "Record successfully saved"
        except Exception as e:
            con.rollback()
            msg = f"Error in insert operation: {str(e)}"
        finally:
            con.close()
        return render_template("updated.html", msg=msg)

@app.route('/update/<int:buggy_id>', methods=['POST', 'GET'])
@login_required
def update_buggy(buggy_id):
    if request.method == 'GET':
        try:
            with sql.connect(DATABASE_FILE) as con:
                cur = con.cursor()
                cur.execute("SELECT * FROM buggies WHERE id = ?", (buggy_id,))
                buggy = cur.fetchone()
                if buggy is None or (buggy['user_id'] != current_user.id and not current_user.is_admin):
                    msg = f"No buggy found with ID {buggy_id} or you do not have permission to edit it"
                    return render_template("error.html", msg=msg)
                
                buggy_data = {
                    'name': buggy[2],
                    'qty_wheels': buggy[3],
                    'flag_color': buggy[4],
                    'flag_color_secondary': buggy[5],
                    'flag_pattern': buggy[6],
                    'armour': buggy[7],
                    'power_type': buggy[8],
                    'power_units': buggy[9],
                    'attack': buggy[10],
                    'tyres': buggy[11],
                    'qty_tyres': buggy[12],
                    'fireproof': buggy[13],
                    'insulated': buggy[14],
                    'antibiotic': buggy[15],
                    'banging': buggy[16],
                    'algo': buggy[17],
                }
                
                options = load_options()
                return render_template("buggy-form.html", options=options, edit_mode=True, buggy_id=buggy_id, **buggy_data)
        except Exception as e:
            msg = f"Error loading buggy data: {str(e)}"
            return render_template("error.html", msg=msg)

    elif request.method == 'POST':
        data = request.form.to_dict()
        msg = validate_buggy_data(data, load_options())
        if msg:
            options = load_options()
            return render_template("buggy-form.html", msg=msg, options=options, edit_mode=True, buggy_id=buggy_id, **data)

        name = data['name']
        qty_wheels = data['qty_wheels']
        flag_color = data['flag_color']
        flag_color_secondary = data['flag_color_secondary']
        flag_pattern = data.get('flag_pattern', 'plain')
        armour = data.get('armour', 'none')
        power_type = data['power_type']
        power_units = data['power_units']
        attack = data.get('attack', 'none')
        tyres = data['tyres']
        qty_tyres = data['qty_tyres']
        fireproof = 'fireproof' in data
        insulated = 'insulated' in data
        antibiotic = 'antibiotic' in data
        banging = 'banging' in data
        algo = data['algo']

        options = load_options()
        total_cost = calculate_total_cost(
            options, armour=armour, power_type=power_type, attack=attack, special='none', tyres=tyres
        )

        try:
            with sql.connect(DATABASE_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    """UPDATE buggies SET name=?, qty_wheels=?, flag_color=?, flag_color_secondary=?, flag_pattern=?, 
                    armour=?, power_type=?, power_units=?, attack=?, tyres=?, qty_tyres=?, total_cost=?, fireproof=?, insulated=?, antibiotic=?, banging=?, algo=? 
                    WHERE id=? AND (user_id=? OR ?=1)""",
                    (name, qty_wheels, flag_color, flag_color_secondary, flag_pattern, armour, power_type, power_units, attack, tyres, qty_tyres, total_cost, fireproof, insulated, antibiotic, banging, algo, buggy_id, current_user.id, current_user.is_admin)
                )
                con.commit()
                msg = "Record successfully updated"
        except Exception as e:
            con.rollback()
            msg = f"Error in update operation: {str(e)}"
        finally:
            con.close()
        return render_template("updated.html", msg=msg)

@app.route('/buggy/<int:buggy_id>')
def show_buggy(buggy_id):
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM buggies WHERE id=?", (buggy_id,))
    record = cur.fetchone()
    return render_template("buggy.html", buggy=record)

@app.route('/edit', methods=['GET'])
@login_required
def select_buggy_to_edit():
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    if current_user.is_admin:
        cur.execute("SELECT id, name FROM buggies")
    else:
        cur.execute("SELECT id, name FROM buggies WHERE user_id = ?", (current_user.id,))
    buggies = cur.fetchall()
    return render_template('edit-select.html', buggies=buggies)

@app.route('/edit/<int:buggy_id>', methods=['POST', 'GET'])
@login_required
def edit_buggy(buggy_id):
    if request.method == 'GET':
        try:
            with sql.connect(DATABASE_FILE) as con:
                con.row_factory = sql.Row
                cur = con.cursor()
                cur.execute("SELECT * FROM buggies WHERE id=? AND (user_id=? OR ?=1)", (buggy_id, current_user.id, current_user.is_admin))
                buggy = cur.fetchone()
                if buggy:
                    data = dict(buggy)
                else:
                    data = default_values
        except Exception as e:
            data = default_values
            print(f"Error fetching buggy data: {e}")

        options = load_options()
        return render_template("buggy-form.html", **data, options=options2, edit_mode=True, buggy_id=buggy_id)
    elif request.method == 'POST':
        data = request.form.to_dict()
        msg = validate_buggy_data(data, load_options())
        if msg:
            options = load_options()
            return render_template("buggy-form.html", msg=msg, options=options2, **data, edit_mode=True, buggy_id=buggy_id)

        name = data['name']
        qty_wheels = data['qty_wheels']
        flag_color = data['flag_color']
        flag_color_secondary = data['flag_color_secondary']
        flag_pattern = data.get('flag_pattern', 'plain')
        armour = data.get('armour', 'none')
        power_type = data['power_type']
        power_units = data['power_units']
        attack = data.get('attack', 'none')
        tyres = data['tyres']
        qty_tyres = data['qty_tyres']
        fireproof = 'fireproof' in data
        insulated = 'insulated' in data
        antibiotic = 'antibiotic' in data
        banging = 'banging' in data
        algo = data['algo']

        
        total_cost = calculate_total_cost(
            options, armour=armour, power_type=power_type, attack=attack, special='none', tyres=tyres
        )

        try:
            with sql.connect(DATABASE_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    """UPDATE buggies SET name=?, qty_wheels=?, flag_color=?, flag_color_secondary=?, flag_pattern=?, 
                    armour=?, power_type=?, power_units=?, attack=?, tyres=?, qty_tyres=?, total_cost=?, fireproof=?, insulated=?, antibiotic=?, banging=?, algo=? WHERE id=? AND (user_id=? OR ?=1)""",
                    (name, qty_wheels, flag_color, flag_color_secondary, flag_pattern, armour, power_type, power_units, attack, tyres, qty_tyres, total_cost, fireproof, insulated, antibiotic, banging, algo, buggy_id, current_user.id, current_user.is_admin)
                )
                con.commit()
                msg = "Record successfully updated"
        except Exception as e:
            con.rollback()
            msg = f"Error in update operation: {str(e)}"
        finally:
            con.close()
        return render_template("updated.html", msg=msg)

@app.route('/poster', methods=['GET'])
def poster():
    return render_template('poster.html')

@app.route('/json-select')
def json():
    return render_template('json-select.html')

@app.route('/json/<string:buggy_id>')
def summary(buggy_id):
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM buggies WHERE id=? LIMIT 1", (buggy_id,))
    record = cur.fetchone()
    buggies = dict(zip([column[0] for column in cur.description], record)).items() 
    return jsonify({ key: val for key, val in buggies if (val != "" and val is not None) })

@app.route('/defaults', methods=['GET'])
def get_defaults():
    return jsonify(default_values)

@app.route('/delete/<int:buggy_id>', methods=['POST'])
@login_required
def delete_buggy(buggy_id):
    try:
        with sql.connect(DATABASE_FILE) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM buggies WHERE id = ? AND (user_id=? OR ?=1)", (buggy_id, current_user.id, current_user.is_admin))
            con.commit()
            msg = "Buggy successfully deleted"
    except Exception as e:
        con.rollback()
        msg = f"Error in delete operation: {str(e)}"
    finally:
        con.close()
    return redirect(url_for('select_buggy_to_edit'))

@app.route('/submit_buggy_json', methods=['POST'])
@login_required
def submit_buggy_json():
    data = request.get_json()
    buggy_id = data.get('buggy_id')
    api_secret = data.get('api_secret')

    if not buggy_id or not api_secret:
        return jsonify({"message": "Buggy ID and API secret are required"}), 400

    try:
        with sql.connect(DATABASE_FILE) as con:
            con.row_factory = sql.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM buggies WHERE id=? AND (user_id=? OR ?=1)", (buggy_id, current_user.id, current_user.is_admin))
            buggy = cur.fetchone()
            if buggy is None:
                return jsonify({"message": "Buggy not found or you do not have permission to submit this buggy"}), 404
            
            buggy_dict = {
                key: value for key, value in dict(buggy).items() if value is not None and value != ""
            }
            buggy_json = json.dumps(buggy_dict)
            
            payload = {
                'user': 'thomas',
                'key': API_KEY,
                'secret': api_secret,
                'buggy_json': buggy_json
            }

            print(f"user: {payload['user']}")
            print(f"key: {payload['key']}")
            print(f"secret: {payload['secret']}")
            print(f"buggy_json: {payload['buggy_json']}")

            response = requests.post(
                f"https://rhul.buggyrace.net/api/upload",
                data=payload 
            )
            
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Text: {response.text}")

            if response.status_code == 200:
                return jsonify({"message": "Buggy JSON submitted successfully!"}), 200
            else:
                return jsonify({"message": f"Failed to submit Buggy JSON: {response.text}"}), response.status_code
    except Exception as e:
        print(f"Error submitting Buggy JSON: {str(e)}")
        return jsonify({"message": f"Error submitting Buggy JSON: {str(e)}"}), 500

@app.route('/buggy-config/<int:buggy_id>', methods=['GET'])
def get_buggy_config(buggy_id):
    try:
        with sql.connect(DATABASE_FILE) as con:
            con.row_factory = sql.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM buggies WHERE id=?", (buggy_id,))
            buggy = cur.fetchone()
            if buggy is None:
                return jsonify({"message": "Buggy not found"}), 404

            buggy_dict = dict(buggy)
            return jsonify(buggy_dict)
    except Exception as e:
        print(f"Error fetching buggy config: {str(e)}")
        return jsonify({"message": f"Error fetching buggy config: {str(e)}"}), 500

if __name__ == '__main__':
    alloc_port = os.environ.get('CS1999_PORT') or 5102
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=alloc_port)
