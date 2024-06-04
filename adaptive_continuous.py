'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from sequence.message import Message
from sequence.protocol import Protocol
from sequence.topology.node import Node
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils import log
from sequence.resource_management.memory_manager import MemoryManager, MemoryInfo
from sequence.constants import MILLISECOND, MICROSECOND


class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.

    New attributes:
        adaptive_max_memory (int): maximum number of memory used for Adaptive-continuous protocol
        memory_array (MemoryArray): memory array to track
    '''

    def __init__(self, owner: "Node", name: str, adaptive_max_memory: int, memory_manager: MemoryManager):
        super().__init__(owner, name)
        self.adaptive_max_memory = adaptive_max_memory
        self.adaptive_memory_used = 0
        self.memory_manager = memory_manager
        self.probability_table = []

    def init(self):
        self.init_probability_table()

    def loop(self) -> None:
        '''a single loop of the adaptive-continuous protocol
        '''
        # 1. check whether the adaptive protocol has used up its memory quota
        if self.adaptive_memory_used >= self.adaptive_max_memory:
            self.loop_event(delay=MILLISECOND)  # schedule a loop event in the future
            return

        # 2. get RAW memory
        raw_memory_info = self.get_raw_memory_info()
        if raw_memory_info is not None:
            # 3. select neighbor & check neighbor's memory
            neighbor = self.select_neighbor()

            # 4. create rules
        else:
            # no RAW memory, schedule another loop event after 1 ms
            self.loop_event(delay=MILLISECOND)


    def loop_event(self, delay: float) -> None:
        '''create a loop event after a random delay
        Args:
            delay: schedule the event after some amount of delay (pico seconds)
        '''
        assert delay >= 0, f'delay = {delay} is negative'
        random_delay = int(self.owner.get_generator().normal(delay, delay / 100))
        if random_delay < 0:
            random_delay = -random_delay
        process = Process(self, 'loop', [])
        event = Event(self.owner.timeline.now() + random_delay, process)
        self.owner.timeline.schedule(event)


    def get_raw_memory_info(self) -> MemoryInfo:
        '''return True if the quantum router has avaliable (i.e., RAW) memory, otherwise return None
        '''
        for memory_info in self.memory_manager:
            if memory_info.state == MemoryInfo.RAW:
                return memory_info
        return None

    def init_probability_table(self) -> dict:
        '''return the probability table computed from the static routing protocols' forwarding table
        '''
        forwarding_table = self.owner.network_manager.protocol_stack[0].get_forwarding_table()
        probability_table = {}
        neighbors = []
        for dst, next_hop in forwarding_table.items():
            if dst == next_hop:  # it is a neighbor when the destination equals the next hop in the forwarding table
                neighbors.append(dst)
        for neighbor in neighbors:
            probability_table[neighbor] = 1 / len(neighbors)
        return probability_table


    def select_neighbor(self):
        return None

    def received_message(self, src: str, msg: Message):
        '''override Protocol.received_message
        '''
        pass
