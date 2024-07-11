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
from sequence.resource_management.memory_manager import MemoryInfo
from reservation import ResourceReservationProtocolAdaptive, ReservationAdaptive
from sequence.constants import MILLISECOND, MICROSECOND, SECOND, EPSILON


class ACMsgType(Enum):
    '''Defines possible message types for the adaptive continuous (AC) protocol
    '''
    REQUEST = auto()  # ask if the neighbor has available memory
    RESPOND = auto()  # responding NO/YES


class AdaptiveContinuousMessage(Message):
    '''Message used by the adaptive continuous protocol

    Attributes:
        msg_type (ACMsgType): the message type
        receiver (str): name of the destination protocol instance
        reservation (Reservation): the reservation created by the Adaptive Continuous Protocol
    '''
    def __init__(self, msg_type: ACMsgType, reservation: ReservationAdaptive, **kwargs):
        super().__init__(msg_type, receiver='adaptive_continuous')
        self.reservation = reservation
        self.string = f'type={msg_type.name}, reservation={reservation}'

        if self.msg_type == ACMsgType.RESPOND:
            self.answer = kwargs['answer']
            self.string += ', answer={}'.format(self.answer)
            if self.answer == True:
                self.path = kwargs['path']
                self.string += f', path={self.path}'
    
    def __str__(self):
        return f'|{self.string}|'


class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.

       This version uses the resource reservation protocol from the network manager, to use the reservation system

    New attributes:
        adaptive_max_memory (int): maximum number of memory used for Adaptive-continuous protocol
        adaptive_memory_used (int):
        resource_reservation:
        probability_table (dict):
        generated_entanglement_pairs (set): each element is a tuple of (str, str), where each str is the name of the memory
    '''

    def __init__(self, owner: "Node", name: str, adaptive_max_memory: int, resource_reservation: ResourceReservationProtocolAdaptive):
        super().__init__(owner, name)
        self.adaptive_max_memory = adaptive_max_memory
        self.adaptive_memory_used = 0
        self.resource_reservation = resource_reservation
        self.probability_table = {}
        self.generated_entanglement_pairs = set()

    def init(self):
        self.init_probability_table()

    def start(self) -> None:
        '''start a new "cycle" of the adaptive-continuous protocol
        '''
        # check whether the adaptive protocol has used up its memory quota
        if self.adaptive_memory_used >= self.adaptive_max_memory:
            self.start_delay(delay=MILLISECOND)  # schedule a start event in the future
            return

        # select neighbor
        neighbor = self.select_neighbor()
        self.adaptive_memory_used += 1
        round_trip_time = self.owner.cchannels[neighbor].delay * 2
        start_time = self.owner.timeline.now() + round_trip_time # consider a round trip time for the "handshaking"
        end_time = start_time + SECOND
        # set up reservation
        reservation = ReservationAdaptive(self.owner.name, neighbor, start_time, end_time, memory_size=1, fidelity=0.9)
        if self.resource_reservation.schedule(reservation):
            # able to schedule on current node, i.e., has memory
            msg = AdaptiveContinuousMessage(ACMsgType.REQUEST, reservation)
            self.owner.send_message(neighbor, msg)
        else:
            # not able to schedule on current node, schedule another start event after 1 ms
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


    def received_message(self, src: str, msg: ACMsgType) -> None:
        '''override Protocol.received_message, method to receive AC Messages.

        Message come in 2 types, as detailed in the `ACMsgType` class

        Args:
            scr (str): name of the node that sent the message
            msg (ACMsgType): message received
        '''
        log.logger.info('{} receive message from {}: {}'.format(self.name, src, msg))

        if msg.msg_type is ACMsgType.REQUEST:
            if self.adaptive_memory_used >= self.adaptive_max_memory:  # AC Protocol cannot exceed adaptive_max_memory
                new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, msg.reservation, answer=False)
            else:
                reservation = msg.reservation
                if self.resource_reservation.schedule(reservation):    # has available quantum memory
                    self.adaptive_memory_used += 1
                    path = [src, self.owner.name]  # path only has two nodes
                    rules = self.resource_reservation.create_rules_adaptive(path, reservation)
                    self.resource_reservation.load_rules_adaptive(rules, reservation)
                    reservation.set_path(path)
                    new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, msg.reservation, answer=True, path=path)
                else:                                                  # no available quantum memory
                    new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, msg.reservation, answer=False)
            self.owner.send_message(src, new_msg)
        
        elif msg.msg_type is ACMsgType.RESPOND:
            if msg.answer is False:           # neighbor doesn't has available memory
                for card in self.resource_reservation.timecards:
                    card.remove(msg.reservation) # clear up the timecards
                self.adaptive_memory_used -= 1
            else:                             # neighbor has available memory
                rules = self.resource_reservation.create_rules_adaptive(msg.path, msg.reservation)
                self.resource_reservation.load_rules_adaptive(rules, msg.reservation)
            self.start_delay(MILLISECOND)


    def adaptive_memory_used_minus_one(self) -> None:
        '''reduce the self.adaptive_memory_used by 1. Called when the entanglement generation protocol is expired
        '''
        log.logger.debug(f'{self.name}, adaptive_memory_used is reduced from {self.adaptive_memory_used} to {self.adaptive_memory_used - 1}')
        assert self.adaptive_memory_used > 0, f"{self.name}, adaptive_memory_used={self.adaptive_memory_used}"
        self.adaptive_memory_used -= 1


    def add_generated_entanglement_pair(self, entanglement_pair: tuple):
        '''track the new entanglement pair generated by the Adaptive Continuous protocol
        Args:
            entanglement_link: Tuple[(node_name, memory_name), (remote_node_name, remote_memory_name)]
        '''
        if entanglement_pair not in self.generated_entanglement_pairs:
            self.generated_entanglement_pairs.add(entanglement_pair)
        else:
            log.logger.warning(f'entanglement_pair {entanglement_pair} already exist')


    def match_generated_entanglement_pair(self, this_node_name: str, remote_node_name: str) -> tuple:
        '''match (this_node_name, remote_node_name) to an existing entanglement pair
        Return:
            Tuple[(node_name, memory_name), (remote_node_name, remote_memory_name)] -- the first matched entanglement link
            None -- if no match exist
        '''
        for entanglement_pair in sorted(self.generated_entanglement_pairs):
            ent_this_node_name   = entanglement_pair[0][0]
            ent_remote_node_name = entanglement_pair[1][0]
            if ent_this_node_name == this_node_name and ent_remote_node_name == remote_node_name:
                return entanglement_pair
        return None


    def remove_entanglement_pair(self, entanglement_pair: tuple):
        '''remove an entanglement_pair because it is used
        '''
        assert entanglement_pair in self.generated_entanglement_pairs, f'{entanglement_pair} not exist!'
        self.generated_entanglement_pairs.remove(entanglement_pair)
