'''
Implement paper "Adaptive, Continuous Entanglement Generation for Quantum Networks" in SeQUeNCe
Paper link: https://ieeexplore.ieee.org/document/9798130
'''

from enum import Enum, auto
from itertools import accumulate
from bisect import bisect_left
from typing import TYPE_CHECKING, Optional

from sequence.message import Message
from sequence.protocol import Protocol
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.utils import log
from sequence.resource_management.memory_manager import MemoryManager
from sequence.constants import MILLISECOND, SECOND, EPSILON
from sequence.components.memory import Memory
from sequence.network_management.reservation import Reservation

from purification import BBPSSW_bds
from reservation import ResourceReservationProtocolAdaptive, ReservationAdaptive

if TYPE_CHECKING:
    from sequence.resource_management.rule_manager import Rule
    from node import QuantumRouterAdaptive
    from resource_manager import ResourceManagerAdaptive


class ACMsgType(Enum):
    '''Defines possible message types for the adaptive continuous (AC) protocol
    '''
    REQUEST = auto()    # ask if the neighbor has available memory
    RESPOND = auto()    # responding NO/YES
    CACHE   = auto()    # add entanlgement path to the cache
    EXPIRE  = auto()    # expire the rules generated by the requests when the requests are served before the end_time (not related to AC protocol)
    INFORM_EP = auto()  # for creating entanglement purification protocol


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
        
        elif self.msg_type == ACMsgType.CACHE:        # for updating the probability table
            self.timestamp = kwargs['timestamp']
            self.string += f', timestamp={self.timestamp}'

        elif self.msg_type == ACMsgType.INFORM_EP:
            self.selected_ep = kwargs['selected_ep']
            self.rule = kwargs['rule']
            self.string += f', selected_ep={self.selected_ep}'
            # self.string += f', selected_ep={self.selected_ep}, rule={self.rule}'

    def __str__(self):
        return f'|{self.string}|'


