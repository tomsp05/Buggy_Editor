import pytest
from app import app, db, User, Buggy, calculate_total_cost, validate_buggy_data

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_calculate_total_cost():
    options = {
        "armour": {"none": {"cost": 0}, "metal": {"cost": 50}},
        "power_type": {"electric": {"cost": 80}, "petrol": {"cost": 70}},
        "attack": {"none": {"cost": 0}, "spikes": {"cost": 30}},
        "special": {"none": {"cost": 0}, "jet": {"cost": 100}},
        "tyres": {"regular": {"cost": 20}, "off-road": {"cost": 40}}
    }
    
    total_cost = calculate_total_cost(options, "metal", "electric", "spikes", "none", "off-road")
    assert total_cost == 200

def test_validate_buggy_data():
    options = {
        "armour": {"none": {"cost": 0}, "metal": {"cost": 50}},
        "power_type": {"electric": {"cost": 80}, "petrol": {"cost": 70}},
        "attack": {"none": {"cost": 0}, "spikes": {"cost": 30}},
        "special": {"none": {"cost": 0}, "jet": {"cost": 100}},
        "tyres": {"regular": {"cost": 20}, "off-road": {"cost": 40}}
    }
    
    data = {
        "qty_wheels": 4,
        "qty_tyres": 4,
        "power_type": "electric",
        "power_units": 1,
        "flag_color": "red",
        "flag_color_secondary": "blue"
    }
    
    assert validate_buggy_data(data, options) is None
    
    data["qty_wheels"] = 3
    assert validate_buggy_data(data, options) == "Number of wheels must be an even number and at least 4."
    data["qty_wheels"] = 4
    data["qty_tyres"] = 2
    assert validate_buggy_data(data, options) == "Number of tyres must be equal to or greater than the number of wheels."
    data["qty_tyres"] = 4
    data["flag_color"] = "red"
    data["flag_color_secondary"] = "red"
    assert validate_buggy_data(data, options) == "Flag color and secondary color must be different."

def test_user_creation(client):
    response = client.post('/signup', json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpassword",
        "admin": False
    })
    assert response.status_code == 201
    assert b"User created" in response.data

def test_user_login(client):
    client.post('/signup', json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpassword",
        "admin": False
    })
    response = client.post('/login', json={
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert b"Login successful" in response.data

if __name__ == '__main__':
    pytest.main()
