'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from enum import Enum, auto
from itertools import accumulate
from bisect import bisect_left

from sequence.message import Message
from sequence.protocol import Protocol
from sequence.topology.node import Node
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils import log
from sequence.resource_management.memory_manager import MemoryManager, MemoryInfo
from sequence.constants import MILLISECOND, MICROSECOND, EPSILON


class ACMsgType(Enum):
    '''Defines possible message types for the adaptive continuous (AC) protocol
    '''
    REQUEST = auto()  # ask if the neighbor has available memory
    RESPOND = auto()      # responding no available memory


class AdaptiveContinuousMessage(Message):
    '''Message used by the adaptive continuous protocol

    Attributes:
        msg_type (ACMsgType): the message type
        receiver (str): name of the destination protocol instance
    '''
    def __init__(self, msg_type: ACMsgType, **kwargs):
        super().__init__(msg_type, receiver='adaptive_continuous')
        self.initiate_memory_name = kwargs['initiate_memory_name']
        self.string = f'type={msg_type.name}, initiate_memory_name={self.initiate_memory_name}'

        if self.msg_type == ACMsgType.RESPOND:
            self.answer = kwargs['answer']
            self.string += ', answer={}'.format(self.answer)
            if self.answer == True:
                self.paired_memory_name = kwargs['paired_memory_name']
                self.string += ', paired_memory_name={}'.format(self.paired_memory_name)
    
    def __str__(self):
        return f'|{self.string}|'


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
        self.probability_table = {}

    def init(self):
        self.init_probability_table()

    def start(self) -> None:
        '''start a new "cycle" of the adaptive-continuous protocol
        '''
        # 1. check whether the adaptive protocol has used up its memory quota
        if self.adaptive_memory_used >= self.adaptive_max_memory:
            self.start_delay(delay=MILLISECOND)  # schedule a start event in the future
            return

        # 2. get RAW memory
        raw_memory_info = self.get_raw_memory_info()
        if raw_memory_info is not None:
            # 3.1 update status to occupied
            self.memory_manager.update(raw_memory_info.memory, MemoryInfo.OCCUPIED)
            # 3.2 select neighbor & check neighbor's memory
            neighbor = self.select_neighbor()
            msg = AdaptiveContinuousMessage(ACMsgType.REQUEST, initiate_memory_name=raw_memory_info.memory.name)
            self.owner.send_message(neighbor, msg)
            # 4. create rules is in the received_message
        else:
            # no RAW memory, schedule another start event after 1 ms
            self.start_delay(delay=MILLISECOND)


    def start_delay(self, delay: float) -> None:
        '''create a "start" event after a random delay
        Args:
            delay: schedule the event after some amount of delay (pico seconds)
        '''
        assert delay >= 0, f'delay = {delay} is negative'
        random_delay = int(self.owner.get_generator().normal(delay, delay / 100))
        if random_delay < 0:
            random_delay = -random_delay
        process = Process(self, 'start', [])
        event = Event(self.owner.timeline.now() + random_delay, process)
        self.owner.timeline.schedule(event)


    def get_raw_memory_info(self) -> MemoryInfo:
        '''return True if the quantum router has avaliable (i.e., RAW) memory, otherwise return None
        '''
        for memory_info in self.memory_manager:
            if memory_info.state == MemoryInfo.RAW:
                return memory_info
        return None


    def init_probability_table(self):
        '''initialize the probability table computed from the static routing protocols' forwarding table
        '''
        probability_table = {}
        forwarding_table = self.owner.network_manager.protocol_stack[0].get_forwarding_table()
        neighbors = []
        for dst, next_hop in forwarding_table.items():
            if dst == next_hop:  # it is a neighbor when the destination equals the next hop in the forwarding table
                neighbors.append(dst)
        for neighbor in neighbors:
            probability_table[neighbor] = 1 / len(neighbors)
        assert abs(sum(probability_table.values()) - 1) < EPSILON
        self.probability_table = probability_table


    def select_neighbor(self) -> str:
        '''return the name of the selected neighbor
           The selection algorithm is roulette wheel
        '''
        neighbors = []
        probs = []
        for neighbor, prob in sorted(self.probability_table.items()):
            neighbors.append(neighbor)
            probs.append(prob)
        probs_accumulate = list(accumulate(probs))
        random_number = self.owner.get_generator().random()
        index = bisect_left(probs_accumulate, random_number)
        return neighbors[index]


    def received_message(self, src: str, msg: ACMsgType):
        '''override Protocol.received_message, method to receive AC Messages.

        Message come in 3 types, as detailed in the `ACMsgType` class

        Args:
            scr (str): name of the node that sent the message
            msg (ACMsgType): message received
        '''
        log.logger.info('{} receive message from {}: {}'.format(self.name, src, msg))

        if msg.msg_type is ACMsgType.REQUEST:
            if self.adaptive_memory_used >= self.adaptive_max_memory:  # AC Protocol cannot exceed adaptive_max_memory
                new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, answer=False, initiate_memory_name=msg.initiate_memory_name)
            else:
                raw_memory_info = self.get_raw_memory_info()
                if raw_memory_info is None:                            # no available quantum memory
                    new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, answer=False, initiate_memory_name=msg.initiate_memory_name)
                else:                                                  # has available quantum memory
                    self.memory_manager.update(raw_memory_info.memory, MemoryInfo.OCCUPIED)
                    new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, answer=True, initiate_memory_name=msg.initiate_memory_name, 
                                                                                        paired_memory_name=raw_memory_info.memory.name)
            self.owner.send_message(src, new_msg)
        
        elif msg.msg_type is ACMsgType.RESPOND:
            if msg.answer is False:           # no paired memory
                self.memory_manager.update(raw_memory_info.memory, MemoryInfo.RAW)
                self.start_delay(MILLISECOND)
            else:                             # has paired memory
                pass


