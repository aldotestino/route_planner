import json
import os
import matplotlib.pyplot as plt
import numpy as np

def save_results_on_file(results: dict):
    with open("results.json", "w") as file:
        json.dump(results, file)


# def get_max_erm_old(results: dict):
#     wanted_key = 0
#     max_erm = float("-inf")

#     for key, value in results.items():
#         erm = value.get("episode_reward_mean", None);
#         if erm > max_erm:
#             max_erm = erm
#             wanted_key = key

#     return wanted_key, max_erm

def get_max_erm(results: list):
    erms = np.array([o["episode_reward_mean"] for o in results])
    index = np.argmax(erms)
    return index, results[index]["episode_reward_mean"]


# def get_min_length_routes_old(routes: list):
#     min_routes = []
#     min_length_route = float("inf")

#     for route in routes:
#         route_length = len(route);
#         if route_length < min_length_route:
#             min_length_route = route_length

#     for route in routes:
#         if len(route) == min_length_route:
#             min_routes.append(route)

#     return min_routes

def get_min_length_routes(routes: list):
    routes_len = np.array([len(route) for route in routes])
    indexes = np.nonzero(routes_len == routes_len.min())
    min_routes = [route for i, route in enumerate(routes) if i in indexes[0].tolist()]
    return [list(route) for route in set(tuple(route) for route in min_routes)]


# def get_route_with_max_pr_old(routes: list, preferred_roads: list):
#     best_route = []
#     max_n_pr = float("-inf")

#     for route in routes:

#         count = 0
#         for road in route:
#             if road in preferred_roads:
#                 count += 1
        
#         if count > max_n_pr:
#             max_n_pr = count
#             best_route = route
    
#     return best_route

def get_route_with_max_pr(routes: list, preferred_roads: list):
    preferred_counts = [sum(1 for road in route if road in preferred_roads) for route in routes]
    index_max_count = np.argmax(preferred_counts)
    return routes[index_max_count]
    

def create_route_file(route: list):
    route_template_f = open("route_template.rou.xml")
    route_template = route_template_f.readlines()
    route_template[7] = f"\t<route id=\"r_0\" edges=\"{' '.join(route)}\">\n"
    route_f = open("result.rou.xml", "w")
    route_f.write("".join(route_template))
    return route_f.name


def create_sumocfg(net_file: str, rou_file: str, add_file: str):
    os.system(f"sumo -n {net_file} -r {rou_file} -a {add_file} --waiting-time-memory 2000 --save-configuration result.sumocfg")
    return "result.sumocfg"


def get_pr_distance(df, preferred_roads):
    tot_pr_distance = 0
    for pr in preferred_roads:
        pr_distances = df[df["road"] == pr]["distance [m]"].tolist()
        pr_distance = 0
        if len(pr_distances) > 1:
            pr_distance = pr_distances[-1] - pr_distances[0]
            
        tot_pr_distance = tot_pr_distance + pr_distance

    return round(tot_pr_distance / 1000, 2)


def format_seconds(seconds: int):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def print_data(df, preferred_roads, persons):
    
    distance = round(df["distance [m]"].tolist()[-1] / 1000, 2) # km
    time = format_seconds(len(df))
    tot_pr_distance = get_pr_distance(df, preferred_roads)
    wait_time = format_seconds(df["accumulated_waiting_time [s]"].tolist()[-1])

    persons_time = []
    persons_distance = []
    persons_distance_pr = []
    persons_wait_time = []

    for person in persons:
        person_df = df[df['persons'].str.contains(person)]
        person_distances = person_df["distance [m]"].tolist()
        persons_distance.append(round((person_distances[-1] - person_distances[0]) / 1000, 2))
        persons_time.append(format_seconds(len(person_distances)))

        persons_distance_pr.append(get_pr_distance(person_df, preferred_roads))

        person_awts = person_df["accumulated_waiting_time [s]"].tolist()
        persons_wait_time.append(format_seconds(person_awts[-1] - person_awts[0]))


    print(f"Distanza totale veicolo: {distance} km")
    print(f"Tempo di percorrenza veicolo: {time} min")
    print(f"Distanza totale percorsa su strade preferenziali dal veicolo: {tot_pr_distance} km")
    print(f"Tempo di attesa veicolo {wait_time} min")

    for i, person in enumerate(persons):
        print(f"Distanza percorsa in auto da {person}: {persons_distance[i]} km")
        print(f"Tempo trascorso in viaggio da {person}: {persons_time[i]} min")
        print(f"Distanza totale percorsa su strade preferenziali da {person}: {persons_distance_pr[i]} km")
        print(f"Tempo di attesa di {person}: {persons_wait_time[i]} min")

    plt.subplots(figsize=(12, 8))
    plt.plot(list(range(len(df))), df["speed [km/h]"])
    plt.xlabel("secondi")
    plt.ylabel("km/h")
    plt.title("Profilo di velocità")
    plt.show()

