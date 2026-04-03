import streamlit as st
import pandas as pd
import numpy as np
import pulp
import pydeck as pdk
import math

# ---------------------------------------------------------
# PAGE CONFIG & CLEAN UI
# ---------------------------------------------------------
st.set_page_config(page_title="Jax Service Allocation Planner", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0); 
        border: none !important;
        box-shadow: none !important;
    }
    .stDataFrame { background-color: transparent !important; }
    .streamlit-expanderContent { background-color: #f8f9fa !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Jacksonville Service Allocation Planner")
st.caption("Strategic City Planning Tool: Budget-Constrained Facility Location Optimizer")

# ---------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 3959.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def weighted_geometric_median(points, weights, eps=1e-6, max_iter=100):
    points, weights = np.asarray(points), np.asarray(weights)
    current = np.average(points, axis=0, weights=weights)
    for _ in range(max_iter):
        diffs = points - current
        dists = np.linalg.norm(diffs, axis=1)
        if np.any(dists < eps): return points[dists.argmin()]
        w_over_d = weights / dists
        new = np.sum(points * w_over_d[:, None], axis=0) / np.sum(w_over_d)
        if np.linalg.norm(new - current) < eps: break
        current = new
    return current

# ---------------------------------------------------------
# DATA LOADING & WEIGHTED LOGIC
# ---------------------------------------------------------
@st.cache_data
def load_and_prep_data(w_uninsured, w_pcp, w_obesity, w_food):
    try:
        try:
            need_df = pd.read_csv("datafiles/clustered_zipcodes.csv")
            centroids = pd.read_excel("datafiles/Usable_ZIP_Code_Population_Weighted_Centroids_Jacksonville.xlsx")
        except:
            need_df = pd.read_csv("clustered_zipcodes.csv")
            centroids = pd.read_excel("Usable_ZIP_Code_Population_Weighted_Centroids_Jacksonville.xlsx")
    except Exception as e:
        st.error(f"Data files not found. Error: {e}")
        st.stop()
        
    need_df = need_df.loc[:, ~need_df.columns.duplicated()]
    need_df = need_df[need_df["ZIP Code"] != 12031]
    need_df = need_df.rename(columns={"ZIP Code": "ZIP", "Low Food Access": "LowFoodAccess", "Park Area": "ParkArea", "PCP Ratio": "PCPRatio"})

    need_df["ZIP"] = need_df["ZIP"].astype(str).str.strip()
    centroids = centroids.rename(columns={"STD_ZIP5": "ZIP", "LATITUDE": "lat", "LONGITUDE": "lon"})
    centroids["ZIP"] = centroids["ZIP"].astype(str).str.strip()

    def norm(s): return (s - s.min()) / (s.max() - s.min()) if s.max() != s.min() else 0
    for col in ["LowFoodAccess", "Obesity", "Uninsured", "ParkArea", "PCPRatio"]:
        need_df[f"norm_{col}"] = norm(need_df[col])

    h_total = w_uninsured + w_pcp + w_obesity
    h_w = [w / h_total if h_total > 0 else 0 for w in [w_uninsured, w_pcp, w_obesity]]
    need_df["clinic_need"] = (h_w[0] * need_df["norm_Uninsured"] + h_w[1] * need_df["norm_PCPRatio"] + h_w[2] * need_df["norm_Obesity"])

    f_total = w_food + w_obesity
    f_w = [w / f_total if f_total > 0 else 0 for w in [w_food, w_obesity]]
    need_df["grocery_need"] = (f_w[0] * need_df["norm_LowFoodAccess"] + f_w[1] * need_df["norm_Obesity"])

    return need_df.merge(centroids[["ZIP", "lat", "lon"]], on="ZIP", how="inner")

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
with st.sidebar:
    st.header("🏢 Planning Parameters")
    with st.expander("💰 Financial Budgeting", expanded=False):
        total_budget = st.number_input("Total Plan Budget ($M)", 1.0, 500.0, 15.0)
        base_cost_clinic = st.slider("Base Clinic Cost ($M)", 1.0, 20.0, 5.0)
        base_cost_grocery = st.slider("Base Grocery Cost ($M)", 1.0, 20.0, 3.5)
        
    with st.expander("🎯 Need Weights", expanded=False):
        w_un = st.slider("Uninsured Weight", 0.0, 1.0, 0.4)
        w_pcp = st.slider("PCP Ratio Weight", 0.0, 1.0, 0.3)
        w_ob = st.slider("Obesity Weight", 0.0, 1.0, 0.1)
        w_fd = st.slider("Food Access Weight", 0.0, 1.0, 0.2)

    radius = st.slider("Service Radius (Miles)", 1.0, 10.0, 3.5)
    
    scaling_factor = 0.05 
    cost_per_clinic = base_cost_clinic * (1 + (scaling_factor * (radius**2)))
    cost_per_grocery = base_cost_grocery * (1 + (scaling_factor * (radius**2)))

    max_clinics = math.floor(total_budget / cost_per_clinic)
    max_groceries = math.floor(total_budget / cost_per_grocery)
    
    st.divider()
    st.metric("Clinic Unit Cost", f"${cost_per_clinic:.2f}M")
    st.metric("Grocery Unit Cost", f"${cost_per_grocery:.2f}M")
    show_analytics = st.checkbox("📊 Show Analytics", value=False)

df = load_and_prep_data(w_un, w_pcp, w_ob, w_fd)

# ---------------------------------------------------------
# OPTIMIZATION
# ---------------------------------------------------------
zips = df["ZIP"].tolist()
lat_map = df.set_index("ZIP")["lat"].to_dict()
lon_map = df.set_index("ZIP")["lon"].to_dict()
coverage = {zi: {zj for zj in zips if haversine(lat_map[zi], lon_map[zi], lat_map[zj], lon_map[zj]) <= radius} for zi in zips}

def run_opt(need_col, prefix, limit):
    if limit < 1: return pd.DataFrame(columns=["ZIP", "lat", "lon", "Impact Score"])
    need_map = df.set_index("ZIP")[need_col].to_dict()
    model = pulp.LpProblem(f"opt_{prefix}", pulp.LpMaximize)
    x = {z: pulp.LpVariable(f"{prefix}_{z}", 0, 1, cat="Binary") for z in zips}
    y = {z: pulp.LpVariable(f"covered_{z}", 0, 1, cat="Binary") for z in zips}
    for j in zips:
        model += y[j] <= pulp.lpSum(x[i] for i in zips if j in coverage[i])
    model += pulp.lpSum(x.values()) <= limit
    model += pulp.lpSum(need_map[z] * y[z] for z in zips)
    model.solve(pulp.PULP_CBC_CMD(msg=False))
    chosen = [z for z in zips if x[z].value() == 1]
    res = []
    for z in chosen:
        sub = df[df["ZIP"].isin(list(coverage[z]))]
        opt_lat, opt_lon = weighted_geometric_median(sub[["lat", "lon"]].values, sub[need_col].values)
        # Rename Score to Impact Score here
        res.append({"ZIP": z, "lat": opt_lat, "lon": opt_lon, "Impact Score": round(sub[need_col].sum(), 2)})
    return pd.DataFrame(res)

clinic_pts = run_opt("clinic_need", "clinic", max_clinics)
grocery_pts = run_opt("grocery_need", "grocery", max_groceries)

# ---------------------------------------------------------
# MAP FUNCTION
# ---------------------------------------------------------
def render_map(points_df, color_rgb, need_col):
    df["fill_color"] = df[need_col].apply(lambda x: [255, 0, 0, int(x * 160)])
    view_state = pdk.ViewState(latitude=30.3322, longitude=-81.6557, zoom=10, pitch=40)
    
    layers = [
        pdk.Layer("ScatterplotLayer", df, get_position="[lon, lat]", 
                  get_fill_color="fill_color", get_radius=1100, pickable=False)
    ]
    
    if not points_df.empty:
        layers.extend([
            pdk.Layer("ScatterplotLayer", points_df, get_position="[lon, lat]", 
                      get_fill_color=color_rgb + [40], get_radius=radius * 1609, pickable=False),
            pdk.Layer("ScatterplotLayer", points_df, get_position="[lon, lat]", 
                      get_fill_color=color_rgb, get_radius=600, pickable=True)
        ])
    
    bg_color = f"rgb({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]})"

    st.pydeck_chart(pdk.Deck(
        layers=layers, initial_view_state=view_state,
        tooltip={
            "html": "<b>ZIP Code:</b> {ZIP}<br/><b>Impact Score:</b> {Impact Score}<br/><b>Latitude:</b> {lat}<br/><b>Longitude:</b> {lon}",
            "style": {"backgroundColor": bg_color, "color": "white"}
        }
    ))

# ---------------------------------------------------------
# UI TABS
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🏥 Healthcare Network", "🛒 Food Security Network"])

with tab1:
    if clinic_pts.empty:
        st.warning("⚠️ Budget insufficient for this radius. Lower the radius or increase total budget.")
    else:
        c1, c2 = st.columns([3, 1])
        with c1: render_map(clinic_pts, [70, 130, 180], "clinic_need") # Steel Blue
        with c2:
            st.write("### Clinic Allocations")
            st.metric("Facilities Built", len(clinic_pts), f"Limit: {max_clinics}")
            st.metric("Money Spent", f"${(len(clinic_pts) * cost_per_clinic):.1f}M")
            st.dataframe(clinic_pts[["ZIP", "lat", "lon", "Impact Score"]].sort_values("Impact Score", ascending=False), hide_index=True)

with tab2:
    if grocery_pts.empty:
        st.warning("⚠️ Budget insufficient for this radius. Lower the radius or increase total budget.")
    else:
        c1, c2 = st.columns([3, 1])
        with c1: render_map(grocery_pts, [34, 139, 34], "grocery_need") # Green
        with c2:
            st.write("### Grocery Allocations")
            st.metric("Facilities Built", len(grocery_pts), f"Limit: {max_groceries}")
            st.metric("Money Spent", f"${(len(grocery_pts) * cost_per_grocery):.1f}M")
            st.dataframe(grocery_pts[["ZIP", "lat", "lon", "Impact Score"]].sort_values("Impact Score", ascending=False), hide_index=True)

if show_analytics:
    st.divider()
    chart_data = df[["ZIP", "clinic_need", "grocery_need"]].set_index("ZIP")
    st.bar_chart(chart_data)

st.divider()
# Expanded info block with Impact Score definition
st.info(f"""
**Strategic Summary:**
* The red heatmap identifies areas with the highest combined social and health risks. 
* The blue/green hubs are the mathematically ideal locations to build facilities to reach the most people in need, given your current budget and service radius.

**What is the Impact Score?**
The **Impact Score** represents the total 'Need Units' captured within a facility's service radius. It is calculated by summing the normalized risk factors of all covered ZIP codes, weighted by your sidebar preferences:
* **Healthcare Impact:** Sum of (Uninsured % × {w_un} + PCP Ratio × {w_pcp} + Obesity × {w_ob}).
* **Food Impact:** Sum of (Low Food Access × {w_fd} + Obesity × {w_ob}).
A higher score indicates the facility is positioned to serve a population with significantly higher service gaps.
""") 