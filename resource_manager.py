"""The Resource Manager customized for the adaptive continuous protocol
"""

from typing import TYPE_CHECKING, Optional, List, Dict, Any, Tuple

from sequence.resource_management.resource_manager import ResourceManager
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol
from sequence.entanglement_management.purification.bbpssw_circuit import BBPSSWCircuit
from sequence.entanglement_management.swapping import EntanglementSwappingA, EntanglementSwappingB
from sequence.components.memory import Memory
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.utils import log
from sequence.network_management.reservation import Reservation
from sequence.network_management.memory_timecard import MemoryTimeCard
from sequence.resource_management.rule_manager import Arguments
from sequence.resource_management.resource_manager import RequestConditionFunc, ResourceManagerMsgType, ResourceManagerMessage
from sequence.kernel.process import Process
from sequence.kernel.event import Event
from sequence.resource_management.rule_manager import Rule
from sequence.resource_management.action_condition_set import eg_rule_condition, ep_rule_condition_request as ep_rule_condition1, ep_rule_condition_await as ep_rule_condition2, es_rule_condition_B as es_rule_conditionB1, es_rule_condition_A as es_rule_conditionA, es_rule_condition_B_end as es_rule_conditionB2

from swapping import EntanglementSwappingA_bds, EntanglementSwappingB_bds
from generation import EntanglementGenerationAadaptive, ShEntanglementGenerationAadaptive
from memory_manager import MemoryManagerAdaptive
from adaptive_continuous import AdaptiveContinuousProtocol, AdaptiveContinuousMessage, ACMsgType
from purification import BBPSSW_bds
from reservation import ReservationAdaptive

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive

# 1. entanglement generation #

def eg_rule_action1_adaptive(memories_info: List["MemoryInfo"], args: Dict[str, Any]) -> \
                             Tuple[EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive, List[None], List[None], List[None]]:
    """Action function used by entanglement generation protocol on nodes except the initiator, i.e., index > 0
    """
    memories = [info.memory for info in memories_info]
    memory = memories[0]
    mid = args["mid"]
    path = args["path"]
    index = args["index"]
    from_app_request = args["from_app_request"]
    encoding_type = args["encoding_type"]
    if encoding_type == "single_atom":
        protocol_name = "EGAa." + memory.name
        protocol = EntanglementGenerationAadaptive(None, protocol_name, mid, path[index - 1], memory, from_app_request)
    elif encoding_type == "single_heralded":
        protocol_name = "ShEGAa." + memory.name
        raw_epr_errors = args["raw_epr_errors"]
        protocol = ShEntanglementGenerationAadaptive(None, protocol_name, mid, path[index - 1], memory, from_app_request, raw_epr_errors)
    else:
        raise ValueError(f'encoding type {encoding_type} not supported yet')
    return protocol, [None], [None], [None]


def eg_rule_action2_adaptive(memories_info: List["MemoryInfo"], args: Arguments) -> \
                             Tuple[EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive, List[str], List["eg_req_func_adaptive"], List[Dict]]:
    """Action function used by entanglement generation protocol on nodes except the responder, i.e., index < len(path) - 1
    """
    mid = args["mid"]
    path = args["path"]
    index = args["index"]
    memories = [info.memory for info in memories_info]
    memory = memories[0]
    from_app_request = args["from_app_request"]
    encoding_type = args["encoding_type"]
    if encoding_type == "single_atom":
        protocol_name = "EGAa." + memory.name
        protocol = EntanglementGenerationAadaptive(None, protocol_name, mid, path[index + 1], memory, from_app_request)
    elif encoding_type == "single_heralded":
        protocol_name = "ShEGAa." + memory.name
        raw_epr_errors = args["raw_epr_errors"]
        protocol = ShEntanglementGenerationAadaptive(None, protocol_name, mid, path[index + 1], memory, from_app_request, raw_epr_errors)
    else:
        raise ValueError(f'encoding type {encoding_type} not supported yet')
    req_args = {"name": args["name"], "reservation": args["reservation"]}
    return protocol, [path[index + 1]], [eg_req_func_adaptive], [req_args]


