'''Definition of Reservation protocol for the adaptive-continuous protocol
'''

from typing import TYPE_CHECKING, List
from sequence.network_management.reservation import ResourceReservationProtocol, Reservation, ResourceReservationMessage, QCap, RSVPMsgType
from sequence.resource_management.rule_manager import Rule
from rule_manager import RuleAdaptive
from sequence.network_management.reservation import eg_rule_action1, eg_rule_action2, eg_rule_condition, ep_rule_action1, ep_rule_condition1, ep_rule_action2, \
                                                    ep_rule_condition2, es_rule_actionB, es_rule_conditionB1, es_rule_actionA, es_rule_conditionA, es_rule_conditionB2
from sequence.kernel.event import Event
from sequence.kernel.process import Process

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive


class ReservationAdaptive(Reservation):
    """Tracking of reservation parameters for the network manager.
       Each request will generate a reservation

       Note: the only difference compared with the parant class is a minor change in __str__()
       
    Attributes:
        initiator (str): name of the node that created the reservation request.
        responder (str): name of distant node with witch entanglement is requested.
        start_time (int): simulation time at which entanglement should be attempted.
        end_time (int): simulation time at which resources may be released.
        memory_size (int): number of entangled memory pairs requested.
        path (list): a list of router names from the source to destination
    """

    def __init__(self, initiator: str, responder: str, start_time: int,
                 end_time: int, memory_size: int, fidelity: float):
        """Constructor for the reservation class.

        Args:
            initiator (str): node initiating the request.
            responder (str): node with which entanglement is requested.
            start_time (int): simulation start time of entanglement.
            end_time (int): simulation end time of entanglement.
            memory_size (int): number of entangled memories requested.
            fidelity (float): desired fidelity of entanglement.
        """
        super().__init__(initiator, responder, start_time, end_time, memory_size, fidelity)

    def __str__(self) -> str:
        return "|AdaptiveContinuous; initiator={}; responder={}; start_time={:,}; end_time={:,}; memory_size={}; target_fidelity={}|".format(
                self.initiator, self.responder, int(self.start_time), int(self.end_time), self.memory_size, self.fidelity)

    def __repr__(self) -> str:
        return self.__str__()



