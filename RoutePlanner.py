import gym
import traci
import traci.constants as tc
from sumolib.net import Net


class RoutePlanner(gym.Env):
    
    def __init__(self, env_config):
        traci.start(env_config["sumo_cmd"])
        self.edges = traci.edge.getIDList()
        self.action_space = gym.spaces.Discrete(3)
        self.observation_space = gym.spaces.Discrete(len(self.edges))
        self.ego_idx = -1
        self.current_ego = f"EGO_{self.ego_idx}"
        self.prev_dist = 0
        self.visited_roads = []  # lista di strade già visitate
        self.start_edge = env_config["start_edge"]
        self.rev_start_edge = env_config["rev_start_edge"]
        self.end_edges = env_config["end_edges"]
        self.end_edge_to_reach = 0
        self.optimal_route = [self.start_edge]
        self.base_route = env_config["base_route"]
        self.sumo_net: Net = env_config["sumo_net"]
        self.save_optimal_route: function = env_config["save_optimal_route"]
        self.preferred_roads = env_config["preferred_roads"]
        self.first_run = True

        self.add_vehicle()


    def reset(self):
        self.first_run = True
        return self.edges.index(self.start_edge)
    

    def step(self, action):
        prev_current_road = ""
        action_applied = False
        reward = 0

        while True:
            current_road = ":"

            while current_road.startswith(":"):
                if prev_current_road != "" or self.first_run:
                    traci.simulationStep()
                    self.first_run = False
                ego_values = traci.vehicle.getSubscriptionResults(self.current_ego)
                try:
                    current_road: str = ego_values[tc.VAR_ROAD_ID]
                except Exception:
                    current_road = ":"

            done = (self.end_edge_to_reach == len(self.end_edges) - 1 and current_road == self.end_edges[-1]) or current_road == self.rev_start_edge
            if done:
                if current_road == self.end_edges[-1]:
                    reward = 10
                    self.save_optimal_route(self.optimal_route)
                self.add_vehicle()
                break
            
            if prev_current_road == "":
                prev_current_road = current_road

            if current_road != prev_current_road:
                 if prev_current_road not in self.visited_roads:
                     self.visited_roads.append(prev_current_road)
                 break
            elif not action_applied:
                out_edges = {}
                try:
                    out_edges = self.sumo_net.getEdge(current_road).getOutgoing()
                except Exception:
                    pass
              
                out_edges_list = [out_edge.getID() for out_edge in out_edges]
                if len(out_edges_list) > 0:
                    if action >= len(out_edges_list):
                        reward = -10
                        done = True
                        self.add_vehicle()
                        break
                    else:
                        self.optimal_route.append(out_edges_list[action])
                        traci.vehicle.setRoute(self.current_ego, [current_road, out_edges_list[action]])
                        action_applied = True
                else:
                    reward = -10
                    done = True
                    self.add_vehicle()
                    break

        current_dist = traci.simulation.getDistanceRoad(current_road, 0, self.end_edges[self.end_edge_to_reach], 0, False)

        if reward == 0:
            if len(self.visited_roads) > 0 and current_road in self.visited_roads:
                reward = -10
            elif current_road == self.end_edges[self.end_edge_to_reach]:
                reward = 10 
                self.end_edge_to_reach += 1
            elif current_dist < self.prev_dist:
                if current_road in self.preferred_roads.keys():
                    reward = self.preferred_roads[current_road]
                else:
                    reward = 1
            else:
                reward = -1

        self.prev_dist = current_dist
        return self.edges.index(current_road), reward, done, {}


    def add_vehicle(self):
        if self.ego_idx > -1 and self.current_ego in traci.vehicle.getIDList():
            traci.vehicle.unsubscribe(self.current_ego)
            traci.vehicle.remove(self.current_ego)
        self.ego_idx += 1
        self.current_ego = f"EGO_{self.ego_idx}"
        self.optimal_route = [self.start_edge]
        traci.vehicle.add(self.current_ego, self.base_route)
        traci.vehicle.subscribe(self.current_ego, (
            tc.VAR_ROUTE_ID,
            tc.VAR_ROAD_ID,
            tc.VAR_POSITION,
            tc.VAR_SPEED,
        ))
        self.visited_roads = []
        self.end_edge_to_reach = 0
        self.prev_dist = traci.simulation.getDistanceRoad(self.start_edge, 0, self.end_edges[self.end_edge_to_reach], 0, False)