def eg_req_func_adaptive(protocols: List["EntanglementProtocol"], args: Arguments) -> EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive:
    """Function used by `eg_rule_action2` function for selecting generation protocols on the remote node
    Args:
        protocols: the waiting protocols (wait for request)
        args: arguments from the node who sent the request
    Return:
        the selected protocol (there could be multiple protocols that satisfy the condition, if so, return the first protocol)
    """
    name = args["name"]
    reservation = args["reservation"]
    for protocol in protocols:
        if (isinstance(protocol, EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive)
                and protocol.remote_node_name == name
                and protocol.rule.get_reservation() == reservation):
            return protocol


# 2. entanglement purification #

def ep_rule_action1_adaptive(memories_info: List["MemoryInfo"], args: Arguments) -> Tuple[BBPSSWCircuit | BBPSSW_bds, List[str], List["ep_req_func1_adaptive"], List[Dict]]:
    """Action function used by BBPSSW protocol on nodes except the initiator node
    """
    encoding_type=args["encoding_type"]
    memories = [info.memory for info in memories_info]
    if encoding_type == "single_atom":
        name = "EP.%s.%s" % (memories[0].name, memories[1].name)
        protocol = BBPSSWCircuit(None, name, memories[0], memories[1])
    elif encoding_type == "single_heralded":
        name = "EP_bds.%s.%s" % (memories[0].name, memories[1].name)
        protocol = BBPSSW_bds(None, name, memories[0], memories[1])

    dsts = [memories_info[0].remote_node]
    req_funcs = [ep_req_func1_adaptive]
    req_args = [{"remote0": memories_info[0].remote_memo, "remote1": memories_info[1].remote_memo}]
    return protocol, dsts, req_funcs, req_args


def ep_rule_action2_adaptive(memories_info: List["MemoryInfo"], args: Arguments) -> Tuple[BBPSSWCircuit | BBPSSW_bds, List[None], List[None], List[None]]:
    """Action function used by BBPSSW protocol on nodes except the responder node
    """
    encoding_type = args['encoding_type']
    memories = [info.memory for info in memories_info]
    if encoding_type == "single_atom":
        name = "EP.%s" % memories[0].name
        protocol = BBPSSWCircuit(None, name, memories[0], None)
    elif encoding_type == "single_heralded":
        name = "EP_bds.%s" % memories[0].name
        protocol = BBPSSW_bds(None, name, memories[0], None)
    return protocol, [None], [None], [None]


def ep_req_func1_adaptive(protocols, args: Arguments) -> BBPSSWCircuit | BBPSSW_bds:
    """Function used by `ep_rule_action1` for selecting purification protocols on the remote node
       Will "combine" two BBPSSW into one BBPSSW

    Args:
        protocols (list): a list of waiting protocols
        args (dict): the arguments
    Return:
        the selected protocol
    """
    remote0 = args["remote0"]
    remote1 = args["remote1"]

    _protocols = []
    for protocol in protocols:
        if not (isinstance(protocol, BBPSSWCircuit) or isinstance(protocol, BBPSSW_bds)):
            continue

        if protocol.kept_memo.name == remote0:
            _protocols.insert(0, protocol)     # 0 is kept
        if protocol.kept_memo.name == remote1:
            _protocols.insert(1, protocol)     # 1 is meas

    if len(_protocols) != 2:
        return None

    protocols.remove(_protocols[1])            # remove the EP_bds for meas
    _protocols[1].rule.protocols.remove(_protocols[1])
    _protocols[1].kept_memo.detach(_protocols[1])
    _protocols[0].meas_memo = _protocols[1].kept_memo  # [0]'s meas is [1]'s kept
    _protocols[0].memories = [_protocols[0].kept_memo, _protocols[0].meas_memo]
    _protocols[0].name = _protocols[0].name + "." + _protocols[0].meas_memo.name
    _protocols[0].meas_memo.attach(_protocols[0])

    return _protocols[0]



