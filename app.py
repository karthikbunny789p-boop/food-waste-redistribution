from flask import Flask, request, redirect, url_for, render_template_string, flash
import sqlite3
import heapq
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB_NAME = "food_redistribution.db"

# Demo road network. Edge weights are distances in km.
GRAPH = {
    "Central Kitchen": {"Market Shelter": 4, "City Home": 2},
    "Market Shelter": {"Central Kitchen": 4, "Community Center": 3},
    "City Home": {"Central Kitchen": 2, "Community Center": 2},
    "Community Center": {"Market Shelter": 3, "City Home": 2},
}

def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donor TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                expiry_hours INTEGER NOT NULL CHECK(expiry_hours > 0),
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL UNIQUE,
                need INTEGER NOT NULL CHECK(need > 0),
                capacity INTEGER NOT NULL CHECK(capacity > 0)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM centers").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO centers(name, location, need, capacity) VALUES (?, ?, ?, ?)",
                [
                    ("Market Shelter", "Market Shelter", 25, 40),
                    ("City Home", "City Home", 20, 30),
                    ("Community Center", "Community Center", 15, 25),
                ],
            )

def astar(start, goal):
    """Find shortest route with A*; zero heuristic keeps it optimal for this graph."""
    if start not in GRAPH or goal not in GRAPH:
        return None, None
    queue = [(0, 0, start, [start])]
    best_cost = {start: 0}
    while queue:
        _, cost, node, path = heapq.heappop(queue)
        if node == goal:
            return path, cost
        if cost != best_cost.get(node):
            continue
        for neighbor, weight in GRAPH[node].items():
            new_cost = cost + weight
            if new_cost < best_cost.get(neighbor, float("inf")):
                best_cost[neighbor] = new_cost
                # h(n)=0 is admissible, so this behaves like Dijkstra and stays optimal.
                heapq.heappush(queue, (new_cost, new_cost, neighbor, path + [neighbor]))
    return None, None

