# 🏢 Jacksonville Service Allocation Planner

A strategic, data-driven optimization tool designed for city planners and public health officials. This application identifies the most impactful locations for new **Healthcare Clinics** and **Grocery Stores** within Jacksonville, FL, by balancing socioeconomic need against real-world budgetary constraints.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

## 📖 Overview

The **Jax Service Allocation Planner** solves the "Facility Location Problem" using mathematical optimization. It analyzes ZIP-code level data—including uninsured rates, primary care access, obesity statistics, and food deserts—to determine where a limited budget should be spent to serve the maximum number of residents in high-risk areas.

This project was created as a part of the **2026 CodeforAwhile: Data for Good AI Challenge for Middle and High School Students.** It was created by Dhruv Sonavane and Sudarshan Centhilkumar as competitors in the high school division. 

### Key Functional Areas:

* **Weighted Need Analysis:** Users can adjust "Need Weights" in the sidebar to prioritize specific health outcomes (e.g., placing more importance on Uninsured populations over Food Access).
* **Dynamic Budgeting & Cost Scaling:** The app calculates construction costs dynamically. As the "Service Radius" increases, the app automatically scales the cost per facility, reflecting the higher infrastructure demands of larger service hubs.
* **Linear Programming Optimization:** Using the `PuLP` library, the app runs a binary integer programming model to select the optimal set of ZIP codes that maximize the total "Need Score" without exceeding the user-defined budget.
* **Geospatial Visualization:** Built with `PyDeck`, the dashboard provides:
    * **Need Heatmap:** A red-shaded background showing the concentration of health risks across the city.
    * **Proposed Facilities:** Blue (Clinic) and Green (Grocery) markers showing exactly where to build.
    * **Service Coverage:** Transparent circles representing the reach of each facility based on the selected mileage radius.

---

### How to run it on your own machine

1. **Create a virtual environment**
   In the terminal, run: 
   ```bash
   $ python -m venv .venv
2. **Install the requirements**
   Ensure you are in the project root directory and run:
   ```bash
   $ .\.venv\Scripts\python.exe -m pip install -r requirements.txt

3. **Run the App**
   ```bash
   $ .\.venv\Scripts\streamlit run jax-service-allocation-planner.py
   