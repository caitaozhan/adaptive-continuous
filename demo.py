'''
Implement the paper titled "Adaptive, Continuous Entanglement Generation for Quantum Networks" 
in SeQUeNCe and conduct experiments with a large number of nodes.
'''

from collections import defaultdict
import numpy as np
import os
import matplotlib.pyplot as plt
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.constants import MILLISECOND
import sequence.utils.log as log
from request_app import RequestAppTimeToServe
from router_net_topo_adaptive import RouterNetTopoAdaptive
from traffic import TrafficMatrix


# five node linear network, zero quantum memory for ACP
def linear_5node_0memory():

    purify = True

    network_config = 'demo/line_5-m0.json'
    log_directory = 'demo'
    log_filename  = 'log-line5,qmem=0,update=False'
    log_file = os.path.join(log_directory, log_filename)
    if os.path.exists(log_directory) is False:
        os.makedirs(log_directory)

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_file)
    log.set_logger_level('DEBUG')
    # modules = ['request_app', 'swapping', 'rule_manager', 'resource_manager', 'generation', 'memory', 'main_test', 'purification', 'bsm']
    modules = ['demo']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = False
        router.adaptive_continuous.print_prob_table = True
        router.resource_manager.purify = purify

    mem_size = 1
    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.line_5()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=60, memo_size=mem_size, fidelity=0.7, entanglement_number=1)
    for request in request_queue[:]:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()

    time_to_serve_dict = defaultdict(float)
    fidelity_dict = defaultdict(list)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve
        fidelity_dict |= app.entanglement_fidelities

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        fidelity = fidelity_dict[reservation][0]
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}, fidelity={fidelity:.6f}')


# five node linear network, zero quantum memory for ACP
def linear_5node_4memory(update_prob_table: bool):

    purify = True

    network_config = 'demo/line_5-m4.json'
    log_directory = 'demo'
    log_filename  = f'log-line5,qmem=4,update={update_prob_table}'
    log_file = os.path.join(log_directory, log_filename)
    if os.path.exists(log_directory) is False:
        os.makedirs(log_directory)

    network_topo = RouterNetTopoAdaptive(network_config)
    
    tl = network_topo.get_timeline()

    log.set_logger(__name__, tl, log_file)
    log.set_logger_level('DEBUG')
    # modules = ['request_app', 'swapping', 'rule_manager', 'resource_manager', 'generation', 'memory', 'main_test', 'purification', 'bsm']
    modules = ['demo']
    for module in modules:
        log.track_module(module)

    name_to_apps = {}
    for router in network_topo.get_nodes_by_type(RouterNetTopo.QUANTUM_ROUTER):
        app = RequestAppTimeToServe(router)
        name_to_apps[router.name] = app
        # if router.name not in ['router_4', 'router_5']:
        #     router.active = False
        router.adaptive_continuous.has_empty_neighbor = True
        router.adaptive_continuous.update_prob = update_prob_table
        router.adaptive_continuous.print_prob_table = True
        router.resource_manager.purify = purify

    mem_size = 1
    num_nodes = len(name_to_apps)
    traffic_matrix = TrafficMatrix(num_nodes)
    traffic_matrix.line_5()
    request_queue = traffic_matrix.get_request_queue_tts(request_period=1, total_time=60, memo_size=mem_size, fidelity=0.5, entanglement_number=1)
    for request in request_queue[:]:
        id, src_name, dst_name, start_time, end_time, memo_size, fidelity, entanglement_number = request
        app = name_to_apps[src_name]
        app.start(dst_name, start_time, end_time, memo_size, fidelity, entanglement_number, id)

    tl.init()
    tl.run()
    # print()

    time_to_serve_dict = defaultdict(float)
    fidelity_dict = defaultdict(list)
    for _, app in name_to_apps.items():
        time_to_serve_dict |= app.time_to_serve
        fidelity_dict |= app.entanglement_fidelities

    for reservation, time_to_serve in sorted(time_to_serve_dict.items()):
        fidelity = fidelity_dict[reservation][0]
        log.logger.info(f'reservation={reservation}, time to serve={time_to_serve / MILLISECOND}, fidelity={fidelity:.6f}')


def read_log(filename: str) -> list:
    '''read data from logs
    '''
    y = []
    with open(filename, 'r') as f:
        for line in f:
            if 'time to serve' in line:
                line = line.split()
                tts = line[13]  # time to serve
                i, j = tts.find('='), -1
                tts = float(tts[i+1:j])
                fidelity = line[14]
                i, j = fidelity.find('='), len(fidelity)
                fidelity = float(fidelity[i+1:j])
                y.append(tts)
    return y


def draw_plots():
    logfile_m0    = 'demo/log-line5,qmem=0,update=False'
    logfile_m4    = 'demo/log-line5,qmem=4,update=False'
    logfile_m4_up = 'demo/log-line5,qmem=4,update=True'
    y_m0 = read_log(logfile_m0)
    y_m4 = read_log(logfile_m4)
    y_m4_up = read_log(logfile_m4_up)
    print('q-memory = 0,              average time to serve = {:.2f} ms'.format(np.average(y_m0)))
    print('q-memory = 4, no adaptive. average time to serve = {:.2f} ms'.format(np.average(y_m4)))
    print('q-memory = 4, adaptive.    average time to serve = {:.2f} ms'.format(np.average(y_m4_up)))

    length = 10
    y_m0_avg = []
    for i in range(length, len(y_m0)+1):
        y_m0_avg.append(np.average(y_m0[i-length:i]))

    y_m4_avg = []
    for i in range(length, len(y_m4)+1):
        y_m4_avg.append(np.average(y_m4[i-length:i]))

    y_m4_up_avg = []
    for i in range(length, len(y_m4_up)+1):
        y_m4_up_avg.append(np.average(y_m4_up[i-length:i]))


    fig, ax = plt.subplots(figsize=(5.5,4))
    fig.subplots_adjust(left=0.13, right=0.96, bottom=0.12, top=0.92)
    ax.plot(range(len(y_m0_avg)), y_m0_avg, label=f'On Demand Only', linewidth=2)
    ax.plot(range(len(y_m4_avg)), y_m4_avg, label=f'UC Protocol', linewidth=2)
    ax.plot(range(len(y_m4_up_avg)), y_m4_up_avg, label=f'AC Protocol', linewidth=2)
    ax.legend(ncols=2, fontsize=11)
    ax.grid()
    ax.set_xlim([0, 50])
    ax.set_ylim([0, 120])
    ax.set_xlabel('Request Number', fontsize=13)
    ax.set_ylabel('Time-to-serve (ms)', fontsize=13)
    ax.set_title('AC Protocol Improves TTS in 5-Node Linear Network', fontsize=13)
    fig.savefig("demo/demo.png")

if __name__ == '__main__':
    
    # linear_5node_0memory()
    # linear_5node_4memory(update_prob_table=False)
    # linear_5node_4memory(update_prob_table=True)

    draw_plots()


