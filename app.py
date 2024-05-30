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
    is_admin = db.Column(db.Boolean, default=0)

class Buggy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    qty_wheels = db.Column(db.Integer, nullable=False)
    flag_color = db.Column(db.String(20), nullable=False)
    flag_color_secondary = db.Column(db.String(20), nullable=False)
    flag_pattern = db.Column(db.String(20), default='plain')
    armour = db.Column(db.String(50), default='none')
    power_type = db.Column(db.String(50), nullable=False)
    power_units = db.Column(db.Integer, nullable=False)
    attack = db.Column(db.String(50), default='none')
    tyres = db.Column(db.String(50), nullable=False)
    qty_tyres = db.Column(db.Integer, nullable=False)
    fireproof = db.Column(db.Boolean, default=False)
    insulated = db.Column(db.Boolean, default=False)
    antibiotic = db.Column(db.Boolean, default=False)
    banging = db.Column(db.Boolean, default=False)
    algo = db.Column(db.String(50), default='none')
    total_cost = db.Column(db.Integer, nullable=False)

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
    if current_user.is_admin:
        buggies = Buggy.query.all()
    else:
        buggies = Buggy.query.filter_by(user_id=current_user.id).all()
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
    admin = data.get('admin', False)
    password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    print(admin)
    new_user = User(username=username, email=email, password=password, is_admin=admin)
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
            new_buggy = Buggy(
                user_id=current_user.id, 
                name=name, 
                qty_wheels=qty_wheels, 
                flag_color=flag_color, 
                flag_color_secondary=flag_color_secondary,
                flag_pattern=flag_pattern, 
                armour=armour, 
                power_type=power_type, 
                power_units=power_units, 
                attack=attack, 
                tyres=tyres, 
                qty_tyres=qty_tyres, 
                total_cost=total_cost, 
                fireproof=fireproof, 
                insulated=insulated, 
                antibiotic=antibiotic, 
                banging=banging, 
                algo=algo
            )
            db.session.add(new_buggy)
            db.session.commit()
            msg = "Record successfully saved"
        except Exception as e:
            db.session.rollback()
            msg = f"Error in insert operation: {str(e)}"
        return render_template("updated.html", msg=msg)

