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
        self.matrix = [[0 if i < j else None for j in range(num_nodes)] for i in range(num_nodes)]
    
    def bottleneck_10(self):
        ''' For the bottleneck_10.json
            (0, 6) -- 50%
            (0, 7) -- 20%
            (1, 8) -- 30%
        '''
        self.matrix[0][6] = 0.5
        self.matrix[0][7] = 0.2
        self.matrix[1][8] = 0.3
    
    def matrix_to_prob_list(self) -> Tuple[List]:
        '''convert the traffix matrix into probability list
        '''
        src_dst_pairs = []
        prob_list = []
        for i in range(self.num_nodes):
            for j in range(i+1, self.num_nodes):
                if self.matrix[i][j] is not None and self.matrix[i][j] > 0:
                    src_dst_pairs.append((i, j))
                    prob_list.append(self.matrix[i][j])
        return src_dst_pairs, prob_list


    def get_request_queue(self, request_time: int, total_time: int, memo_size: int, fidelity: float, entanglement_number: int) -> list:
        '''get a queue of requests, each request is represented by (src, dst, start_time, end_time, memo_size, fidelity, entanglement_number)
           the request are uniformly distributed, one after another
        
        Args:
            request_time: the time period for each request (end_time - start_time)
            total_time: the total time of all request
            memo_size: the memory size for each request
            fidelity: the fidelity requirement for each request
        Return:
            a list of requests, where each request is represented by a tuple (src name, dst name, start time, end time, memory size, fidelity)
        '''
        src_dst_pairs, prob_list = self.matrix_to_prob_list()
        prob_accumulate = list(accumulate(prob_list))
        random.seed(0)

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