def build_plan():
    with connect_db() as conn:
        foods = conn.execute(
            "SELECT * FROM food WHERE status='Available' ORDER BY expiry_hours ASC, id ASC"
        ).fetchall()
        centers = [dict(row) for row in conn.execute(
            "SELECT * FROM centers ORDER BY name"
        ).fetchall()]

        # Track capacity and unmet need for this plan.
        remaining_capacity = {c["id"]: c["capacity"] for c in centers}
        remaining_need = {c["id"]: c["need"] for c in centers}
        plan = []

        for item in foods:
            available = item["quantity"]
            candidates = []
            for center in centers:
                if remaining_capacity[center["id"]] <= 0 or remaining_need[center["id"]] <= 0:
                    continue
                path, distance = astar(item["location"], center["location"])
                if path is None:
                    continue
                candidates.append((distance, center["name"], center, path))
            candidates.sort(key=lambda x: (x[0], x[1]))

            allocations = []
            for distance, _, center, path in candidates:
                amount = min(
                    available,
                    remaining_capacity[center["id"]],
                    remaining_need[center["id"]]
                )
                if amount <= 0:
                    continue
                allocations.append({
                    "center": center["name"],
                    "quantity": amount,
                    "route": path,
                    "distance": distance,
                    "expiry_hours": item["expiry_hours"],
                })
                available -= amount
                remaining_capacity[center["id"]] -= amount
                remaining_need[center["id"]] -= amount
                if available == 0:
                    break

            plan.append({
                "food_id": item["id"],
                "food": item["name"],
                "donor": item["donor"],
                "quantity": item["quantity"],
                "expiry_hours": item["expiry_hours"],
                "location": item["location"],
                "allocations": allocations,
                "unallocated": available,
            })
        return plan

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Food Redistribution Planner</title>
<style>
body{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#20252b}
header{background:#1d6b4f;color:white;padding:22px 5%}
main{max-width:1100px;margin:24px auto;padding:0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}
.card{background:white;border-radius:10px;padding:18px;box-shadow:0 2px 8px #0001;margin-bottom:18px}
h1{margin:0;font-size:26px} h2{font-size:20px;margin-top:0}
label{display:block;font-size:14px;margin:10px 0 5px}
input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccd3d8;border-radius:6px}
button,.button{display:inline-block;background:#1d6b4f;color:white;border:0;border-radius:6px;padding:10px 14px;margin-top:12px;cursor:pointer;text-decoration:none}
table{width:100%;border-collapse:collapse;background:white}
th,td{text-align:left;padding:10px;border-bottom:1px solid #e6e9ec;font-size:14px;vertical-align:top}
th{background:#edf3f0}.muted{color:#667085;font-size:13px}.notice{background:#fff4d8;padding:10px;border-radius:6px;margin-bottom:12px}
.pill{display:inline-block;padding:4px 8px;background:#e5f4eb;border-radius:20px;font-size:12px}
@media(max-width:600px){table{font-size:12px}th,td{padding:7px}}
</style>
</head>
<body>
<header><h1>AI-Based Food Waste Redistribution</h1>
<p>Surplus food allocation and A* route planning demo</p></header>
<main>
{% with messages = get_flashed_messages() %}
{% if messages %}{% for message in messages %}<div class="notice">{{message}}</div>{% endfor %}{% endif %}
{% endwith %}
<div class="notice"><b>Demo limitation:</b> routes use a sample road network and distances, not live GPS or real traffic.</div>
<div class="grid">
<section class="card">
<h2>Add Surplus Food</h2>
<form method="post" action="{{url_for('add_food')}}">
<label>Donor / Restaurant</label><input name="donor" required maxlength="80" placeholder="e.g. Green Restaurant">
<label>Food name</label><input name="name" required maxlength="80" placeholder="e.g. Rice meals">
<label>Quantity (portions)</label><input type="number" name="quantity" min="1" required>
<label>Time until expiry (hours)</label><input type="number" name="expiry_hours" min="1" required>
<label>Pickup location</label><select name="location" required>{% for loc in locations %}<option>{{loc}}</option>{% endfor %}</select>
<button type="submit">Add Food</button>
</form>
</section>
<section class="card">
<h2>Add Donation Center</h2>
<form method="post" action="{{url_for('add_center')}}">
<label>Center name</label><input name="name" required maxlength="80">
<label>Location node</label><select name="location" required>{% for loc in locations %}<option>{{loc}}</option>{% endfor %}</select>
<label>Food portions needed</label><input type="number" name="need" min="1" required>
<label>Storage capacity (portions)</label><input type="number" name="capacity" min="1" required>
<button type="submit">Add Center</button>
</form>
<p class="muted">Each center must use a unique name and location in this demo.</p>
</section>
</div>
<section class="card">
<h2>Donation Centers</h2>
<table><tr><th>Name</th><th>Location</th><th>Need</th><th>Capacity</th></tr>
{% for c in centers %}<tr><td>{{c.name}}</td><td>{{c.location}}</td><td>{{c.need}}</td><td>{{c.capacity}}</td></tr>{% else %}<tr><td colspan="4">No centers added.</td></tr>{% endfor %}
</table>
</section>
<section class="card">
<h2>Available Surplus Food</h2>
<table><tr><th>Food</th><th>Donor</th><th>Quantity</th><th>Expiry</th><th>Pickup</th><th>Status</th><th>Action</th></tr>
{% for f in foods %}<tr><td>{{f.name}}</td><td>{{f.donor}}</td><td>{{f.quantity}}</td><td>{{f.expiry_hours}} h</td><td>{{f.location}}</td><td><span class="pill">{{f.status}}</span></td><td>{% if f.status == 'Available' %}<form method="post" action="{{url_for('mark_distributed', food_id=f.id)}}" onsubmit="return confirm('Mark this food as distributed?')"><button type="submit">Mark distributed</button></form>{% else %}—{% endif %}</td></tr>
{% else %}<tr><td colspan="7">No food records yet.</td></tr>{% endfor %}
</table>
</section>
<section class="card">
<h2>Generate Redistribution Plan</h2>
<p class="muted">The planner prioritizes food expiring sooner, then allocates portions to centers with unmet need and available capacity, preferring the shortest route.</p>
<a class="button" href="{{url_for('plan')}}">Generate Plan</a>
</section>
{% if plan is not none %}
<section class="card">
<h2>Generated Plan</h2>
{% for p in plan %}
<div class="card">
<h3>{{p.food}} — {{p.quantity}} portions</h3>
<p class="muted">Donor: {{p.donor}} | Expires in {{p.expiry_hours}} hours | Pickup: {{p.location}}</p>
{% if p.allocations %}
<table><tr><th>Donation center</th><th>Allocated</th><th>Route</th><th>Distance</th></tr>
{% for a in p.allocations %}<tr><td>{{a.center}}</td><td>{{a.quantity}} portions</td><td>{{a.route|join(' → ')}}</td><td>{{a.distance}} km</td></tr>{% endfor %}</table>
{% else %}<p>No eligible center found for this food's pickup location.</p>{% endif %}
{% if p.unallocated %}<p class="notice">{{p.unallocated}} portions remain unallocated because center need/capacity is insufficient.</p>{% endif %}
</div>
{% else %}<p>No available food records. Add food first.</p>{% endfor %}
</section>
{% endif %}
<p class="muted">Academic prototype only. Verify food safety, storage conditions, recipient consent, and local food donation requirements before real-world use.</p>
</main>
</body></html>
"""

def render_page(plan=None):
    with connect_db() as conn:
        foods = conn.execute("SELECT * FROM food ORDER BY id DESC").fetchall()
        centers = conn.execute("SELECT * FROM centers ORDER BY name").fetchall()
    return render_template_string(
        PAGE, foods=foods, centers=centers, locations=sorted(GRAPH.keys()), plan=plan
    )

@app.route("/")
def index():
    return render_page()

@app.route("/food", methods=["POST"])
def add_food():
    try:
        quantity = int(request.form["quantity"])
        expiry = int(request.form["expiry_hours"])
        if quantity < 1 or expiry < 1:
            raise ValueError
        with connect_db() as conn:
            conn.execute(
                "INSERT INTO food(donor,name,quantity,expiry_hours,location) VALUES(?,?,?,?,?)",
                (request.form["donor"].strip(), request.form["name"].strip(),
                 quantity, expiry, request.form["location"])
            )
        flash("Food record added successfully.")
    except (ValueError, KeyError):
        flash("Enter a valid positive quantity and expiry time.")
    return redirect(url_for("index"))

@app.route("/center", methods=["POST"])
def add_center():
    try:
        need, capacity = int(request.form["need"]), int(request.form["capacity"])
        if need < 1 or capacity < 1:
            raise ValueError
        with connect_db() as conn:
            conn.execute(
                "INSERT INTO centers(name,location,need,capacity) VALUES(?,?,?,?)",
                (request.form["name"].strip(), request.form["location"], need, capacity)
            )
        flash("Donation center added successfully.")
    except sqlite3.IntegrityError:
        flash("Center name and location must be unique.")
    except (ValueError, KeyError):
        flash("Enter valid positive need and capacity values.")
    return redirect(url_for("index"))

@app.route("/plan")
def plan():
    return render_page(build_plan())

@app.route("/distributed/<int:food_id>", methods=["POST"])
def mark_distributed(food_id):
    with connect_db() as conn:
        conn.execute("UPDATE food SET status='Distributed' WHERE id=?", (food_id,))
    flash("Food status updated.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