@app.route('/update/<int:buggy_id>', methods=['POST', 'GET'])
@login_required
def update_buggy(buggy_id):
    if request.method == 'GET':
        try:
            buggy = Buggy.query.get(buggy_id)
            if buggy is None or (buggy.user_id != current_user.id and not current_user.is_admin):
                msg = f"No buggy found with ID {buggy_id} or you do not have permission to edit it"
                return render_template("error.html", msg=msg)
                
            buggy_data = {
                'name': buggy.name,
                'qty_wheels': buggy.qty_wheels,
                'flag_color': buggy.flag_color,
                'flag_color_secondary': buggy.flag_color_secondary,
                'flag_pattern': buggy.flag_pattern,
                'armour': buggy.armour,
                'power_type': buggy.power_type,
                'power_units': buggy.power_units,
                'attack': buggy.attack,
                'tyres': buggy.tyres,
                'qty_tyres': buggy.qty_tyres,
                'fireproof': buggy.fireproof,
                'insulated': buggy.insulated,
                'antibiotic': buggy.antibiotic,
                'banging': buggy.banging,
                'algo': buggy.algo,
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
            buggy = Buggy.query.get(buggy_id)
            if buggy.user_id != current_user.id and not current_user.is_admin:
                msg = "You do not have permission to update this buggy"
                return render_template("error.html", msg=msg)
            
            buggy.name = name
            buggy.qty_wheels = qty_wheels
            buggy.flag_color = flag_color
            buggy.flag_color_secondary = flag_color_secondary
            buggy.flag_pattern = flag_pattern
            buggy.armour = armour
            buggy.power_type = power_type
            buggy.power_units = power_units
            buggy.attack = attack
            buggy.tyres = tyres
            buggy.qty_tyres = qty_tyres
            buggy.fireproof = fireproof
            buggy.insulated = insulated
            buggy.antibiotic = antibiotic
            buggy.banging = banging
            buggy.algo = algo
            buggy.total_cost = total_cost

            db.session.commit()
            msg = "Record successfully updated"
        except Exception as e:
            db.session.rollback()
            msg = f"Error in update operation: {str(e)}"
        return render_template("updated.html", msg=msg)
    
@app.route('/buggy/<int:buggy_id>')
def show_buggy(buggy_id):
    buggy = Buggy.query.get(buggy_id)
    return render_template("buggy.html", buggy=buggy)

@app.route('/edit', methods=['GET'])
@login_required
def select_buggy_to_edit():
    if current_user.is_admin:
        buggies = Buggy.query.all()
    else:
        buggies = Buggy.query.filter_by(user_id=current_user.id).all()
    return render_template('edit-select.html', buggies=buggies)


@app.route('/edit/<int:buggy_id>', methods=['POST', 'GET'])
@login_required
def edit_buggy(buggy_id):
    if request.method == 'GET':
        try:
            buggy = Buggy.query.get(buggy_id)
            if buggy is None or (buggy.user_id != current_user.id and not current_user.is_admin):
                msg = f"No buggy found with ID {buggy_id} or you do not have permission to edit it"
                return render_template("error.html", msg=msg)
                
            buggy_data = {
                'name': buggy.name,
                'qty_wheels': buggy.qty_wheels,
                'flag_color': buggy.flag_color,
                'flag_color_secondary': buggy.flag_color_secondary,
                'flag_pattern': buggy.flag_pattern,
                'armour': buggy.armour,
                'power_type': buggy.power_type,
                'power_units': buggy.power_units,
                'attack': buggy.attack,
                'tyres': buggy.tyres,
                'qty_tyres': buggy.qty_tyres,
                'fireproof': buggy.fireproof,
                'insulated': buggy.insulated,
                'antibiotic': buggy.antibiotic,
                'banging': buggy.banging,
                'algo': buggy.algo,
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
            buggy = Buggy.query.get(buggy_id)
            if buggy.user_id != current_user.id and not current_user.is_admin:
                msg = "You do not have permission to update this buggy"
                return render_template("error.html", msg=msg)
            
            buggy.name = name
            buggy.qty_wheels = qty_wheels
            buggy.flag_color = flag_color
            buggy.flag_color_secondary = flag_color_secondary
            buggy.flag_pattern = flag_pattern
            buggy.armour = armour
            buggy.power_type = power_type
            buggy.power_units = power_units
            buggy.attack = attack
            buggy.tyres = tyres
            buggy.qty_tyres = qty_tyres
            buggy.fireproof = fireproof
            buggy.insulated = insulated
            buggy.antibiotic = antibiotic
            buggy.banging = banging
            buggy.algo = algo
            buggy.total_cost = total_cost

            db.session.commit()
            msg = "Record successfully updated"
        except Exception as e:
            db.session.rollback()
            msg = f"Error in update operation: {str(e)}"
        return render_template("updated.html", msg=msg)


@app.route('/poster', methods=['GET'])
def poster():
    return render_template('poster.html')

@app.route('/json-select')
def json():
    return render_template('json-select.html')

@app.route('/json/<string:buggy_id>')
def summary(buggy_id):
    buggy = Buggy.query.get(buggy_id)
    buggy_dict = {
        key: value for key, value in buggy.__dict__.items() if value is not None and key != '_sa_instance_state'
    }
    return jsonify(buggy_dict)

@app.route('/defaults', methods=['GET'])
def get_defaults():
    return jsonify(default_values)

@app.route('/delete/<int:buggy_id>', methods=['POST'])
@login_required
def delete_buggy(buggy_id):
    try:
        buggy = Buggy.query.get(buggy_id)
        if buggy.user_id != current_user.id and not current_user.is_admin:
            return jsonify({"message": "You do not have permission to delete this buggy"}), 403
        db.session.delete(buggy)
        db.session.commit()
        msg = "Buggy successfully deleted"
    except Exception as e:
        db.session.rollback()
        msg = f"Error in delete operation: {str(e)}"
    return redirect(url_for('select_buggy_to_edit'))

@app.route('/submit_buggy_json', methods=['POST'])
@login_required
def submit_buggy_json():
    import json
    data = request.get_json()
    buggy_id = data.get('buggy_id')
    api_secret = data.get('api_secret')

    if not buggy_id or not api_secret:
        return jsonify({"message": "Buggy ID and API secret are required"}), 400

    try:
        buggy = Buggy.query.get(buggy_id)
        if buggy.user_id != current_user.id and not current_user.is_admin:
            return jsonify({"message": "You do not have permission to submit this buggy"}), 403
            
        buggy_dict = {
            key: value for key, value in buggy.__dict__.items() if value is not None and key != '_sa_instance_state'
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
        buggy = Buggy.query.get(buggy_id)
        if buggy is None:
            return jsonify({"message": "Buggy not found"}), 404

        buggy_dict = {
            key: value for key, value in buggy.__dict__.items() if value is not None and key != '_sa_instance_state'
        }
        return jsonify(buggy_dict)
    except Exception as e:
        print(f"Error fetching buggy config: {str(e)}")
        return jsonify({"message": f"Error fetching buggy config: {str(e)}"}), 500

if __name__ == '__main__':
    alloc_port = os.environ.get('CS1999_PORT') or 5102
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=alloc_port)
