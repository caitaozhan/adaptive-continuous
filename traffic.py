'''generate a traffix matrix and request queue
'''

from typing import Tuple, List
from itertools import accumulate
import random
from bisect import bisect_left

from sequence.constants import SECOND


class TrafficMatrix:
    '''traffic matrix
    '''
    def __init__(self, num_nodes: int):
        self.num_nodes = num_nodes
        self.matrix = None
        self.set_matrix_to_zero()

    def set_matrix_to_zero(self):
        self.matrix = [[0 if i < j else None for j in range(self.num_nodes)] for i in range(self.num_nodes)]

    def set(self, topology: str, nodes: int, seed: int = None):
        '''set the traffix matrix for runner.py and main.py
        Args:
            topology (str): topology type
            nodes (int): number of nodes
            seed (int): a seed for traffic pattern
        '''
        if topology == 'as' and nodes == 20:
            self.as_20()
        elif topology == 'as' and nodes == 100:
            self.as_100()
        elif topology == 'line' and nodes == 2:
            self.line_2()
        elif topology == 'bottleneck' and nodes == 20:
            self.bottleneck_20(seed)
        else:
            raise Exception(f'{topology},{nodes} combination not supported')

    def line_2(self):
        ''' For the line_2.json
        '''
        self.matrix[0][1] = 1
        # self.matrix[1][0] = 1


    def line_5(self):
        ''' For the line_5.json
        '''
        self.matrix[1][3] = 1


    def bottleneck_10(self):
        ''' For the bottleneck_10.json
            (2, 8) -- 50%
            (3, 9) -- 20%
            (3, 9) -- 30%
        '''
        self.matrix[2][8] = 0.5
        self.matrix[3][9] = 0.2
        self.matrix[3][8] = 0.3

    def bottleneck_20(self, seed: int):
        ''' For the bottleneck_20.json
            (7, 18) -- 25%
            (7, 19) -- 25%
            (8, 18) -- 25%
            (8, 19) -- 25%
        '''
        self.set_matrix_to_zero()
        if seed == 0:
            self.matrix[0][11] = 0.25
            self.matrix[0][12] = 0.25
            self.matrix[1][11] = 0.25
            self.matrix[1][12] = 0.25        
        if seed == 1:
            self.matrix[7][18] = 0.25
            self.matrix[7][19] = 0.25
            self.matrix[8][18] = 0.25
            self.matrix[8][19] = 0.25
    
    def as_20(self):
        '''for autonomous system 20 nodes
        '''
        self.matrix[10][14] = 1/3
        self.matrix[13][19] = 1/3
        self.matrix[11][16] = 1/3


    def as_100(self):
        '''for autonomous system 100 nodes
        '''
        self.matrix[53][57] = 1/6
        self.matrix[33][51] = 1/6
        self.matrix[57][71] = 1/6
        self.matrix[48][54] = 1/6
        self.matrix[73][88] = 1/6
        self.matrix[53][85] = 1/6


    def matrix_to_prob_list(self) -> Tuple[List]:
        '''convert the traffix matrix into probability list
        '''
        src_dst_pairs = []
        prob_list = []
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if self.matrix[i][j] is not None and self.matrix[i][j] > 0:
                    src_dst_pairs.append((i, j))
                    prob_list.append(self.matrix[i][j])
        return src_dst_pairs, prob_list


    def get_request_queue(self, request_time: int, total_time: int, memo_size: int, fidelity: float, entanglement_number: int, seed: int = 0) -> list:
        '''get a queue of requests, each request is represented by (src, dst, start_time, end_time, memo_size, fidelity, entanglement_number)
           the request are uniformly distributed, one after another
        
        Args:
            request_time: the time period for each request (end_time - start_time)
            total_time: the total time of all request
            memo_size: the memory size for each request
            fidelity: the fidelity requirement for each request
            entanglement_number: the number of entanglement needed
            seed: the random seed
        Return:
            a list of requests, where each request is represented by a tuple (src name, dst name, start time, end time, memory size, fidelity)
        '''
        src_dst_pairs, prob_list = self.matrix_to_prob_list()
        prob_accumulate = list(accumulate(prob_list))
        random.seed(seed)

        request_id = 0
        request_queue = []
        cur_time = 0.01 # in seconds
        while cur_time < total_time:
            random_number = random.uniform(0, 1)
            index = bisect_left(prob_accumulate, random_number)
            src, dst = src_dst_pairs[index]
            src_name = f'router_{src}'
            dst_name = f'router_{dst}'
            start_time = cur_time
            end_time = cur_time + request_time
            if end_time < total_time:
                request_queue.append((request_id, src_name, dst_name, round(start_time * SECOND), round(end_time * SECOND), memo_size, fidelity, entanglement_number))
                request_id += 1
            cur_time = end_time + 0.01
        
        return request_queue


    def get_request_queue_tts(self, request_queue: list, request_period: float, delta: float, start_time: float, end_time: float, memo_size: int, fidelity: float, entanglement_number: int, seed: int = 0) -> list:
        '''get a queue of requests, each request is represented by (src, dst, start_time, end_time, memo_size, fidelity, entanglement_number)
           the request are uniformly distributed, one after another
        
           This is for the time to serve metric

        Args:
            queue: existing request queue. The new requests will be concatenated to this queue. Has impact on the request ID
            request_period: the time period (in seconds) for each request
            delta: time for EP pre-generation
            start_time: the start time of the first request in the queue
            end_time:   the end tme of the last request in the queue
            memo_size: the memory size for each request
            fidelity: the fidelity requirement for each request
            entanglement_number: the number of entanglement needed
            seed: the random seed
        Return:
            a list of requests, where each request is represented by a tuple (src name, dst name, start time, end time, memory size, fidelity)
        '''
        assert delta < request_period

        src_dst_pairs, prob_list = self.matrix_to_prob_list()
        prob_accumulate = list(accumulate(prob_list))
        random.seed(seed)

        if request_queue:
            request_id = request_queue[-1][0] + 1   # start from the ID from the last request of the paramater request_queue
        else:
            request_id = 0

        cur_time = start_time # in seconds
        while cur_time < end_time:
            random_number = random.uniform(0, 1)
            index = bisect_left(prob_accumulate, random_number)
            src, dst = src_dst_pairs[index]
            src_name = f'router_{src}'
            dst_name = f'router_{dst}'
            request_start_time = cur_time + delta
            request_end_time = cur_time + request_period
            if request_end_time <= end_time:
                request_queue.append((request_id, src_name, dst_name, round(request_start_time * SECOND), round(request_end_time * SECOND), memo_size, fidelity, entanglement_number))
                request_id += 1
            cur_time = request_end_time

        return request_queue
