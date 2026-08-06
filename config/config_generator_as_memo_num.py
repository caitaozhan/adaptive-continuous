"""This module generates a JSON config file and a flow file for an Internet Autonomous System network.

Help information may also be obtained using the `-h` flag.

Args:
    net_size (int): number of routers.
    seed (int): indicator of random number generation state.
    alpha (int): alpha for exponential distribution of flows.
    memo_size (int): number of memories per node.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default config).
    -o --output (str): name of the output file (default as.json).
    -s --stop (float): simulation stop time (in s) (default infinity).

python config/config_generator_as_memo_num.py 200 0 1 10 10 0.0002 1 -o as_200.json -s 110
"""

import argparse
import json
import os
import random

import networkx as nx
import numpy as np
from networkx import dijkstra_path
from simanneal import Annealer

from sequence.constants import BELL_DIAGONAL_STATE_FORMALISM, SECOND
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo

SEED = 1
random.seed(SEED)

TEMPLATE = "bsm_template"



def generate_bsm_links(graph, parsed_args):
    cchannels = []
    qchannels = []
    bsm_nodes = []

    for i, node_pair in enumerate(graph.edges):
        node1, node2 = node_pair
        bsm_name = f"BSM_{node1}_{node2}"
        bsm_node = {Topology.NAME: bsm_name,
                    Topology.TYPE: RouterNetTopo.BSM_NODE,
                    Topology.SEED: i,
                    RouterNetTopo.TEMPLATE: TEMPLATE}
        bsm_nodes.append(bsm_node)

        for node in node_pair:
            qchannels.append({Topology.SRC: node,
                              Topology.DST: bsm_name,
                              Topology.DISTANCE: parsed_args.qc_length * 500,
                              Topology.ATTENUATION: parsed_args.qc_atten})

        for node in node_pair:
            cchannels.append({Topology.SRC: bsm_name,
                              Topology.DST: node,
                              Topology.DELAY: parsed_args.cc_delay * 1e9})

            cchannels.append({Topology.SRC: node,
                              Topology.DST: bsm_name,
                              Topology.DELAY: parsed_args.cc_delay * 1e9})

    return cchannels, qchannels, bsm_nodes


def get_exp_dis_prob(x0, x1, alpha):
    integral_func = lambda x, alpha: -np.e ** (-alpha * x)
    return integral_func(x1, alpha) - integral_func(x0, alpha)