# 3. entanglement swapping #

def es_rule_actionA_adaptive(memories_info: List["MemoryInfo"], args: Arguments) -> Tuple[EntanglementSwappingA | EntanglementSwappingA_bds, List[str], List["es_req_func_adaptive"], List[Dict]]:
    """Action function used by EntanglementSwappingA protocol on nodes
    """
    es_succ_prob = args["es_succ_prob"]
    memories = [info.memory for info in memories_info]
    encoding_type = args["encoding_type"]
    
    if encoding_type == "single_atom":
        es_degradation = args["es_degradation"]
        name = "ESA.{}.{}".format(memories[0].name, memories[1].name)
        protocol = EntanglementSwappingA(None, name, memories[0], memories[1], es_succ_prob, es_degradation)
    elif encoding_type == 'single_heralded':
        is_twirled = args['is_twirled']
        name = "ESA_bds.{}.{}".format(memories[0].name, memories[1].name)
        protocol = EntanglementSwappingA_bds(None, name, memories[0], memories[1], es_succ_prob, is_twirled)

    dsts = [info.remote_node for info in memories_info]
    req_funcs = [es_req_func_adaptive, es_req_func_adaptive]
    req_args = [{"target_memo": memories_info[0].remote_memo}, {"target_memo": memories_info[1].remote_memo}]
    return protocol, dsts, req_funcs, req_args


def es_rule_actionB_adaptive(memories_info: List["MemoryInfo"], args: Arguments) -> Tuple[EntanglementSwappingB | EntanglementSwappingB_bds, List[None], List[None], List[None]]:
    """Action function used by EntanglementSwappingB protocol
    """
    memories = [info.memory for info in memories_info]
    memory = memories[0]
    encoding_type = args["encoding_type"]
    if encoding_type == "single_atom":
        protocol = EntanglementSwappingB(None, "ESB." + memory.name, memory)
    elif encoding_type == 'single_heralded':
        protocol = EntanglementSwappingB_bds(None, "ESB_bds." + memory.name, memory)
    return protocol, [None], [None], [None]


def es_req_func_adaptive(protocols: List["EntanglementProtocol"], args: Arguments) -> EntanglementSwappingB_bds | EntanglementSwappingB_bds:
    """Function used by `es_rule_actionA` for selecting swapping protocols on the remote node
    """
    target_memo = args["target_memo"]
    for protocol in protocols:
        if (isinstance(protocol, EntanglementSwappingB | EntanglementSwappingB_bds)
                # and protocol.memory.name == memories_info[0].remote_memo):
                and protocol.memory.name == target_memo):
            return protocol

