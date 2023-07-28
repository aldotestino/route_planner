import logging
import os
import random
import sys
import sumolib
import platform
import ray
from ray.rllib.algorithms import ppo
import traci
import traci.constants as tc
import matplotlib.pyplot as plt
import pandas as pd

from RoutePlanner import RoutePlanner
from utils import save_results_on_file, get_max_erm, get_min_length_routes, create_route_file, create_sumocfg, get_route_with_max_pr, print_data

sys.setrecursionlimit(100000)

start_edge = "E4"
rev_start_edge = ""
end_edges = ["E1", "48563882#0"]

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


net_file = os.path.join("scenario_7", "bari.net.xml")
add_file = os.path.join("scenario_7", "bari.add.xml")

sumo_binary = "/opt/homebrew/bin//sumo-gui" if platform.system() == "Darwin" else os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo-gui.exe')
sumo_cmd = [sumo_binary, "-c", os.path.join("scenario_7", "bari.sumocfg")]
sumo_net = sumolib.net.readNet(net_file)

preferred_roads = {
    "1068572560#0": 5,
    "29980621#4": 5,
    "29980621#5": 5,
    "29980621#6": 5,
    "E3": 5,
    "E6": 5
}

optimal_routes = []
results = []

def save_optimal_route(optimal_route):
    optimal_routes.append(optimal_route)

ray.init(logging_level=logging.ERROR)

algo = ppo.PPO(env=RoutePlanner, config={
    "env_config": {
        "sumo_cmd": sumo_cmd,
        "sumo_net": sumo_net,
        "base_route": "r_0",
        "start_edge": start_edge,
        "rev_start_edge": rev_start_edge,
        "end_edges": end_edges,
        "save_optimal_route": save_optimal_route,
        "preferred_roads": preferred_roads
    },
    "num_workers": 0
})

for i in range(40):
    res = algo.train()
    episode_reward_mean = res["episode_reward_mean"];
    print(f"epoch: {i} - episode_reward_mean: {episode_reward_mean}")
    results.append({
        "episode_reward_mean": episode_reward_mean,
        "optimal_routes": optimal_routes
    })
    optimal_routes = []


plt.subplots(figsize=(12, 8))
plt.plot(list(range(40)), [epoch["episode_reward_mean"] for epoch in results])
plt.xlabel("epoch")
plt.ylabel("episode reward mean")
plt.show()

save_results_on_file(results)
index, max_erm = get_max_erm(results)
min_routes = get_min_length_routes(results[index]["optimal_routes"])
if len(min_routes) > 1:
    best_route = get_route_with_max_pr(min_routes, preferred_roads.keys())
else:
    best_route = min_routes[0]


print(f"Epoca con il valore massimo di 'episode_reward_mean' {index}")
print(f"Valore massimo di 'episode_reward_mean' {max_erm}")
print(f"Miglior route: {best_route}")

rou_file = create_route_file(best_route)
sumocfg_file = create_sumocfg(net_file, rou_file, add_file)

traci.close()

# SIMULAZIONE ROUTE OTTIMALE #

sumo_cmd = [sumo_binary, "-c", sumocfg_file]

traci.start(sumo_cmd)
traci.vehicle.add("v_0" ,"r_0", line="vehicle");
traci.vehicle.subscribe("v_0", (
    tc.VAR_ROUTE_ID,
    tc.VAR_ROAD_ID,
    tc.VAR_POSITION,
    tc.VAR_SPEED,
    tc.VAR_WAITING_TIME,
    tc.VAR_ACCUMULATED_WAITING_TIME,
    tc.VAR_CO2EMISSION,
    tc.VAR_FUELCONSUMPTION,
    tc.VAR_DISTANCE,
    tc.VAR_PERSON_NUMBER,
))

traffic_routes = ["r_1", "r_2", "r_3", "r_4"]
n_traffic_vehicle = 400
for i in range(1, n_traffic_vehicle + 1):
    traci.vehicle.add(f"v_{i}", random.choice(traffic_routes), depart=f"{random.randint(0, 600)}")

vehicle_df = pd.DataFrame(columns=["road", "speed [km/h]", "waiting_time [s]", "accumulated_waiting_time [s]", "co2_emission [mg/s]", "fuel_consumption [mg/s]", "distance [m]", "persons"])


while True:
    traci.simulationStep()
    try:

        vehicle_values = traci.vehicle.getSubscriptionResults("v_0")
        road = vehicle_values[tc.VAR_ROAD_ID]
        speed = round(float(vehicle_values[tc.VAR_SPEED]) * 3.6, 2)
        waiting_time = int(vehicle_values[tc.VAR_WAITING_TIME])
        accumulated_waiting_time = int(vehicle_values[tc.VAR_ACCUMULATED_WAITING_TIME])
        co2_emission = vehicle_values[tc.VAR_CO2EMISSION]
        fuel_consumption = vehicle_values[tc.VAR_FUELCONSUMPTION]
        distance = vehicle_values[tc.VAR_DISTANCE]
        persons = list(traci.vehicle.getPersonIDList("v_0"))

        vehicle_df.loc[len(vehicle_df)] = [road, speed, waiting_time, accumulated_waiting_time, co2_emission, fuel_consumption, distance, ':'.join(persons)]

        
    except Exception:
        print("simulazione terminata")
        break


print(vehicle_df)
vehicle_df.to_csv("vehicle_data.csv")

persons_ids = vehicle_df["persons"].dropna().str.split(':').explode().unique()

print_data(vehicle_df, preferred_roads.keys(), persons_ids)

traci.close()