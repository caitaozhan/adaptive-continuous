"""The Resource Manager customized for the adaptive continuous protocol
"""

from typing import TYPE_CHECKING, Optional

from sequence.resource_management.resource_manager import ResourceManager
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol
from sequence.components.memory import Memory
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.utils import log
from sequence.network_management.reservation import Reservation
from sequence.resource_management.rule_manager import Arguments
from sequence.resource_management.resource_manager import RequestConditionFunc, ResourceManagerMsgType, ResourceManagerMessage
from sequence.kernel.process import Process
from sequence.kernel.event import Event

from generation import EntanglementGenerationAadaptive, ShEntanglementGenerationAadaptive
from memory_manager import MemoryManagerAdaptive
from reservation import ReservationAdaptive
from adaptive_continuous import AdaptiveContinuousProtocol, AdaptiveContinuousMessage, ACMsgType
from purification import BBPSSW_bds, BBPSSWMessage, BBPSSWMsgType

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive


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
                    if self.purify:
                        entanglement_pair2 = adaptive_continuous.get_entanglement_pair2(entanglement_pair)
                        if entanglement_pair2:
                            adaptive_continuous.remove_entanglement_pair(entanglement_pair)
                            adaptive_continuous.remove_entanglement_pair(entanglement_pair2)  # two distant nodes creating purification protocol at the same time
                            purification_protocol = adaptive_continuous.create_purification_protocol(entanglement_pair, entanglement_pair2, protocol.rule)
                            self.owner.protocols.append(purification_protocol)
                            msg = BBPSSWMessage(BBPSSWMsgType.INFORM_EP, purification_protocol.remote_protocol_name, entanglement_pairs=(entanglement_pair, entanglement_pair2))
                            self.owner.send_message(purification_protocol.remote_node_name, msg)

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
