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


def ring():
    filename = 'tmp/ring'
    size = 10
    net_type = 'ring'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/ring.png')
    plt.show()


def grid():
    filename = 'tmp/grid'
    size = 10
    net_type = 'grid'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/grid.png')
    plt.show()


def as_net():
    filename = 'tmp/as_net'
    size = 10
    net_type = 'as_net'
    graph_arr = Utility.gen_network_json(filename, size, net_type)
    G = nx.Graph(graph_arr)
    pos = nx.spring_layout(G)
    nx.draw_networkx(G, pos)
    plt.savefig('tmp/as_net.png')
    plt.show()


if __name__ == '__main__':
    ring()
    grid()
    as_net()

