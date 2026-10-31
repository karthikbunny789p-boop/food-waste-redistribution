import streamlit as st
import pandas as pd
import heapq
import time

st.set_page_config(
    page_title="Food Redistribution System",
    page_icon="🍲",
    layout="wide"
)

# Location network and distances
graph = {
    "Kitchen": {"Market": 4, "College": 2},
    "Market": {"Kitchen": 4, "Shelter": 3},
    "College": {"Kitchen": 2, "Shelter": 2},
    "Shelter": {"Market": 3, "College": 2}
}

# Donation centers
centers = {
    "Market": {
        "name": "Food Shelter",
        "need": 30,
        "capacity": 40
    },
    "College": {
        "name": "Orphanage",
        "need": 20,
        "capacity": 25
    },
    "Shelter": {
        "name": "Community Center",
        "need": 25,
        "capacity": 30
    }
}

# Estimated heuristic distances to each destination
heuristic = {
    "Kitchen": 0,
    "Market": 3,
    "College": 2,
    "Shelter": 0
}

if "food" not in st.session_state:
    st.session_state.food = []

st.title("AI-Based Food Waste Redistribution")
st.write(
    "Redistribute surplus food to donation centers "
    "using AI search algorithms."
)

st.header("1. Enter Food Donation Details")
with st.form("food_form"):
    name = st.text_input("Food Name")
    quantity = st.number_input(
        "Quantity (kg)", min_value=1, value=10
    )
    expiry = st.number_input(
        "Expiry Time (hours)", min_value=1, value=4
    )
    location = st.selectbox(
        "Pickup Location", list(graph.keys())
    )
    submitted = st.form_submit_button("Add Food")
    if submitted:
        if name.strip():
            st.session_state.food.append({
                "Food": name,
                "Quantity": int(quantity),
                "Expiry": int(expiry),
                "Location": location
            })
            st.success("Food donation added successfully!")
        else:
            st.error("Please enter the food name.")

if st.session_state.food:
    st.subheader("Available Food Donations")
    st.dataframe(
        pd.DataFrame(st.session_state.food),
        use_container_width=True
    )

# Greedy Best First Search
def greedy_search(start, goal):
    queue = [(heuristic[goal], start, [start])]
    visited = set()
    while queue:
        _, node, path = heapq.heappop(queue)
        if node == goal:
            distance = sum(
                graph[path[i]][path[i + 1]]
                for i in range(len(path) - 1)
            )
            return distance, path
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                heapq.heappush(
                    queue,
                    (heuristic[goal], neighbor,
                     path + [neighbor])
                )
    return float("inf"), []

# A* shortest-path search
def astar_search(start, goal):
    queue = [(0, 0, start, [start])]
    best = {start: 0}
    while queue:
        _, cost, node, path = heapq.heappop(queue)
        if node == goal:
            return cost, path
        if cost > best.get(node, float("inf")):
            continue
        for neighbor, distance in graph[node].items():
            new_cost = cost + distance
            if new_cost < best.get(
                neighbor, float("inf")
            ):
                best[neighbor] = new_cost
                priority = new_cost + heuristic[neighbor]
                heapq.heappush(
                    queue,
                    (priority, new_cost, neighbor,
                     path + [neighbor])
                )
    return float("inf"), []

st.header("2. Select AI Search Algorithm")
algorithm = st.selectbox(
    "Route Optimization",
    ["A* Search", "Greedy Best-First Search"]
)

if st.button("Generate Redistribution Plan"):
    if not st.session_state.food:
        st.warning("Add food donations first.")
    else:
        remaining_need = {
            loc: data["need"]
            for loc, data in centers.items()
        }
        remaining_capacity = {
            loc: data["capacity"]
            for loc, data in centers.items()
        }
        plan = []
        # Prioritize food with the earliest expiry
        sorted_food = sorted(
            st.session_state.food,
            key=lambda item: item["Expiry"]
        )
        start_time = time.perf_counter()
        for item in sorted_food:
            available = item["Quantity"]
            # Prefer centers with available need and capacity
            destinations = sorted(
                centers.keys(),
                key=lambda loc: (
                    astar_search(
                        item["Location"], loc
                    )[0]
                )
            )
            for destination in destinations:
                if available <= 0:
                    break
                if (
                    remaining_need[destination] <= 0
                    or remaining_capacity[destination] <= 0
                ):
                    continue
                if algorithm == "A* Search":
                    distance, route = astar_search(
                        item["Location"], destination
                    )
                else:
                    distance, route = greedy_search(
                        item["Location"], destination
                    )
                if not route:
                    continue
                allocated = min(
                    available,
                    remaining_need[destination],
                    remaining_capacity[destination]
                )
                if allocated > 0:
                    plan.append({
                        "Food": item["Food"],
                        "Quantity (kg)": allocated,
                        "Donation Center":
                            centers[destination]["name"],
                        "Route": " -> ".join(route),
                        "Distance (km)": distance,
                        "Expiry (hours)": item["Expiry"]
                    })
                    available -= allocated
                    remaining_need[destination] -= allocated
                    remaining_capacity[destination] -= allocated
        execution_time = time.perf_counter() - start_time
        st.session_state.plan = plan
        st.session_state.execution_time = execution_time

if "plan" in st.session_state:
    st.header("3. Food Redistribution Results")
    if st.session_state.plan:
        result = pd.DataFrame(st.session_state.plan)
        st.dataframe(result, use_container_width=True)
        total = result["Quantity (kg)"].sum()
        st.metric("Total Food Redistributed", f"{total} kg")
        st.metric(
            "Execution Time",
            f"{st.session_state.execution_time:.6f} seconds"
        )
        st.success("Redistribution plan generated successfully!")
    else:
        st.warning(
            "No suitable donation center has available capacity."
        )

st.header("4. Donation Center Information")
center_data = []
for loc, data in centers.items():
    center_data.append({
        "Location": loc,
        "Donation Center": data["name"],
        "Food Requirement (kg)": data["need"],
        "Maximum Capacity (kg)": data["capacity"]
    })
st.dataframe(
    pd.DataFrame(center_data),
    use_container_width=True
)

st.caption(
    "Note: This educational prototype uses sample locations "
    "and distances, not live maps or real-time traffic."
)
