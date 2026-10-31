import streamlit as st
import pandas as pd
import heapq
import time
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Food Waste Redistribution & Route Optimizer",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .stButton>button {
        background-color: #2563EB;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        width: 100%;
    }
</style>
""", unsafe_allow_python_style=True)

# --- Network Coordinates & Graph ---
locations = {
    "Kitchen": {"lat": 17.385043, "lon": 78.486671, "type": "Donor"},
    "Market": {"lat": 17.406498, "lon": 78.477244, "type": "Center"},
    "College": {"lat": 17.398422, "lon": 78.558265, "type": "Center"},
    "Shelter": {"lat": 17.440081, "lon": 78.348916, "type": "Center"}
}

graph = {
    "Kitchen": {"Market": 4, "College": 2},
    "Market": {"Kitchen": 4, "Shelter": 3},
    "College": {"Kitchen": 2, "Shelter": 2},
    "Shelter": {"Market": 3, "College": 2}
}

centers = {
    "Market": {"name": "Food Shelter", "need": 30, "capacity": 40},
    "College": {"name": "Orphanage", "need": 20, "capacity": 25},
    "Shelter": {"name": "Community Center", "need": 25, "capacity": 30}
}

heuristic = {
    "Kitchen": 0,
    "Market": 3,
    "College": 2,
    "Shelter": 0
}

# Initialize Session State
if "food" not in st.session_state:
    st.session_state.food = []

# --- AI Search Algorithms ---
def greedy_search(start, goal):
    queue = [(heuristic[goal], start, [start])]
    visited = set()
    while queue:
        _, node, path = heapq.heappop(queue)
        if node == goal:
            distance = sum(graph[path[i]][path[i + 1]] for i in range(len(path) - 1))
            return distance, path
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                heapq.heappush(queue, (heuristic[goal], neighbor, path + [neighbor]))
    return float("inf"), []

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
            if new_cost < best.get(neighbor, float("inf")):
                best[neighbor] = new_cost
                priority = new_cost + heuristic[neighbor]
                heapq.heappush(queue, (priority, new_cost, neighbor, path + [neighbor]))
    return float("inf"), []

# --- Header Section ---
st.markdown('<div class="main-header">🌱 AI-Powered Food Waste Redistribution System</div>', unsafe_allow_python_style=True)
st.markdown('<div class="sub-header">Optimize surplus food delivery routes and reduce urban food spoilage using A* & Greedy Best-First Search.</div>', unsafe_allow_python_style=True)

# --- Sidebar Controls ---
st.sidebar.title("⚙️ System Control")
algorithm = st.sidebar.selectbox(
    "Select AI Routing Algorithm",
    ["A* Search Algorithm", "Greedy Best-First Search"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Quick Actions")
if st.sidebar.button("Clear Inventory Data"):
    st.session_state.food = []
    if "plan" in st.session_state:
        del st.session_state.plan
    st.sidebar.success("Cleared inventory!")

# --- Main Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Donation Management", "🚀 Optimization & Plan", "🗺️ Geographic Map", "📊 Recipient Overview"])

# TAB 1: DONATION INPUT & INVENTORY
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add Surplus Food Entry")
        with st.form("food_form", clear_on_submit=True):
            name = st.text_input("Food Item Name", placeholder="e.g., Prepared Meals, Rice, Bread")
            quantity = st.number_input("Quantity (kg)", min_value=1, value=15)
            expiry = st.number_input("Expiry Window (Hours)", min_value=1, value=4)
            location = st.selectbox("Pickup Location", list(graph.keys()))
            
            submitted = st.form_submit_button("➕ Add Food Donation")
            if submitted:
                if name.strip():
                    st.session_state.food.append({
                        "Food": name,
                        "Quantity": int(quantity),
                        "Expiry": int(expiry),
                        "Location": location
                    })
                    st.success(f"Added {name} ({quantity} kg) to active queue.")
                else:
                    st.error("Please specify the item name.")

    with col2:
        st.subheader("Current Available Inventory")
        if st.session_state.food:
            df_food = pd.DataFrame(st.session_state.food).sort_values("Expiry")
            st.dataframe(df_food, use_container_width=True, hide_index=True)
            
            st.info("💡 **Priority Rule:** Donations are automatically sorted by earliest expiry window.")
        else:
            st.warning("No surplus food currently logged. Add food items using the form on the left.")

# TAB 2: OPTIMIZATION & PLAN GENERATION
with tab2:
    st.subheader("Generate & View Redistribution Plan")
    
    if st.button("⚡ Run AI Route & Allocation Engine"):
        if not st.session_state.food:
            st.warning("Please add food items in the 'Donation Management' tab first.")
        else:
            remaining_need = {loc: data["need"] for loc, data in centers.items()}
            remaining_capacity = {loc: data["capacity"] for loc, data in centers.items()}
            plan = []
            
            sorted_food = sorted(st.session_state.food, key=lambda item: item["Expiry"])
            start_time = time.perf_counter()
            
            for item in sorted_food:
                available = item["Quantity"]
                destinations = sorted(
                    centers.keys(),
                    key=lambda loc: astar_search(item["Location"], loc)[0]
                )
                
                for destination in destinations:
                    if available <= 0:
                        break
                    if remaining_need[destination] <= 0 or remaining_capacity[destination] <= 0:
                        continue
                    
                    if "A*" in algorithm:
                        distance, route = astar_search(item["Location"], destination)
                    else:
                        distance, route = greedy_search(item["Location"], destination)
                    
                    if not route:
                        continue
                    
                    allocated = min(available, remaining_need[destination], remaining_capacity[destination])
                    if allocated > 0:
                        plan.append({
                            "Food": item["Food"],
                            "Allocated (kg)": allocated,
                            "Destination Center": centers[destination]["name"],
                            "Optimal Route": " ➔ ".join(route),
                            "Total Distance (km)": distance,
                            "Expiry Window": f"{item['Expiry']} hrs"
                        })
                        available -= allocated
                        remaining_need[destination] -= allocated
                        remaining_capacity[destination] -= allocated

            execution_time = time.perf_counter() - start_time
            st.session_state.plan = plan
            st.session_state.execution_time = execution_time

    if "plan" in st.session_state:
        if st.session_state.plan:
            plan_df = pd.DataFrame(st.session_state.plan)
            
            # Key Performance Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Food Allocated", f"{plan_df['Allocated (kg)'].sum()} kg")
            m2.metric("Active Deliveries", f"{len(plan_df)}")
            m3.metric("Execution Latency", f"{st.session_state.execution_time * 1000:.2f} ms")
            
            st.markdown("### Optimized Distribution Route Schedule")
            st.dataframe(plan_df, use_container_width=True, hide_index=True)
            
            # Export Option
            csv_data = plan_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Redistribution Schedule (CSV)",
                data=csv_data,
                file_name="food_redistribution_plan.csv",
                mime="text/csv"
            )
        else:
            st.warning("No valid routes or available capacity found at recipient centers.")

# TAB 3: GEOGRAPHIC MAP VISUALIZATION
with tab3:
    st.subheader("Network Node & Hub Map")
    map_data = []
    for name, details in locations.items():
        map_data.append({
            "name": name,
            "lat": details["lat"],
            "lon": details["lon"],
            "type": details["type"]
        })
    df_map = pd.DataFrame(map_data)
    
    st.map(df_map, zoom=11, use_container_width=True)
    st.caption("📍 Interactive map pins representing pickup points and recipient hubs.")

# TAB 4: RECIPIENT CENTER STATUS
with tab4:
    st.subheader("Donation Centers Demand & Capacity")
    center_list = []
    for loc, d in centers.items():
        center_list.append({
            "Location Key": loc,
            "Center Name": d["name"],
            "Need Requirement (kg)": d["need"],
            "Max Storage Capacity (kg)": d["capacity"]
        })
    df_centers = pd.DataFrame(center_list)
    st.dataframe(df_centers, use_container_width=True, hide_index=True)
    
    # Capacity Visualization Chart
    st.subheader("Capacity vs Demand Overview")
    st.bar_chart(df_centers.set_index("Center Name")[["Need Requirement (kg)", "Max Storage Capacity (kg)"]])