class ResourceManagerAdaptive(ResourceManager):
    """Class to define the resource manager.

    Note: needs to keep track which entanglement pairs are generated via the Adaptive Continuous protocol

    The resource manager uses a memory manager to track memory states for the entanglement protocols.
    It also uses a rule manager to direct the creation and operation of entanglement protocols.

    Attributes:
        name (str): label for manager instance.
        owner (QuantumRouter): node that resource manager is attached to.
        memory_manager (MemoryManager): internal memory manager object.
        rule_manager (RuleManager): internal rule manager object.
        pending_protocols (List[Protocol]): list of protocols awaiting a response for a remote resource request.
        waiting_protocols (List[Protocol]): list of protocols awaiting a request from a remote protocol.
        purify (bool): whether enable purification
    """

    def __init__(self, owner: "QuantumRouterAdaptive", memory_array_name: str):
        super().__init__(owner, memory_array_name)
        self.memory_manager = MemoryManagerAdaptive(owner.components[memory_array_name])
        self.memory_manager.set_resource_manager(self)
        self.purify = False

        self.es_succ_prob = 1
        self.es_degradation = 0

    def update(self, protocol: "EntanglementProtocol", memory: "Memory", state: str) -> None:
        """Override. Method to update state of memory after completion of entanglement management protocol.

        Args:
            protocol (EntanglementProtocol): concerned protocol. If not None, then remove it from everywhere
            memory (Memory): memory to update.
            state (str): new state for the memory.

        Side Effects:
            May modify memory state, and modify any attached protocols.
            May add generated entanglement pair into the adaptive_continuous
        """

        self.memory_manager.update(memory, state)

        if protocol:
            memory.detach(protocol)
            memory.attach(memory.memory_array)
            if protocol in protocol.rule.protocols:
                protocol.rule.protocols.remove(protocol)

            # let the AC protocol track this entanglement link
            if isinstance(protocol, EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive) and state == MemoryInfo.ENTANGLED: # entanglement succeed
                if isinstance(protocol.rule.reservation, ReservationAdaptive): # Adaptive Continuous Protocol's reservation
                    adaptive_continuous = self.get_adaptive_continuous_protocol()
                    entanglement_pair = ((self.owner.name, memory.name), (memory.entangled_memory['node_id'], memory.entangled_memory['memo_id']))
                    adaptive_continuous.add_generated_entanglement_pair(entanglement_pair)

                    # entanglement purification
                    if self.purify and protocol.primary:  # the primary node select the EP
                        entanglement_pair2 = adaptive_continuous.get_entanglement_pair2(entanglement_pair)
                        if entanglement_pair2:
                            adaptive_continuous.remove_entanglement_pair(entanglement_pair)
                            adaptive_continuous.remove_entanglement_pair(entanglement_pair2)
                            purification_protocol = adaptive_continuous.create_purification_protocol(entanglement_pair, entanglement_pair2, protocol.rule)
                            self.owner.protocols.append(purification_protocol)

                            # NOTE: The purification protocol at the non-primary node is created by the AC Protocol, which shouldn't be (it should be the resource manager)
                            # I am letting the AC Protocol creating it because I don't want to add a new message type to Resource Manager and make changes
                            msg = AdaptiveContinuousMessage(ACMsgType.INFORM_EP, reservation=protocol.rule.reservation, selected_ep=(entanglement_pair, entanglement_pair2), rule=protocol.rule)
                            self.owner.send_message(protocol.remote_node_name, msg)

                            if purification_protocol.is_ready():
                                classical_delay = self.owner.cchannels[protocol.remote_node_name].delay
                                future_purify_time = self.owner.timeline.now() + classical_delay
                                process = Process(purification_protocol, 'start', [])
                                event = Event(future_purify_time, process)
                                self.owner.timeline.schedule(event)
                            else:
                                raise Exception('Program should not run to here')

            # let the AC protocol track the purified kept memory
            if self.purify and isinstance(protocol, BBPSSW_bds) and state == MemoryInfo.ENTANGLED:
                adaptive_continuous = self.get_adaptive_continuous_protocol()
                entanglement_pair = ((self.owner.name, memory.name), (memory.entangled_memory['node_id'], memory.entangled_memory['memo_id']))
                adaptive_continuous.add_generated_entanglement_pair(entanglement_pair)


        if protocol in self.owner.protocols:
            self.owner.protocols.remove(protocol)

        if protocol in self.waiting_protocols:
            self.waiting_protocols.remove(protocol)

        if protocol in self.pending_protocols:
            self.pending_protocols.remove(protocol)

        # check if any rules have been met. If no rule met, then get_idle_memory()
        memo_info = self.memory_manager.get_info_by_memory(memory)
        for rule in self.rule_manager:
            memories_info = rule.is_valid(memo_info)
            if len(memories_info) > 0:
                rule.do(memories_info)
                for info in memories_info:
                    info.to_occupied()
                return

        self.owner.get_idle_memory(memo_info)


    def expire(self, rule: "Rule") -> None:
        """Method to remove expired rule.

        override parent method

        Will update (remove) rule in rule manager.
        Will also update (remove) protocols connected to the rule (if they have already been created, and not finished yet).

        Args:
            rule (Rule): rule to remove.
        """

        log.logger.info('{} expire rule {}'.format(self.owner.name, rule))
        created_protocols = self.rule_manager.expire(rule)
        while created_protocols:
            protocol = created_protocols.pop()
            if protocol in self.waiting_protocols:
                self.waiting_protocols.remove(protocol)
            elif protocol in self.pending_protocols:
                self.pending_protocols.remove(protocol)
            elif protocol in self.owner.protocols:
                self.owner.protocols.remove(protocol)
            else:
                if isinstance(protocol, BBPSSW_bds):
                    log.logger.info(f'Purification protocol {protocol} to be removed is located on the neighbor node')
                    continue
                else:
                    raise Exception("Unknown place of protocol")

            for memory in protocol.memories:
                self.update(protocol, memory, MemoryInfo.RAW)


    def send_request(self, protocol: "EntanglementProtocol", req_dst: Optional[str], req_condition_func: RequestConditionFunc, req_args: Arguments):
        """Override. Method to send protocol request to another node.

        Send the request to pair the local 'protocol' with the protocol on the remote node 'req_dst'.
        The function `req_condition_func` describes the desired protocol.

        Args:
            protocol (EntanglementProtocol): protocol sending the request.
            req_dst (str): name of destination node.
            req_condition_func (Callable[[List[EntanglementProtocol]], EntanglementProtocol]):
                function used to evaluate condition on distant node.
            req_args (Dict[str, Any]): arguments for req_cond_func.
        """

        protocol.owner = self.owner
        if req_dst is None:
            self.waiting_protocols.append(protocol)
            return
        if protocol not in self.pending_protocols:
            self.pending_protocols.append(protocol)
        memo_names = [memo.name for memo in protocol.memories]
        msg = ResourceManagerMessage(ResourceManagerMsgType.REQUEST, protocol=protocol.name, node=self.owner.name,
                                     memories=memo_names, req_condition_func=req_condition_func, req_args=req_args)
        self.owner.send_message(req_dst, msg)
        if isinstance(protocol, EntanglementGenerationAadaptive | ShEntanglementGenerationAadaptive) and req_dst is not None:
            protocol.node_send_resource_management_request = True  # to decrease the time spend on resource manager pairing
        log.logger.debug("{} send {} message to {}".format(self.owner.name, msg.msg_type.name, req_dst))


    def update_swap_memory(self, protocol: "EntanglementProtocol", memory: "Memory") -> None:
        """Method to update state of memory after completion of entanglement management protocol.

        Compared with update(): 1) the update_swap_memory() don't have the self.memory_manager.update() in the first line
        2) Also, don't need to inform the AC protocol

        Args:
            protocol (EntanglementProtocol): concerned protocol. If not None, then remove it from everywhere
            memory (Memory): memory to update.

        Side Effects:
            May modify memory state, and modify any attached protocols.
            May add generated entanglement pair into the adaptive_continuous
        """

        if protocol:
            memory.detach(protocol)
            memory.attach(memory.memory_array)
            if protocol in protocol.rule.protocols:
                protocol.rule.protocols.remove(protocol)

        if protocol in self.owner.protocols:
            self.owner.protocols.remove(protocol)

        if protocol in self.waiting_protocols:
            self.waiting_protocols.remove(protocol)

        if protocol in self.pending_protocols:
            self.pending_protocols.remove(protocol)

        # check if any rules have been met
        memo_info = self.memory_manager.get_info_by_memory(memory)
        for rule in self.rule_manager:
            memories_info = rule.is_valid(memo_info)
            if len(memories_info) > 0:
                rule.do(memories_info)
                for info in memories_info:
                    info.to_occupied()
                return

        self.owner.get_idle_memory(memo_info)  # no new rules apply to this memory, thus "idle"


    def get_adaptive_continuous_protocol(self) -> AdaptiveContinuousProtocol:
        '''return the adaptive continuous protocol
        '''
        return self.owner.adaptive_continuous


    def swap_two_memory(self, occupied_memory_name: str, entangled_memory_name: str):
        '''swap two quantum memories
        
        Args:
            occupied_memory_name: name of memory in occupied status (from the request)
            entangled_memory_name: name of memory in entangled status (from the AC protocol)
        '''
        self.memory_manager.swap_two_memory(occupied_memory_name, entangled_memory_name)


    def check_entangled_memory(self, entangled_memory_name: str) -> bool:
        '''return True if the memory by parameter entangled_memory_name is indeed entangled, otherwise False
        
        Args:
            entangled_memory_name: the name of the memory being checked
        '''
        return self.memory_manager.check_entangled_memory(entangled_memory_name)


    def expire_rules_by_reservation(self, reservation: Reservation) -> None:
        '''expire rules created by the reservation
        
        Args:
            reservation: the rules created by this reservation will expire
        '''
        rule_to_expire = []
        for rule in self.rule_manager.rules:
            if rule.reservation == reservation:
                rule_to_expire.append(rule)
        
        for rule in rule_to_expire:
            self.expire(rule)

    def create_rules_adaptive(self, path: list, reservation: ReservationAdaptive, timecards: list[MemoryTimeCard]) -> List["Rule"]:
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
        for card in timecards:  # check which timecard includes the reservation
            if reservation in card.reservations:
                memory_indices.append(card.memory_index)

        index = path.index(self.owner.name)  # the location of this node along the path from initiator to responder
        
        priority = 20
        # create rules for entanglement generation
        if index > 0:
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            action_args = {"mid": self.owner.map_to_middle_node[path[index - 1]], "path": path, "index": index, "from_app_request": False,
                           "encoding_type": "single_heralded", "raw_epr_errors": [1/3, 1/3, 1/3]}
            rule = Rule(priority, eg_rule_action1_adaptive, eg_rule_condition, action_args, condition_args)
            rules.append(rule)
            priority += 1

        if index < len(path) - 1:
            if index == 0:
                condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:]}

            action_args = {"mid": self.owner.map_to_middle_node[path[index + 1]],
                           "path": path, "index": index, "name": self.owner.name, "reservation": reservation, "from_app_request": False,
                           "encoding_type": "single_heralded", "raw_epr_errors": [1/3, 1/3, 1/3]}
            rule = Rule(10, eg_rule_action2_adaptive, eg_rule_condition, action_args, condition_args)
            rules.append(rule)
            priority += 1

        for rule in rules:
            rule.set_reservation(reservation)
        
        for rule in rules:
            process = Process(self.owner.resource_manager, "load", [rule])
            event = Event(reservation.start_time, process, self.owner.timeline.schedule_counter)
            self.owner.timeline.schedule(event)

            process = Process(self.owner.resource_manager, "expire", [rule])
            event = Event(reservation.end_time, process, self.owner.timeline.schedule_counter)
            self.owner.timeline.schedule(event)

        for card in timecards:
            if reservation in card.reservations:
                process = Process(self.owner.resource_manager, "update", [None, self.memo_arr[card.memory_index], "RAW"]) # update memory to RAW
                event = Event(reservation.end_time, process, self.owner.timeline.schedule_counter)
                self.owner.timeline.schedule(event)

                process = Process(self.owner.adaptive_continuous, "adaptive_memory_used_minus_one", [self.memo_arr[card.memory_index]])
                event = Event(reservation.end_time, process, self.owner.timeline.schedule_counter)
                self.owner.timeline.schedule(event)


    def create_rules_request(self, path: list, reservation: ReservationAdaptive, timecards: list[MemoryTimeCard]) -> List["Rule"]:
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
        for card in timecards:
            if reservation in card.reservations:
                memory_indices.append(card.memory_index)

        index = path.index(self.owner.name)  # the location of this node along the path from initiator to responder

        priority = 10
        # 1. create rules for entanglement generation
        if index > 0:                  # non initiator
            condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            action_args = {"mid": self.owner.map_to_middle_node[path[index - 1]],
                           "path": path, "index": index, "from_app_request": True,
                           "encoding_type": "single_heralded", "raw_epr_errors": [1/3, 1/3, 1/3]}  # TODO: make 1/3 an input
            rule = Rule(priority, eg_rule_action1_adaptive, eg_rule_condition, action_args, condition_args)
            rules.append(rule)
            priority += 1

        if index < len(path) - 1:      # non responder
            if index == 0:
                condition_args = {"memory_indices": memory_indices[:reservation.memory_size]}
            else:
                condition_args = {"memory_indices": memory_indices[reservation.memory_size:]}  # the second half

            action_args = {"mid": self.owner.map_to_middle_node[path[index + 1]],
                           "path": path, "index": index, "name": self.owner.name, "reservation": reservation, "from_app_request": True,
                           "encoding_type": "single_heralded", "raw_epr_errors": [1/3, 1/3, 1/3]}
            rule = Rule(priority, eg_rule_action2_adaptive, eg_rule_condition, action_args, condition_args)
            rules.append(rule)
            priority += 1

        # # 2. create rules for entanglement purification
        # if index > 0:                  # non initiator
        #     condition_args = {"memory_indices": memory_indices[:reservation.memory_size], "reservation": reservation}
        #     action_args = {"encoding_type": "single_heralded"}
        #     rule = Rule(priority, ep_rule_action1_adaptive, ep_rule_condition1, action_args, condition_args)
        #     rules.append(rule)
        #     priority += 1

        # if index < len(path) - 1:      # non responder
        #     if index == 0:
        #         condition_args = {"memory_indices": memory_indices, "fidelity": reservation.fidelity}
        #     else:
        #         condition_args = {"memory_indices": memory_indices[reservation.memory_size:], "fidelity": reservation.fidelity}

        #     action_args = {"encoding_type": "single_heralded"}
        #     rule = Rule(priority, ep_rule_action2_adaptive, ep_rule_condition2, action_args, condition_args)
        #     rules.append(rule)
        #     priority += 1

        # 3. create rules for entanglement swapping
        if index == 0:                 # initiator
            condition_args = {"memory_indices": memory_indices, "target_remote": path[-1], "fidelity": reservation.fidelity}
            action_args = {"encoding_type": "single_heralded"}
            rule = Rule(priority, es_rule_actionB_adaptive, es_rule_conditionB1, action_args, condition_args)
            rules.append(rule)
            priority += 1

        elif index == len(path) - 1:   # responder
            action_args = {"encoding_type": "single_heralded"}
            condition_args = {"memory_indices": memory_indices, "target_remote": path[0], "fidelity": reservation.fidelity}
            rule = Rule(priority, es_rule_actionB_adaptive, es_rule_conditionB1, action_args, condition_args)
            rules.append(rule)
            priority += 1

        else:                          # middle nodes
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
            action_args = {"es_succ_prob": self.es_succ_prob, "es_degradation": self.es_degradation, "encoding_type": "single_heralded", "is_twirled": True}
            rule = Rule(priority, es_rule_actionA_adaptive, es_rule_conditionA, action_args, condition_args)
            rules.append(rule)
            priority += 1

            action_args = {"encoding_type": "single_heralded"}
            rule = Rule(priority, es_rule_actionB_adaptive, es_rule_conditionB2, action_args, condition_args)
            rules.append(rule)
            priority += 1

        for rule in rules:
            rule.set_reservation(reservation)

        return rules