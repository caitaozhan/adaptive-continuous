"""This module generates JSON config files for networks in a bottleneck configuration, shown as follows:

(left) -- node -- node -- (right)

Help information may also be obtained using the `-h` flag.

Args:
    right_size (int): number of nodes on the left side of the bottleneck
    left_size (int): number of nodes on the right side of the bottleneck
    memo_size_bottleneck (int): number of memories on the bottleneck node.
    memo_size_side (int): number of memories on the side nodes.
    qc_length (float): distance between nodes (in km).
    qc_atten (float): quantum channel attenuation (in dB/m).
    cc_delay (float): classical channel delay (in ms).

Optional Args:
    -d --directory (str): name of the output directory (default tmp)
    -o --output (str): name of the output file (default out.json).
    -s --stop (float): simulation stop time (in s) (default infinity).
    -p --parallel: sets simulation as parallel and requires addition args:
        server ip (str): IP address of quantum manager server.
        server port (int): port quantum manager server is attached to.
        num. processes (int): number of processes to use for simulation.
        sync/async (bool): denotes if timelines should be synchronous (true) or not (false).
        lookahead (int): simulation lookahead time for timelines (in ps).
    -n --nodes (str): path to csv file providing process information for nodes.

    
python config/config_generator_bottleneck.py 4 4 10 5 1 0.0002 1 -d config -o bottleneck_10.json -s 100
python config/draw_topo.py config/bottleneck_10.json -d config -f bottleneck_10 -m

"""

import argparse
import json
import os

from sequence.utils.config_generator import add_default_args, get_node_csv, generate_node_procs, generate_nodes, generate_classical, final_config, router_name_func
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


# parse args
parser = argparse.ArgumentParser()
parser.add_argument('left_size', type=int, help='number of nodes on the left side of the bottleneck')
parser.add_argument('right_size', type=int, help='number of nodes on the right side of the bottleneck')
parser.add_argument('memo_size_bottleneck', type=int, help='number of memories on the bottleneck node')
parser.add_argument('memo_size_side', type=int, help='number of memories on the side node')
parser.add_argument('qc_length', type=float, help='distance between nodes (in km)')
parser.add_argument('qc_atten', type=float, help='quantum channel attenuation (in dB/m)')
parser.add_argument('cc_delay', type=float, help='classical channel delay (in ms)')
parser.add_argument('-d', '--directory', type=str, default='tmp', help='name of output directory')
parser.add_argument('-o', '--output', type=str, default='out.json', help='name of output config file')
parser.add_argument('-s', '--stop', type=float, default=float('inf'), help='stop time (in s)')
parser.add_argument('-p', '--parallel', nargs=4, help='optional parallel arguments: server ip, server port, num. processes, lookahead')
parser.add_argument('-n', '--nodes', type=str, help='path to csv file to provide process for each node')

args = parser.parse_args()

net_size = args.left_size + args.right_size + 2

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
                "fidelity": 0.98,
                "efficiency": 0.5
            },
            "adaptive_max_memory": 2
        }
    }

# get csv file (if present) and node names
if args.nodes:
    node_procs = get_node_csv(args.nodes)
    # assume center node is last listed
    center_name = list(node_procs.keys())[-1]
else:
    node_procs = generate_node_procs(args.parallel, net_size, router_name_func)
    # rename bottleneck router
    # center_name = "router_center"
    # proc = node_procs[router_name_func(args.star_size)]
    # del node_procs[router_name_func(args.star_size)]
    # node_procs[center_name] = proc
router_names = list(node_procs.keys())

bottleneck_left_name  = f'router_{args.left_size}'
bottleneck_right_name = f'router_{args.left_size + 1}'

# generate nodes, with middle having different num
template = 'adaptive_protocol'
nodes = generate_nodes(node_procs, router_names, args.memo_size_side, template)
for node in nodes:
    if node[Topology.NAME] == bottleneck_left_name or node[Topology.NAME] == bottleneck_right_name:
        node[RouterNetTopo.MEMO_ARRAY_SIZE] = args.memo_size_bottleneck
        
channels = [] # [(left node, bsm, right node), ...]

# generate quantum links
qchannels = []
cchannels = []
bsm_names = []
# left side
for i in range(args.left_size):
    bsm_name = f'BSM_{i}_{args.left_size}'
    bsm_names.append(bsm_name)
    channels.append((router_names[i], bsm_name, bottleneck_left_name))

# bottleneck
bsm_name = f'BSM_{args.left_size}_{args.left_size+1}'
bsm_names.append(bsm_name)
channels.append((router_names[args.left_size], bsm_name, router_names[args.left_size+1]))

# right side
for i in range(args.left_size + 2, args.left_size + 2 + args.right_size):
    bsm_name = f'BSM_{args.left_size + 1}_{i}'
    bsm_names.append(bsm_name)
    channels.append((bottleneck_right_name, bsm_name, router_names[i]))

bsm_nodes = [{Topology.NAME: bsm_name,
              Topology.TYPE: RouterNetTopo.BSM_NODE,
              Topology.SEED: i}
              for i, bsm_name in enumerate(bsm_names)]

if args.parallel:
    for i in range(args.star_size):
        bsm_nodes[i][RouterNetTopo.GROUP] = nodes[i][RouterNetTopo.GROUP]

for left_node_name, bsm_name, right_node_name in channels:
    # qchannels
    qchannels.append({Topology.SRC: left_node_name,
                      Topology.DST: bsm_name,
                      Topology.DISTANCE: args.qc_length * 500,
                      Topology.ATTENUATION: args.qc_atten})
    qchannels.append({Topology.SRC: right_node_name,
                      Topology.DST: bsm_name,
                      Topology.DISTANCE: args.qc_length * 500,
                      Topology.ATTENUATION: args.qc_atten})
    # cchannels
    cchannels.append({Topology.SRC: left_node_name,
                      Topology.DST: bsm_name,
                      Topology.DELAY: args.cc_delay * 1e9})
    cchannels.append({Topology.SRC: right_node_name,
                      Topology.DST: bsm_name,
                      Topology.DELAY: args.cc_delay * 1e9})
    cchannels.append({Topology.SRC: bsm_name,
                      Topology.DST: left_node_name,
                      Topology.DELAY: args.cc_delay * 1e9})
    cchannels.append({Topology.SRC: bsm_name,
                      Topology.DST: right_node_name,
                      Topology.DELAY: args.cc_delay * 1e9})

output_dict[Topology.ALL_NODE] = nodes + bsm_nodes
output_dict[Topology.ALL_Q_CHANNEL] = qchannels

# generate classical links
router_cchannels = generate_classical(router_names, args.cc_delay)
cchannels += router_cchannels
output_dict[Topology.ALL_C_CHANNEL] = cchannels

# write other config options to output dictionary
final_config(output_dict, args)

# write final json
path = os.path.join(args.directory, args.output)
output_file = open(path, 'w')
json.dump(output_dict, output_file, indent=4)