class ResourceReservationProtocolAdaptive(ResourceReservationProtocol):
    '''ReservationProtocol for node resources customized for adaptive-continuous protocol
    Task:
        update the cache
    '''

    def __init__(self, owner: "QuantumRouterAdaptive", name: str, memory_array_name: str):
        super().__init__(owner, name, memory_array_name)


    def create_rules_adaptive(self, path: list, reservation: ReservationAdaptive) -> List["Rule"]:
        """Method to create rules for entanglement generation (only) for a successful AC protocol's request.

        Rules are used to direct the flow of information/entanglement in the resource manager.

        Args:
            path (List[str]): list of node names in entanglement path.
            reservation (Reservation): approved reservation.

        Returns:
            List[Rule]: list of rules created by the method.
        """
        rules = []
        memory_indices = []
        for card in self.timecards:  # check which timecard includes the reservation
            if reservation in card.reservations:
                memory_indices.append(card.memory_index)

        index = path.index(self.owner.name)  # the location of this node along the path from initiator to responder

        # create rules for entanglement generation
        if index > 0:
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            action_args = {"mid": self.owner.map_to_middle_node[path[index - 1]], "path": path, "index": index}
            rule = Rule(10, eg_rule_action1, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        if index < len(path) - 1:
            if index == 0:
                condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:]}

            action_args = {"mid": self.owner.map_to_middle_node[path[index + 1]],
                           "path": path, "index": index, "name": self.owner.name, "reservation": reservation}
            rule = Rule(10, eg_rule_action2, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        for rule in rules:
            rule.set_reservation(reservation)
        
        return rules


    def load_rules_adaptive(self, rules: List[Rule], reservation: ReservationAdaptive):
        """Method to add AC protocol created rules to resource manager.

        This method will schedule the resource manager to load all rules at the reservation start time.
        The rules will be set to expire at the reservation end time.

        Args:
            rules (List[Rules]): rules to add.
            reservation (Reservation): reservation that created the rules.
        """

        self.accepted_reservation.append(reservation)
        for card in self.timecards:
            if reservation in card.reservations:
                process = Process(self.owner.resource_manager, "update", [None, self.memo_arr[card.memory_index], "RAW"])
                event = Event(reservation.end_time, process, 1)
                self.owner.timeline.schedule(event)

                process = Process(self.owner.adaptive_continuous, "adaptive_memory_used_minus_one", [self.memo_arr[card.memory_index]])
                event = Event(reservation.end_time, process, 2)
                self.owner.timeline.schedule(event)

        for rule in rules:
            process = Process(self.owner.resource_manager, "load", [rule])
            event = Event(reservation.start_time, process)
            self.owner.timeline.schedule(event)

            process = Process(self.owner.resource_manager, "expire", [rule])
            event = Event(reservation.end_time, process, 0)
            self.owner.timeline.schedule(event)


    def create_rules_request(self, path: list, reservation: ReservationAdaptive) -> List["Rule"]:
        """Method to create rules for a successful request.

        Note: Use the RuleAdaptive class for creating entanglement generation protocols

        Rules are used to direct the flow of information/entanglement in the resource manager.

        Args:
            path (List[str]): list of node names in entanglement path.
            reservation (Reservation): approved reservation.

        Returns:
            List[Rule]: list of rules created by the method.
        """

        rules = []
        memory_indices = []
        for card in self.timecards:
            if reservation in card.reservations:
                memory_indices.append(card.memory_index)

        index = path.index(self.owner.name)  # the location of this node along the path from initiator to responder

        # 1. create rules for entanglement generation
        if index > 0:
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            action_args = {"mid": self.owner.map_to_middle_node[path[index - 1]],
                           "path": path, "index": index}
            rule = RuleAdaptive(10, eg_rule_action1, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        if index < len(path) - 1:
            if index == 0:
                condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:]}

            action_args = {"mid": self.owner.map_to_middle_node[path[index + 1]],
                           "path": path, "index": index, "name": self.owner.name, "reservation": reservation}
            rule = RuleAdaptive(10, eg_rule_action2, eg_rule_condition, action_args, condition_args)
            rules.append(rule)

        # 2. create rules for entanglement purification
        if index > 0:
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size], "reservation": reservation}
            action_args = {}
            rule = Rule(10, ep_rule_action1, ep_rule_condition1, action_args, condition_args)
            rules.append(rule)

        if index < len(path) - 1:
            if index == 0:
                condition_args = {"memory_indices": memory_indices, "fidelity": reservation.fidelity}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:], "fidelity": reservation.fidelity}

            action_args = {}
            rule = Rule(10, ep_rule_action2, ep_rule_condition2, action_args, condition_args)
            rules.append(rule)

        # 3. create rules for entanglement swapping
        if index == 0:
            condition_args = {"memory_indices": memory_indices, "target_remote": path[-1], "fidelity": reservation.fidelity}
            action_args = {}
            rule = Rule(10, es_rule_actionB, es_rule_conditionB1, action_args, condition_args)
            rules.append(rule)
        elif index == len(path) - 1:
            action_args = {}
            condition_args = {"memory_indices": memory_indices, "target_remote": path[0], "fidelity": reservation.fidelity}
            rule = Rule(10, es_rule_actionB, es_rule_conditionB1, action_args, condition_args)
            rules.append(rule)
        else:
            _path = path[:]
            while _path.index(self.owner.name) % 2 == 0:
                new_path = []
                for i, n in enumerate(_path):
                    if i % 2 == 0 or i == len(_path) - 1:
                        new_path.append(n)
                _path = new_path
            _index = _path.index(self.owner.name)
            left, right = _path[_index - 1], _path[_index + 1]

            condition_args = {"memory_indices": memory_indices, "left": left, "right": right, "fidelity": reservation.fidelity}
            action_args = {"es_succ_prob": self.es_succ_prob, "es_degradation": self.es_degradation}
            rule = Rule(10, es_rule_actionA, es_rule_conditionA, action_args, condition_args)
            rules.append(rule)

            action_args = {}
            rule = Rule(10, es_rule_actionB, es_rule_conditionB2, action_args, condition_args)
            rules.append(rule)

        for rule in rules:
            rule.set_reservation(reservation)

        return rules


    def pop(self, src: str, msg: "ResourceReservationMessage"):
        """Method to receive messages from lower protocols.

        Messages may be of 3 types, causing different network manager behavior:

        1. REQUEST: requests are evaluated, and forwarded along the path if accepted. Otherwise a REJECT message is sent back.
        2. REJECT: any reserved resources are released and the message forwarded back towards the initializer.
        3. APPROVE: rules are created to achieve the approved request. The message is forwarded back towards the initializer.

        Args:
            src (str): source node of the message.
            msg (ResourceReservationMessage): message received.
        
        Side Effects:
            May push/pop to lower/upper attached protocols (or network manager).

        Assumption:
            the path initiator -> responder is same as the reverse path
        """

        if msg.msg_type == RSVPMsgType.REQUEST:
            assert self.owner.timeline.now() < msg.reservation.start_time
            if self.schedule(msg.reservation):
                qcap = QCap(self.owner.name)
                msg.qcaps.append(qcap)
                if self.owner.name == msg.reservation.responder:
                    path = [qcap.node for qcap in msg.qcaps]
                    rules = self.create_rules_request(path, reservation=msg.reservation)
                    self.load_rules(rules, msg.reservation)
                    msg.reservation.set_path(path)
                    new_msg = ResourceReservationMessage(RSVPMsgType.APPROVE, self.name, msg.reservation, path=path)
                    self._pop(msg=msg)
                    self._push(dst=msg.reservation.initiator, msg=new_msg)
                else:
                    self._push(dst=msg.reservation.responder, msg=msg)
            else:
                new_msg = ResourceReservationMessage(RSVPMsgType.REJECT, self.name, msg.reservation)
                self._push(dst=msg.reservation.initiator, msg=new_msg)
        elif msg.msg_type == RSVPMsgType.REJECT:
            for card in self.timecards:
                card.remove(msg.reservation)
            if msg.reservation.initiator == self.owner.name:
                self._pop(msg=msg)
            else:
                self._push(dst=msg.reservation.initiator, msg=msg)
        elif msg.msg_type == RSVPMsgType.APPROVE:
            rules = self.create_rules_request(msg.path, msg.reservation)
            self.load_rules(rules, msg.reservation)
            if msg.reservation.initiator == self.owner.name:
                self._pop(msg=msg)
            else:
                self._push(dst=msg.reservation.initiator, msg=msg)
        else:
            raise Exception("Unknown type of message", msg.msg_type)