def get_partition(graph, GROUP_NUM, node_memo_size):
    net_size = len(graph.nodes)

    def energy_func_memory_number(reverse_map_group):
        group_memo_num = []
        for node in reverse_map_group:
            group = reverse_map_group[node]
            while group >= len(group_memo_num):
                group_memo_num.append(0)
            group_memo_num[group] += node_memo_size[node]
        e = max(group_memo_num) - min(group_memo_num)
        return e

    class State():
        def __init__(self, group):
            self.group = group
            self.reverse_map_group = {}
            for i, g in enumerate(self.group):
                for n in g:
                    self.reverse_map_group[n] = i

        def get_energy(self):
            return energy_func_memory_number(self.reverse_map_group)

        def move(self):
            group = self.group
            r_group = self.reverse_map_group

            g1, g2 = random.choices(list(range(len(group))), k=2)
            index1, index2 = random.choices(list(range(len(group[g1]))), k=2)
            n1, n2 = group[g1][index1], group[g2][index2]

            group[g1][index1], group[g2][index2] = n2, n1
            r_group[group[g1][index1]] = g1
            r_group[group[g2][index2]] = g2

    class Partition(Annealer):
        def move(self):
            self.state.move()

        def energy(self):
            return self.state.get_energy()

    group = [[] for _ in range(GROUP_NUM)]
    for i in range(net_size):
        index = i // (net_size // GROUP_NUM)
        group[index].append(f"router_{i}")

    if GROUP_NUM == 1:
        return group

    ini_state = State(group)
    partition = Partition(ini_state)
    auto_schedule = partition.auto(minutes=2)

    partition.set_schedule(auto_schedule)
    state, energy = partition.anneal()
    return state.group


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('net_size', type=int, help="net_size (int) - Number of routers")
    parser.add_argument('seed', type=int, help="seed (int) - Indicator of random number generation state")
    parser.add_argument('alpha', type=int, help="alpha for exponential distribution of flows")
    parser.add_argument('memo_size', type=int, help='number of memories per node')
    parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
    parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
    parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
    parser.add_argument('-d', '--directory', type=str, default='config', help='name of output directory')
    parser.add_argument('-o', '--output', type=str, default='as.json', help='name of output config file')
    parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
    args = parser.parse_args()

    NET_SIZE = args.net_size
    FLOW_MEMO_SIZE = args.memo_size

    templates = {
        "router_template": {
            "MemoryArray": {
                "fidelity": 0.95,
                "efficiency": 0.6,
                "coherence_time": 2,
                "decoherence_errors": [0.3333333333333333, 0.3333333333333333, 0.3333333333333333]
            },
            "adaptive_max_memory": 0
        },
        "bsm_template": {
            "encoding_type": "single_heralded",
            "SingleHeraldedBSM": {
                "detectors": [
                    {"efficiency": 0.95},
                    {"efficiency": 0.95}
                ]
            }
        }
    }

    graph = nx.random_internet_as_graph(NET_SIZE, args.seed)
    paths = []
    for src in graph.nodes:
        for dst in graph.nodes:
            if dst >= src:
                continue
            path = dijkstra_path(graph, src, dst)
            hop_num = len(path) - 2
            while len(paths) <= hop_num:
                paths.append([])
            paths[hop_num].append(tuple(path))
            paths[hop_num].append(tuple(path[::-1]))

    MAX_HOP = len(paths)
    TOTAL_FLOW_NUM = NET_SIZE
    # exponential distribution
    FLOW_NUMS = [int(get_exp_dis_prob(i, i + 1, args.alpha) * TOTAL_FLOW_NUM) for i in range(MAX_HOP)]
    FLOW_NUMS[-1] = TOTAL_FLOW_NUM - sum(FLOW_NUMS[:-1])

    selected_paths = {}
    hops_counter = [0 for _ in range(MAX_HOP)]
    nodes_caps = [0 for _ in range(NET_SIZE)]

    for hop_num in range(MAX_HOP - 1, -1, -1):
        flow_num = FLOW_NUMS[hop_num]
        for _ in range(flow_num):
            while len(paths[hop_num]) > 0:
                sample_index = random.choice(list(range(len(paths[hop_num]))))
                sample_path = paths[hop_num][sample_index]
                paths[hop_num].remove(sample_path)

                if sample_path[0] in selected_paths:
                    continue

                selected_paths[sample_path[0]] = sample_path
                for i, node in enumerate(sample_path):
                    if i == 0 or i == len(sample_path) - 1:
                        nodes_caps[node] += 1 * FLOW_MEMO_SIZE
                    else:
                        nodes_caps[node] += 2 * FLOW_MEMO_SIZE

                hops_counter[hop_num] += 1
                break

    unused_nodes = []
    for i, c in enumerate(nodes_caps):
        if c == 0:
            unused_nodes.append(i)

    while unused_nodes:
        n1 = unused_nodes.pop()
        if unused_nodes:
            n2 = unused_nodes.pop()
        else:
            samples = random.choices(list(range(NET_SIZE)), k=2)
            if samples[0] != n1:
                n2 = samples[0]
            else:
                n2 = samples[1]

        if n2 > n1:
            n1, n2 = n2, n1

        path = dijkstra_path(graph, n1, n2)
        hops_counter[len(path) - 2] += 1

        for i, node in enumerate(path):
            if i == 0 or i == len(path) - 1:
                nodes_caps[node] += 1 * FLOW_MEMO_SIZE
            else:
                nodes_caps[node] += 2 * FLOW_MEMO_SIZE

        if n1 not in selected_paths:
            selected_paths[n1] = path
        else:
            selected_paths[n2] = path[::-1]

    mapping = {}
    for i in range(NET_SIZE):
        mapping[i] = f"router_{i}"
    nx.relabel_nodes(graph, mapping, copy=False)

    router_names = [f"router_{i}" for i in range(NET_SIZE)]
    nodes = [{Topology.NAME: name,
              Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
              Topology.SEED: i,
              RouterNetTopo.MEMO_ARRAY_SIZE: FLOW_MEMO_SIZE,
              RouterNetTopo.TEMPLATE: "router_template"}
             for i, name in enumerate(router_names)]

    cchannels, qchannels, bsm_nodes = generate_bsm_links(graph, args)

    for node1 in router_names:
        for node2 in router_names:
            if node1 == node2:
                continue
            cchannels.append({Topology.SRC: node1,
                              Topology.DST: node2,
                              Topology.DELAY: args.cc_delay * 1e9})

    output_dict = {Topology.ALL_TEMPLATES: templates,
                   Topology.ALL_NODE: nodes + bsm_nodes,
                   Topology.ALL_Q_CHANNEL: qchannels,
                   Topology.ALL_C_CHANNEL: cchannels,
                   Topology.STOP_TIME: int(args.stop * SECOND),
                   Topology.FORMALISM: BELL_DIAGONAL_STATE_FORMALISM}

    path = os.path.join(args.directory, args.output)
    with open(path, 'w') as f:
        json.dump(output_dict, f, indent=4)

    flows = {}
    for src in selected_paths:
        path = selected_paths[src]
        src_name = f"router_{src}"
        new_path = [f"router_{n}" for n in path]
        flows[src_name] = new_path

    flow_path = os.path.join(args.directory, 'flow_' + args.output)
    with open(flow_path, 'w') as f:
        flow_info = {"flows": flows, "memo_size": FLOW_MEMO_SIZE}
        json.dump(flow_info, f)


if __name__ == '__main__':
    main()
