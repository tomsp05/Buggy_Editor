import sqlite3

DATABASE_FILE = 'database.db'

connection = sqlite3.connect(DATABASE_FILE)
print(f"Opened database successfully in file {DATABASE_FILE}")

# Drop the existing 'buggies' table (if it exists) and create a new one with the updated schema
connection.execute("DROP TABLE IF EXISTS buggies")
connection.execute("""
CREATE TABLE buggies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, -- Foreign key to associate buggy with a user
    name VARCHAR(20),
    qty_wheels INTEGER DEFAULT 4 CHECK(qty_wheels >= 4 AND qty_wheels % 2 = 0),
    flag_color VARCHAR(20),
    flag_color_secondary VARCHAR(20),
    flag_pattern VARCHAR(20),
    armour VARCHAR(20),
    power_type VARCHAR(20) CHECK(power_type != 'none'),
    power_units INTEGER DEFAULT 1 CHECK(power_units >= 1),
    aux_power_type VARCHAR(20),
    aux_power_units INTEGER DEFAULT 0,
    hamster_booster INTEGER DEFAULT 0,
    tyres VARCHAR(20),
    qty_tyres INTEGER DEFAULT 4 CHECK(qty_tyres >= qty_wheels),
    attack VARCHAR(20),
    qty_attacks INTEGER DEFAULT 0,
    fireproof BOOLEAN DEFAULT false,
    insulated BOOLEAN DEFAULT false,
    antibiotic BOOLEAN DEFAULT false,
    banging BOOLEAN DEFAULT false,
    special VARCHAR(20) DEFAULT 'none',
    algo VARCHAR(20),
    total_cost INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) -- Define the foreign key constraint
)
""")
print("OK, table 'buggies' exists")

# Optionally, insert a default buggy if the table is empty
cursor = connection.cursor()

cursor.execute("SELECT * FROM buggies LIMIT 1")
rows = cursor.fetchall()
if len(rows) == 0:
    cursor.execute("""
        INSERT INTO buggies (
            user_id, name, qty_wheels, flag_color, flag_color_secondary, flag_pattern,
            armour, power_type, power_units, aux_power_type, aux_power_units,
            hamster_booster, tyres, qty_tyres, attack, qty_attacks, fireproof,
            insulated, antibiotic, banging, special, algo, total_cost
        ) VALUES (
            1, 'Default Buggy', 4, 'white', 'black', 'plain', 'none', 'petrol', 1, 'none', 0,
            0, 'knobbly', 4, 'none', 0, false, false, false, false, 'none', 'steady', 0
        )
    """)
    connection.commit()
    print("Added one default buggy")
else:
    print("Found a buggy in the database, nice")

connection.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(150) NOT NULL
)
""")
print("OK, table 'users' exists")

print("OK, your database is ready")
connection.close()