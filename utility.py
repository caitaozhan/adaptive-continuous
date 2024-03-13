'''some utilities
'''

from math import sqrt
import matplotlib.pyplot as plt
import json
import networkx as nx
import numpy as np


class Utility:

    @staticmethod
    def gen_network_json(filename, size, net_type, seed=0):
        if net_type == "ring":
            arr = np.zeros((size, size), dtype=int)
            for i in range(size):
                arr[i, (i+1) % size] = 1
                arr[(i+1) % size, i] = 1

        elif net_type == "grid":
            side = int(sqrt(size))
            G = nx.grid_2d_graph(side, side)
            arr = nx.convert_matrix.to_numpy_array(G)

        elif net_type == "as_net":
            G = nx.random_internet_as_graph(size, seed)
            arr = nx.convert_matrix.to_numpy_array(G)

        else:
            raise ValueError("Unknown graph type " + net_type)

        fh = open(filename, 'w')
        topo = {"array": arr.tolist()}
        json.dump(topo, fh)
        return arr

    @staticmethod
    def gen_traffic_matrix(node_num, rng):
        # generator of traffic matrix 
        mtx = rng.random((node_num, node_num))
        for i in range(node_num):
            mtx[i, i] = 0  # no self-to-self traffic
        return mtx


def ring():
    filename = 'tmp/ring'
    size = 20
    net_type = 'ring'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/ring.png')
    plt.show()


def grid():
    filename = 'tmp/grid'
    size = 20
    net_type = 'grid'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/grid.png')
    plt.show()


def as_net():
    filename = 'tmp/as_net'
    size = 20
    net_type = 'as_net'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/as_net.png')
    plt.show()


def gen_traffic():
    from numpy.random import default_rng
    seed = 0
    size = 20
    rng = default_rng(seed)
    traffic_matrix = Utility.gen_traffic_matrix(20, rng)
    filename = 'tmp/traffix_matrix'
    fh = open(filename, 'w')
    traffic = {"traffic": traffic_matrix.tolist()}
    json.dump(traffic, fh)



if __name__ == '__main__':
    # ring()
    # grid()
    # as_net()
    gen_traffic()
