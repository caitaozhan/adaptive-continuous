"""This module generates JSON config files for Internet Autonomous System Network
"""

from collections import defaultdict

import os
import networkx as nx
from networkx import dijkstra_path
import argparse
import json
import pandas as pd
import numpy as np
from simanneal import Annealer
import random
import matplotlib.pyplot as plt

from sequence.utils.config_generator import add_default_args, generate_classical, final_config, router_name_func, bsm_name_func
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


SEED = 1
random.seed(SEED)


'''
python config/config_generator_as_memo_num.py 20 0 1 1 10 1 0.0002 1 -d config -o as_20.json -s 10
python config/draw_topo.py config/as_20.json -d config -f as_20

python config/config_generator_as_memo_num.py 200 0 1 1 10 1 0.0002 1 -d config -o as_200.json -s 110


'''

def generate_bsm_links(graph, parsed_args, bsm_naming_func):
    cchannels = []
    qchannels = []
    bsm_nodes = []

    for i, node_pair in enumerate(graph.edges):
        node1, node2 = node_pair
        bsm_name = bsm_naming_func(node1, node2)
        bsm_node = {Topology.NAME: bsm_name,
                    Topology.TYPE: RouterNetTopo.BSM_NODE,
                    Topology.SEED: i,
                    RouterNetTopo.TEMPLATE: template}
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
    integral_func = lambda x, alpha: - np.e ** (-alpha * x)
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
        group[index].append(router_name_func(i))

    if GROUP_NUM == 1:
        return group

    ini_state = State(group)
    partition = Partition(ini_state)
    auto_schedule = partition.auto(minutes=2)

    partition.set_schedule(auto_schedule)
    state, energy = partition.anneal()
    return state.group


parser = argparse.ArgumentParser()
parser.add_argument('net_size', type=int, help="net_size (int) – Number of routers")
parser.add_argument('seed', type=int, help="seed (int) – Indicator of random number generation state. ")
parser.add_argument('group_n', type=int, help="group_n (int) - Number of groups for parallel simulation")
parser.add_argument('alpha', type=int, help="alpha for exponential distribution of flows")
parser = add_default_args(parser)
args = parser.parse_args()

NET_SIZE = args.net_size
NET_SEED = args.seed
GROUP_NUM = args.group_n
ALPHA = args.alpha
FLOW_MEMO_SIZE = args.memo_size
QC_LEN = args.qc_length
QC_ATT = args.qc_atten
CC_DELAY = args.cc_delay
if args.parallel:
    IP = args.parallel[0]
    PORT = int(args.parallel[1])
    LOOKAHEAD = int(args.parallel[4])
    assert int(args.parallel[2]) == GROUP_NUM

graph = nx.random_internet_as_graph(NET_SIZE, NET_SEED)
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
FLOW_NUMS = [int(get_exp_dis_prob(i, i + 1, ALPHA) * TOTAL_FLOW_NUM) for i in range(MAX_HOP)]
FLOW_NUMS[-1] = TOTAL_FLOW_NUM - sum(FLOW_NUMS[:-1])

# fixed hop
# fixed_hop = 4
# FLOW_NUMS = [0 for i in range(MAX_HOP)]
# FLOW_NUMS[fixed_hop] = TOTAL_FLOW_NUM


selected_paths = {}
hops_counter = [0 for i in range(MAX_HOP)]
nodes_caps = [0 for i in range(NET_SIZE)]

for hop_num in range(MAX_HOP - 1, -1, -1):
    flow_num = FLOW_NUMS[hop_num]
    for f_index in range(flow_num):
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
node_memo_size = {}

for i in range(NET_SIZE):
    mapping[i] = router_name_func(i)
    # node_memo_size[router_name_func(i)] = nodes_caps[i]
    node_memo_size[router_name_func(i)] = args.memo_size
nx.relabel_nodes(graph, mapping, copy=False)


output_dict = {}

# templates
output_dict[Topology.ALL_TEMPLATES] = \
    {
        "perfect_memo": {
            "MemoryArray": {
                "fidelity": 1.0,
                "efficiency": 1.0
            }
        },
        "adaptive_protocol": {
            "MemoryArray": {
                "fidelity": 0.95,
                "efficiency": 0.6,
                "coherence_time": 2,
                "decoherence_errors": [0.3333333333333333, 0.3333333333333333, 0.3333333333333333]
            },
            "adaptive_max_memory": 0,
            "encoding_type": "single_heralded",
            "SingleHeraldedBSM": {
                "detectors" :[
                    {"efficiency": 0.95}, 
                    {"efficiency": 0.95}
                ]
            }
        }
    }


node_procs = {}

if args.nodes:
    # TODO: add length/proc assertions
    df = pd.read_csv(args.nodes)
    for name, group in zip(df['name'], df['group']):
        node_procs[name] = group
else:
    groups = get_partition(graph, int(GROUP_NUM), node_memo_size)
    for i, g in enumerate(groups):
        for name in g:
            node_procs[name] = i

template = 'adaptive_protocol'

router_names = list(node_procs.keys())
nodes = [{Topology.NAME: name,
          Topology.TYPE: RouterNetTopo.QUANTUM_ROUTER,
          Topology.SEED: i,
          RouterNetTopo.MEMO_ARRAY_SIZE: node_memo_size[name],
          RouterNetTopo.GROUP: node_procs[name],
          RouterNetTopo.TEMPLATE: template}
         for i, name in enumerate(router_names)]

# add bsm links
cchannels, qchannels, bsm_nodes = generate_bsm_links(graph, args, bsm_name_func)
nodes += bsm_nodes
output_dict[Topology.ALL_NODE] = nodes
output_dict[Topology.ALL_Q_CHANNEL] = qchannels

# add router-to-router classical channels
router_cchannels = generate_classical(router_names, args.cc_delay)
cchannels += router_cchannels
output_dict[Topology.ALL_C_CHANNEL] = cchannels

# write other config options
final_config(output_dict, args)

# write final json
path = os.path.join(args.directory, args.output)
output_file = open(path, 'w')
json.dump(output_dict, output_file, indent=4)

flows = {}
for src in selected_paths:
    path = selected_paths[src]
    src_name = router_name_func(src)
    new_path = [router_name_func(n) for n in path]
    flows[src_name] = new_path

flow_path = os.path.join(args.directory, 'flow_' + args.output)
flow_fh = open(flow_path, 'w')
flow_info = {"flows": flows, "memo_size": FLOW_MEMO_SIZE}
json.dump(flow_info, flow_fh)

fow_tables = defaultdict(lambda: {})
for src in selected_paths:
    path = selected_paths[src]
    for i, node in enumerate(path):
        if i == len(path) - 1:
            break
        table = fow_tables[node]
        if path[-1] in table:
            assert table[path[-1]] == path[i + 1]
        else:
            table[path[-1]] = path[i + 1]