class AdaptiveContinuousProtocol(Protocol):
    '''This protocol continuously generates entanglement with its neighbor nodes. 
       The probability to which neighbor to entangle is computed adaptively regarding the user requests.

       This version uses the resource reservation protocol from the network manager, to use the reservation system

    New attributes:
        adaptive_max_memory (int): maximum number of memory used for Adaptive-continuous protocol
        adaptive_memory_used (int): the number of memory that is currently used by the adaptive continuous protocol
        resource_reservation (ResourceReservationProtocolAdaptive): the resource reservation protocol
        probability_table (dict): str -> float, the probability that decides which neighbor is selected
        generated_entanglement_pairs (set): each element is a tuple of (str, str), where each str is the name of the memory
        cache (list): store the history of entanglement paths
        update_prob (bool): whether update the probability table or not
        has_empty_neighbor (bool): whether the probability table has empty neighbor
    '''

    def __init__(self, owner: "QuantumRouterAdaptive", name: str, adaptive_max_memory: int, resource_reservation: ResourceReservationProtocolAdaptive):
        super().__init__(owner, name)
        self.adaptive_max_memory = adaptive_max_memory
        self.adaptive_memory_used = 0
        self.resource_reservation = resource_reservation
        self.probability_table = {}
        self.probability_table_update_count = 0
        self.generated_entanglement_pairs = set()
        self.cache = []  # each item is (timestamp: int, path: list)
        self.update_prob = True
        self.has_empty_neighbor = True
        self.strategy = "freshest"  # "random" or "freshest", for picking an entanglement pair given multiple entanglement pairs
        self.print_prob_table = False

    def init(self):
        '''deal with the probability table
        '''
        self.init_probability_table()
        elapse = SECOND
        self.update_probability_table_event(elapse)

    def set_adaptive_max_memory(self, adaptive_max_memory: int) -> None:
        '''set the max memory used for the adaptive continuousp protocol
        '''
        self.adaptive_max_memory = adaptive_max_memory

    def update_probability_table_event(self, elapse):
        self.update_probability_table(elapse)
        process = Process(self.owner.adaptive_continuous, "update_probability_table_event", [elapse])
        event = Event(self.owner.timeline.now() + elapse, process)
        self.owner.timeline.schedule(event)

    def start(self) -> None:
        '''start a new "cycle" of the adaptive-continuous protocol
        '''
        # check whether the adaptive protocol has used up its memory quota
        if self.adaptive_memory_used >= self.adaptive_max_memory:
            self.start_delay(delay = MILLISECOND)  # schedule a start event in the future
            return

        # select neighbor
        neighbor = self.select_neighbor()
        if neighbor == '':
            log.logger.debug(f'{self.owner.name} selected neighbor None')
            self.start_delay(delay = 10 * MILLISECOND)  # schedule a start event in the future
            return

        log.logger.debug(f'{self.owner.name} selected neighbor {neighbor}, adaptive_memory_used is increased from {self.adaptive_memory_used} to {self.adaptive_memory_used + 1}')
        self.adaptive_memory_used += 1
        round_trip_time = self.owner.cchannels[neighbor].delay * 2
        start_time = self.owner.timeline.now() + round_trip_time # consider a round trip time for the "handshaking"
        end_time = self.round_to_second(start_time + SECOND)     # the 'period' is one second
        # end_time = start_time + SECOND/3     # the 'period' is one second
        # set up reservation
        reservation = ReservationAdaptive(self.owner.name, neighbor, start_time, end_time, memory_size=1, fidelity=0.9)
        if self.resource_reservation.schedule(reservation):
            # able to schedule on current node, i.e., has memory
            msg = AdaptiveContinuousMessage(ACMsgType.REQUEST, reservation)
            self.owner.send_message(neighbor, msg)
        else:
            # not able to schedule on current node (lack of memory), schedule another start event after 1 ms
            self.adaptive_memory_used -= 1
            self.start_delay(delay = MILLISECOND)


    def start_delay(self, delay: float) -> None:
        '''create a "start" event after a random delay between [0, delay]
        Args:
            delay: schedule the event after some amount of delay (pico seconds) between 0 and delay
        '''
        if self.adaptive_max_memory > 0:      # only start if AC protocol is assigned some memories
            assert delay >= 0, f'delay = {delay} is negative'
            random_delay = int(self.owner.get_generator().uniform(0, delay))
            process = Process(self, 'start', [])
            event = Event(self.owner.timeline.now() + random_delay, process)
            self.owner.timeline.schedule(event)


    def init_probability_table(self):
        '''initialize the probability table computed from the static routing protocols' forwarding table
        '''
        probability_table = {}
        forwarding_table = self.owner.network_manager.protocol_stack[0].get_forwarding_table()
        neighbors = []
        for dst, next_hop in forwarding_table.items():
            if dst == next_hop:  # it is a neighbor when the destination equals the next hop in the forwarding table
                neighbors.append(dst)

        if self.has_empty_neighbor:
            neighbors.append('')  # add an empty string for chosing nothing

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
        neighbor = neighbors[index]
        return neighbor


    def received_message(self, src: str, msg: ACMsgType) -> None:
        '''override Protocol.received_message, method to receive AC Messages.

        Message come in 2 types, as detailed in the `ACMsgType` class

        Args:
            scr (str): name of the node that sent the message
            msg (ACMsgType): message received
        '''
        log.logger.debug('{} receive message from {}: {}'.format(self.owner.name, src, msg))

        if msg.msg_type is ACMsgType.REQUEST:
            if self.adaptive_memory_used >= self.adaptive_max_memory:  # AC Protocol cannot exceed adaptive_max_memory
                new_msg = AdaptiveContinuousMessage(ACMsgType.RESPOND, msg.reservation, answer=False)
                log.logger.debug(f'{self.owner.name} adaptive_memory_used reached the maximum')
            else:
                reservation = msg.reservation
                if self.resource_reservation.schedule(reservation):    # has available quantum memory
                    log.logger.debug(f'{self.owner.name} adaptive_memory_used is increased from {self.adaptive_memory_used} to {self.adaptive_memory_used + 1}')
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
                log.logger.debug(f'{self.owner.name} not going to establish entanglement link {self.owner.name}-{src}; adaptive_memory_used is decreased from {self.adaptive_memory_used} to {self.adaptive_memory_used - 1}')
                self.adaptive_memory_used -= 1
            else:                             # neighbor has available memory
                rules = self.resource_reservation.create_rules_adaptive(msg.path, msg.reservation)
                self.resource_reservation.load_rules_adaptive(rules, msg.reservation)
                log.logger.info(f'{self.owner.name} attempting to establish entanglement link {self.owner.name}-{src}')
            self.start_delay(3 * MILLISECOND)
        
        elif msg.msg_type is ACMsgType.CACHE:
            timestamp = msg.timestamp
            path = msg.reservation.path
            self.cache.append((timestamp, path))
            log.logger.debug(f'{self.owner.name} added {(timestamp, path)} to cache')
        
        elif msg.msg_type is ACMsgType.EXPIRE:
            # This job should be done by the resource manager. 
            # Didn't do it because of not wanting to add a Message type in the Resource Manager
            reservation = msg.reservation
            resource_manager = self.get_resource_manager()
            resource_manager.expire_rules_by_reservation(reservation)

        elif msg.msg_type is ACMsgType.INFORM_EP:
            # This job should be done by the resource manager (rules generate protocols)
            # Didn't do it because didn't want to add a Message type in the Resource Manager
            # create the purification protocol.
            entanglement_pair, entanglement_pair2 = msg.selected_ep  # ((node_name, memory_name), (remote_node_name, remote_memory_name))
            rule = msg.rule
            if rule in rule.rule_manager.rules:   # AC Protocol expired while the message is traveling in the air
                entanglement_pair  = (entanglement_pair[1],  entanglement_pair[0])  # remote node to local node
                entanglement_pair2 = (entanglement_pair2[1], entanglement_pair2[0])
                self.remove_entanglement_pair(entanglement_pair)
                self.remove_entanglement_pair(entanglement_pair2)
                purification_protocol = self.create_purification_protocol(entanglement_pair, entanglement_pair2, rule)
                self.owner.protocols.append(purification_protocol)
                if purification_protocol.is_ready():
                    purification_protocol.start()
                else:
                    raise Exception('Program should not run here')
            else:
                log.logger.info(f'Rule expired: {rule}')


    def adaptive_memory_used_minus_one(self, memory: Memory) -> None:
        '''reduce the self.adaptive_memory_used by 1. Called right after the entanglement generation protocol is expired
        Args:
            memory: this is the memory that is set to RAW (due to expired rule), released from the adaptive continuous protocol
        '''
        assert self.adaptive_memory_used > 0, f"{self.owner.name} adaptive_memory_used={self.adaptive_memory_used}"
        self.adaptive_memory_used -= 1
        log.logger.debug(f'{self.owner.name} adaptive_memory_used is reduced from {self.adaptive_memory_used + 1} to {self.adaptive_memory_used}')
        # remove the entanglement pair that memory is in
        ep_to_delete = None
        for entanglement_pair in self.generated_entanglement_pairs:
            if entanglement_pair[0][1] == memory.name:
                ep_to_delete = entanglement_pair
                break
            elif entanglement_pair[1][1] == memory.name:
                ep_to_delete = entanglement_pair
                break
        if ep_to_delete is None:  # the entanglement pair that includes argument memory doesn't exist, because the EP generation is not successfull yet
            log.logger.info(f'{self.owner.name} {memory.name} is not found in self.generated_entanglement_pairs!')
        else:
            self.generated_entanglement_pairs.remove(ep_to_delete)
            log.logger.info(f'{self.owner.name} removed EP {ep_to_delete}')


    def update_probability_table(self, elapse: int):
        '''update the probability table
        Args:
            elapse: consider the paths whose timestamp is withini [current_time - elapse, current_time]
        '''
        if self.probability_table_update_count == 0:
            self.probability_table_update_count += 1
            return
        if self.update_prob == False:
            return
        # print(self.probability_table)
        # 1. get all the entanglement paths
        current_time = self.owner.timeline.now()
        paths = []
        for i in range(len(self.cache) - 1, -1, -1):
            timestamp = self.cache[i][0]
            if current_time - elapse <= timestamp:
                paths.append(self.cache[i][1])
        # print(f'{self.owner.name} {paths}')
        # 2. get the all the neighbors that is in the entanglement path
        neighbor_in_path = set()
        this_node = self.owner.name
        for path in paths:
            this_index = None
            for i in range(len(path)):
                if path[i] == this_node:
                    this_index = i
                    break
            if this_index is not None:
                if this_index >= 1:
                    neighbor_in_path.add(path[this_index - 1])
                if this_index <= len(path) - 2:
                    neighbor_in_path.add(path[this_index + 1])
        # 3.1 if neighbor is in the set neighbor_in_path, then increase probability
        # delta = 1 / len(self.probability_table.keys())
        delta = 0.05
        exist = False
        for neighbor in self.probability_table.keys():
            if neighbor != '' and neighbor in neighbor_in_path:
                self.probability_table[neighbor] += delta
                exist = True
        if exist is False and self.has_empty_neighbor:
            self.probability_table[''] += delta
        # 3.2 normalize the probability table
        summ = sum(self.probability_table.values())
        for neighbor in self.probability_table.keys():
            self.probability_table[neighbor] /= summ

        if self.print_prob_table:
            print(f'{self.owner.name}, {self.probability_table_update_count}, ', end = '')
            for node, prob in self.probability_table.items():
                if node != '':
                    print(f'{node}: {prob:.4}', end = ' ')
                else:
                    print(f'None: {prob:.4}', end = ' ')
            print()

        self.probability_table_update_count += 1


    def add_generated_entanglement_pair(self, entanglement_pair: tuple):
        '''track the new entanglement pair generated by the Adaptive Continuous protocol
        Args:
            entanglement_link: Tuple[(node_name, memory_name), (remote_node_name, remote_memory_name)]
        '''
        if entanglement_pair not in self.generated_entanglement_pairs:
            self.generated_entanglement_pairs.add(entanglement_pair)
            log.logger.info(f'{self.owner.name} added EP {entanglement_pair}')
        else:
            log.logger.warning(f'{self.owner.name} EP {entanglement_pair} already exist')


    def match_generated_entanglement_pair(self, this_node_name: str, remote_node_name: str) -> Optional[tuple]:
        '''match (this_node_name, remote_node_name) to an existing entanglement pair
        
        Return:
            Tuple[(node_name, memory_name), (remote_node_name, remote_memory_name)] -- the freshest entanglement pair
            None -- if no match exist
        '''
        entanglement_pairs = []
        for entanglement_pair in sorted(self.generated_entanglement_pairs):
            ent_this_node_name   = entanglement_pair[0][0]
            ent_remote_node_name = entanglement_pair[1][0]
            if ent_this_node_name == this_node_name and ent_remote_node_name == remote_node_name:
                entanglement_pairs.append(entanglement_pair)
        
        if len(entanglement_pairs) == 0:
            return None

        if self.strategy == "random":
            return entanglement_pairs[0]
        elif self.strategy == "freshest":
            freshest_ep = None
            best_fidelity = 0
            for ep in entanglement_pairs:
                fidelity = self.get_fidelity(ep)
                if fidelity > best_fidelity:
                    freshest_ep = ep
                    best_fidelity = fidelity
            return freshest_ep
        else:
            raise Exception(f'{self.strategy} not supported')


    def get_fidelity(self, entanglement_pair: tuple) -> float:
        '''
        Args:
            entanglement_pair (tuple): the entanglement pair created by the ACP, ((node_name, memory_name), (remote_node_name, remote_memory_name))
        Return:
            float: the fidelity of the entanglement pair, will update the fidelity
        '''
        local_memory_name  = entanglement_pair[0][1]
        remote_memory_name = entanglement_pair[1][1]
        local_memory: Memory = self.owner.timeline.get_entity_by_name(local_memory_name)
        remote_memory: Memory = self.owner.timeline.get_entity_by_name(remote_memory_name)
        local_memory.bds_decohere()
        remote_memory.bds_decohere()
        return local_memory.get_bds_fidelity()

    def remove_entanglement_pair(self, entanglement_pair: tuple):
        '''remove an entanglement_pair because it is used
        
        Side Effect:
            Will raise Exception when the entanglement_pair doesn't exist. 
            It will happen when an expire event happend in the middle of a swap memory protocol, which takes 2 ms long
        '''
        entanglement_pair2 = (entanglement_pair[1], entanglement_pair[0])
        if entanglement_pair in self.generated_entanglement_pairs:
            self.generated_entanglement_pairs.remove(entanglement_pair)
            log.logger.info(f'{self.owner.name} removed EP {entanglement_pair}')
        elif entanglement_pair2 in self.generated_entanglement_pairs:
            self.generated_entanglement_pairs.remove(entanglement_pair2)
            log.logger.info(f'{self.owner.name} removed EP {entanglement_pair2}')
        else:
            raise Exception(f"{entanglement_pair} doesn't exist in {self.name}")
            

    def round_to_second(self, time: int) -> int:
        '''turn 1.001 second into 1 second
        
        Args:
            time: in picoseconds
        '''
        return (time // SECOND) * SECOND


    def send_entanglement_path(self, node: str, timestamp: float, reservation: Reservation):
        '''send the entanlgment path to the node

        Args:
            node: the name of the destination node
            timestamp: the time
            reservation: the reservation reserved by the AC protocol
        '''
        msg = AdaptiveContinuousMessage(ACMsgType.CACHE, reservation, timestamp=timestamp)
        self.owner.send_message(node, msg)


    def send_expire_rules_message(self, node: str, reservation: Reservation) -> None:
        '''send messages to node to expire the rules generated by reseravation

        Args:
            node: send message to this node
            reseravation: the rules generated by this reservation (from request) will expire
        '''
        msg = AdaptiveContinuousMessage(ACMsgType.EXPIRE, reservation)
        self.owner.send_message(node, msg)


    def get_resource_manager(self) -> "ResourceManagerAdaptive":
        return self.owner.resource_manager


    def get_entanglement_pair2(self, entanglement_pair: tuple) -> Optional[tuple]:
        '''given an entanglement_pair, find an other entanglement_pair between the same two nodes (for purification). 
           Both two nodes select the EP whose fidelity is the closest.
        
        Args:
            entanglement_pair (tuple): the entanglement pair created by the ACP, ((node_name, memory_name), (remote_node_name, remote_memory_name))
        Return:
            entanglement_pair or None
        '''
        this_fidelity = 0
        eps = []
        this_node  = entanglement_pair[0][0]
        other_node = entanglement_pair[1][0]
        for ep in self.generated_entanglement_pairs:
            if ep == entanglement_pair:
                this_fidelity = self.get_fidelity(ep)
            else:
                if ep[0][0] == this_node and ep[1][0] == other_node:
                    eps.append(ep)

        if eps:
            closest_ep = None
            fidelity_difference = 1
            for ep in eps:
                fidelity = self.get_fidelity(ep)
                difference = abs(this_fidelity - fidelity)
                if difference < fidelity_difference:
                    closest_ep = ep
                    fidelity_difference = difference
            return closest_ep
        else:
            return None


    def create_purification_protocol(self, entanglement_pair: tuple, entanglement_pair2: tuple, rule: Rule) -> BBPSSW_bds:
        '''given two entanglement pairs, create the purification protocol and pair it directly 
        (instead of creating the purification through rules and pairing in the resource management)
        
        Args:
            entanglement_pair (tuple):  ((node_name, memory_name), (remote_node_name, remote_memory_name))
            entanglement_pair2 (tuple): ((node_name, memory_name), (remote_node_name, remote_memory_name))
            rule (Rule): the rule that the purification is associated with, this rule should be eg_rule_action_adaptive, when it expires, it will remove the purification from self.owner.protocols
        Return:
            BBPSSW_bds: the purification protocol
        '''
        assert entanglement_pair[0][0] == entanglement_pair2[0][0], 'this node does not match'
        assert entanglement_pair[1][0] == entanglement_pair2[1][0], 'remote node does not match'
        # this_node_name    = entanglement_pair[0][0]
        this_memory1_name = entanglement_pair[0][1]
        this_memory2_name = entanglement_pair2[0][1]
        remote_node_name    = entanglement_pair2[1][0]
        remote_memory1_name = entanglement_pair[1][1]
        remote_memory2_name = entanglement_pair2[1][1]
        name = "EP_bds.{}.{}".format(this_memory1_name, this_memory2_name)
        this_memory1: Memory = self.owner.timeline.get_entity_by_name(this_memory1_name)  # kept memory
        this_memory2: Memory = self.owner.timeline.get_entity_by_name(this_memory2_name)  # meas memory
        purification_protocol = BBPSSW_bds(self.owner, name, this_memory1, this_memory2)
        # update memory observer and memory info
        this_memory1.detach(this_memory1.memory_array)   # set observer
        this_memory1.attach(purification_protocol)
        this_memory2.detach(this_memory2.memory_array)
        this_memory2.attach(purification_protocol)
        memory_manager = self.get_memory_manager()
        this_info1 = memory_manager.get_info_by_memory(this_memory1)
        this_info2 = memory_manager.get_info_by_memory(this_memory2)
        this_info1.to_occupied()                         # set memory_info to occupied
        this_info2.to_occupied()
        remote_protocol_name = "EP_bds.{}.{}".format(remote_memory1_name, remote_memory2_name)
        memories = [remote_memory1_name, remote_memory2_name]
        purification_protocol.set_others(remote_protocol_name, remote_node_name, memories)
        purification_protocol.rule = rule
        rule.protocols.append(purification_protocol)  # when the rule expires, it clears this purification protocol
        return purification_protocol


    def get_memory_manager(self) -> MemoryManager:
        '''get the memory manager that is associated to self.owner
        '''
        return self.owner.resource_manager.memory_manager
