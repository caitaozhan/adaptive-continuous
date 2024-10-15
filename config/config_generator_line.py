"""This module generates JSON config files for networks in a linear configuration.

Help information may also be obtained using the `-h` flag.

Args:
    linear_size (int): number of nodes in the graph.
    memo_size (int): number of memories per node.
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
"""

import argparse
import json
import os
from sequence.utils.config_generator import add_default_args, get_node_csv, generate_node_procs, generate_nodes, generate_classical, final_config, router_name_func
from sequence.topology.topology import Topology
from sequence.topology.router_net_topo import RouterNetTopo


parser = argparse.ArgumentParser()
parser.add_argument('linear_size', type=int, help='number of network nodes')
parser = add_default_args(parser)
args = parser.parse_args()

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
                "efficiency": 0.5,
                "coherence_time": 1,
                "decoherence_errors": [0.3333333333333333, 0.3333333333333333, 0.3333333333333333]
            },
            "adaptive_max_memory": 0,
            "encoding_type": "single_heralded"
        }
    }

# get csv file (if present)
if args.nodes:
    node_procs = get_node_csv(args.nodes)
else:
    node_procs = generate_node_procs(args.parallel, args.linear_size, router_name_func)

# generate nodes
router_names = list(node_procs.keys())
# nodes = generate_nodes(node_procs, router_names, args.memo_size)
template = 'adaptive_protocol'
nodes = generate_nodes(node_procs, router_names, args.memo_size, template, args.gate_fidelity, args.measurement_fidelity)

# generate bsm nodes
bsm_names = ["BSM_{}_{}".format(i, i + 1) for i in range(args.linear_size - 1)]
bsm_nodes = [{Topology.NAME: bsm_name,
              Topology.TYPE: RouterNetTopo.BSM_NODE,
              Topology.SEED: i,
              RouterNetTopo.TEMPLATE: template}
             for i, bsm_name in enumerate(bsm_names)]
if args.parallel:
    for i in range(args.linear_size - 1):
        bsm_nodes[i][RouterNetTopo.GROUP] = int(
            i // (args.linear_size / int(args.parallel[2])))
nodes += bsm_nodes
output_dict[Topology.ALL_NODE] = nodes

# generate quantum links, classical with bsm nodes
qchannels = []
cchannels = []
for i, bsm_name in enumerate(bsm_names):
    # qchannels
    qchannels.append({Topology.SRC: router_names[i],
                      Topology.DST: bsm_name,
                      Topology.DISTANCE: args.qc_length * 500,
                      Topology.ATTENUATION: args.qc_atten})
    qchannels.append({Topology.SRC: router_names[i + 1],
                      Topology.DST: bsm_name,
                      Topology.DISTANCE: args.qc_length * 500,
                      Topology.ATTENUATION: args.qc_atten})
    # cchannels
    for node in [router_names[i], router_names[i + 1]]:
        cchannels.append({Topology.SRC: bsm_name,
                          Topology.DST: node,
                          Topology.DELAY: args.cc_delay * 1e9})

        cchannels.append({Topology.SRC: node,
                          Topology.DST: bsm_name,
                          Topology.DELAY: args.cc_delay * 1e9})
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


# python config/config_generator_line.py 2 10 1 0.0002 1 -d config -o line_2.json -s 10 -gf 0.99 -mf 0.99
# python config/config_generator_line.py 5 10 1 0.0002 1 -d config -o line_5.json -s 10 -gf 0.99 -mf 0.99
