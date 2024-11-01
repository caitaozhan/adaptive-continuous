'''modified version for entanglement generation
'''

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from enum import Enum, auto
from math import sqrt

from sequence.topology.node import Node
from sequence.components.memory import Memory
from sequence.topology.node import BSMNode, SingleAtomBSM, SingleHeraldedBSM
from sequence.utils import log
from sequence.utils.encoding import single_atom, single_heralded
from sequence.entanglement_management.entanglement_protocol import EntanglementProtocol
from sequence.message import Message
from sequence.components.circuit import Circuit
from sequence.kernel.event import Event
from sequence.kernel.process import Process
from sequence.resource_management.memory_manager import MemoryInfo, MemoryManager
from sequence.kernel.quantum_manager import BELL_DIAGONAL_STATE_FORMALISM

if TYPE_CHECKING:
    from adaptive_continuous import AdaptiveContinuousProtocol


def valid_trigger_time(trigger_time: int, target_time: int, resolution: int) -> bool:
    """return True if the trigger time is valid, else return False."""
    lower = target_time - (resolution // 2)
    upper = target_time + (resolution // 2)
    return lower <= trigger_time <= upper


class GenerationMsgType(Enum):
    """Defines possible message types for entanglement generation."""

    NEGOTIATE = auto()
    NEGOTIATE_ACK = auto()
    MEAS_RES = auto()
    INFORM_EP = auto()


class EntanglementGenerationMessage(Message):
    """Message used by entanglement generation protocols.

    This message contains all information passed between generation protocol instances.
    Messages of different types contain different information.

    Attributes:
        msg_type (GenerationMsgType): defines the message type.
        receiver (str): name of destination protocol instance.
        qc_delay (int): quantum channel delay to BSM node (if `msg_type == NEGOTIATE`).
        frequency (float): frequency with which local memory can be excited (if `msg_type == NEGOTIATE`).
        emit_time (int): time to emit photon for measurement (if `msg_type == NEGOTIATE_ACK`).
        res (int): detector number at BSM node (if `msg_type == MEAS_RES`).
        time (int): detection time at BSM node (if `msg_type == MEAS_RES`).
        resolution (int): time resolution of BSM detectors (if `msg_type == MEAS_RES`).
    """

    def __init__(self, msg_type: GenerationMsgType, receiver: str, **kwargs):
        super().__init__(msg_type, receiver)
        encoding_type = kwargs.get('encoding_type', single_atom)
        if encoding_type == 'single_atom':
            self.protocol_type = EntanglementGenerationAadaptive
        elif encoding_type == 'single_heralded':
            self.protocol_type = ShEntanglementGenerationAadaptive
        else:
            raise ValueError(f'encoding type {encoding_type} not supported')

        if msg_type is GenerationMsgType.NEGOTIATE:
            self.qc_delay = kwargs.get("qc_delay")
            self.frequency = kwargs.get("frequency")

        elif msg_type is GenerationMsgType.NEGOTIATE_ACK:
            self.emit_time = kwargs.get("emit_time")

        elif msg_type is GenerationMsgType.MEAS_RES:
            self.detector = kwargs.get("detector")
            self.time = kwargs.get("time")
            self.resolution = kwargs.get("resolution")
        
        elif msg_type is GenerationMsgType.INFORM_EP:
            self.entanglement_pair = kwargs.get("entanglement_pair")

        else:
            raise Exception("EntanglementGeneration generated invalid message type {}".format(msg_type))

    def __str__(self):
        if self.msg_type is GenerationMsgType.NEGOTIATE:
            return "type:{}, qc_delay:{}, frequency:{}".format(self.msg_type, self.qc_delay, self.frequency)
        elif self.msg_type is GenerationMsgType.NEGOTIATE_ACK:
            return "type:{}, emit_time:{}".format(self.msg_type, self.emit_time)
        elif self.msg_type is GenerationMsgType.MEAS_RES:
            return "type:{}, detector:{}, time:{}, resolution={}".format(self.msg_type, self.detector, self.time, self.resolution)
        elif self.msg_type is GenerationMsgType.INFORM_EP:
            return "type:{}, entanglement_pair:{}".format(self.msg_type, self.entanglement_pair)
        else:
            raise Exception("EntanglementGeneration generated invalid message type {}".format(self.msg_type))


class EntanglementGenerationAadaptive(EntanglementProtocol):
    """Entanglement generation protocol for quantum router.

    Customized for the Adaptive Continuous Protocol

    The EntanglementGenerationA protocol should be instantiated on a quantum router node.
    Instances will communicate with each other (and with the B instance on a BSM node) to generate entanglement.

    Attributes:
        own (QuantumRouter): node that protocol instance is attached to.
        name (str): label for protocol instance.
        middle (str): name of BSM measurement node where emitted photons should be directed.
        remote_node_name (str): name of distant QuantumRouter node, containing a memory to be entangled with local memory.
        memory (Memory): quantum memory object to attempt entanglement for.
        from_app_request (bool): if true, then the EG protocol is generated by a request from an app
                                 if False, then the EG protocol is generated by a AC protocol
    """

    _plus_state = [sqrt(1/2), sqrt(1/2)]
    _flip_circuit = Circuit(1)
    _flip_circuit.x(0)
    _z_circuit = Circuit(1)
    _z_circuit.z(0)

    def __init__(self, owner: "Node", name: str, middle: str, other: str, memory: "Memory", from_app_request: bool):
        """Constructor for entanglement generation A class.

        Args:
            owner (Node): node to attach protocol to.
            name (str): name of protocol instance.
            middle (str): name of middle measurement node.
            other (str): name of other node.
            memory (Memory): memory to entangle.
        """

        super().__init__(owner, name)
        self.middle: str = middle
        self.remote_node_name: str = other
        self.remote_protocol_name: str = None

        # memory info
        self.memory: Memory = memory
        self.memories: List[Memory] = [memory]
        self.remote_memory_name: str = ""  # memory index used by corresponding protocol on other node

        # network and hardware info
        self.fidelity: float = memory.raw_fidelity
        self.qc_delay: int = 0
        self.expected_time: int = -1   # expected time for middle BSM node to receive the photon

        # memory internal info
        self.ent_round = 0  # keep track of current stage of protocol
        self.bsm_res = [-1, -1]  # keep track of bsm measurements to distinguish Psi+ and Psi-

        self.scheduled_events = []

        # misc
        self.primary: bool = False  # one end node is the "primary" that initiates negotiation

        self._qstate_key: int = self.memory.qstate_key

        self.from_app_request: bool = from_app_request

        self.node_send_resource_management_request: bool = False
        self.matched_entanglement_pair = None


    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        """Method to set other entanglement protocol instance.

        Args:
            protocol (str): other protocol name.
            node (str): other node name.
            memories (List[str]): the list of memory names used on other node.
        """
        assert self.remote_protocol_name is None
        self.remote_protocol_name = protocol
        self.remote_memory_name = memories[0]
        self.primary = self.owner.name > self.remote_node_name

    
    def start(self) -> None:
        """Method to start "one round" in the entanglement generation protocol (there are two rounds in Barrett-Kok).

        Will start negotiations with other protocol (if primary).

        Side Effects:
            Will send message through attached node.
        """

        log.logger.info(f"{self.name} protocol start with partner {self.remote_protocol_name}")

        # to avoid start after remove protocol
        if self not in self.owner.protocols:
            return

        # update memory, and if necessary start negotiations for round
        if self.update_memory():
            if self.primary:

                if self.from_app_request is False:   # EGA protocol is generated from the adaptive continuous protocol
                    self.qc_delay = self.owner.qchannels[self.middle].delay          # send NEGOTIATE message as normal
                    frequency = self.memory.frequency
                    message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE, self.remote_protocol_name, qc_delay=self.qc_delay, frequency=frequency)
                    self.owner.send_message(self.remote_node_name, message)

                else:                            # EGA protocol is generated from the request
                    if self.ent_round == 1:
                        
                        if self.matched_entanglement_pair is None:                       # if not informed EP
                            adaptive_continuous: AdaptiveContinuousProtocol = self.owner.adaptive_continuous         # first check if there is pre-generated entanglement pair
                            this_node_name = self.owner.name
                            remote_node_name = self.remote_node_name
                            matched_entanglement_pair = adaptive_continuous.match_generated_entanglement_pair(this_node_name, remote_node_name)
                            if matched_entanglement_pair is None:                        # no pre-generated entanglement pair
                                self.qc_delay = self.owner.qchannels[self.middle].delay  # send NEGOTIATE message as normal
                                frequency = self.memory.frequency
                                message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE, self.remote_protocol_name, qc_delay=self.qc_delay, frequency=frequency)
                                self.owner.send_message(self.remote_node_name, message)
                            else:                                                        # has pre-generated entanglement pair
                                log.logger.info(f'{this_node_name} match pre-generated entanglement pair {matched_entanglement_pair}')
                                adaptive_continuous.remove_entanglement_pair(matched_entanglement_pair)
                                msg = EntanglementGenerationMessage(GenerationMsgType.INFORM_EP, self.remote_protocol_name, entanglement_pair=matched_entanglement_pair)
                                self.owner.send_message(self.remote_node_name, msg)
                                # swap the memory at a future time
                                entangled_memory_name = self.get_entanglement_memory_name(matched_entanglement_pair)
                                classical_delay = self.owner.cchannels[self.remote_node_name].delay
                                future_swap_time = self.owner.timeline.now() + classical_delay
                                occupied_memory_name = self.memory.name
                                process = Process(self, 'swap_two_memory', [occupied_memory_name, entangled_memory_name])
                                event = Event(future_swap_time, process)
                                self.owner.timeline.schedule(event)
                                self.scheduled_events.append(event)
                        
                        else:                                                            # if informed EP

                            adaptive_continuous = self.owner.adaptive_continuous
                            try:
                                entangled_memory_name = self.get_entanglement_memory_name(self.matched_entanglement_pair)
                                adaptive_continuous.remove_entanglement_pair(self.matched_entanglement_pair)
                                self.swap_two_memory(self.memory.name, entangled_memory_name)
                            except Exception as e:
                                log.logger.warning(f'{self.owner.name} Swap memory failed between {self.memory.name} and {entangled_memory_name}! Error message: {e}. ')
                                self.update_resource_manager(self.memory, MemoryInfo.RAW)
                                    

                    elif self.ent_round == 2:
                        self.qc_delay = self.owner.qchannels[self.middle].delay   # send NEGOTIATE message as normal
                        frequency = self.memory.frequency
                        message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE, self.remote_protocol_name, qc_delay=self.qc_delay, frequency=frequency)
                        self.owner.send_message(self.remote_node_name, message)
                    
                    else:
                        pass
            
            else:  # not primary
                
                if self.from_app_request is True and self.node_send_resource_management_request is False:  # is from app request and not sent resource_management REQUEST
                    # select EP and inform to other node
                    adaptive_continuous = self.owner.adaptive_continuous         # first check if there is pre-generated entanglement pair
                    this_node_name = self.owner.name
                    remote_node_name = self.remote_node_name
                    self.matched_entanglement_pair = adaptive_continuous.match_generated_entanglement_pair(this_node_name, remote_node_name)
                    if self.matched_entanglement_pair is not None:               # has pre-generated entanglement pair
                        log.logger.info(f'{this_node_name} match pre-generated entanglement pair {self.matched_entanglement_pair}')
                        adaptive_continuous.remove_entanglement_pair(self.matched_entanglement_pair)
                        msg = EntanglementGenerationMessage(GenerationMsgType.INFORM_EP, self.remote_protocol_name, entanglement_pair=self.matched_entanglement_pair)
                        self.owner.send_message(self.remote_node_name, msg, priority=0)
                        # swap the memory at a future time
                        entangled_memory_name = self.get_entanglement_memory_name(self.matched_entanglement_pair)
                        classical_delay = self.owner.cchannels[self.remote_node_name].delay
                        future_swap_time = self.owner.timeline.now() + classical_delay
                        occupied_memory_name = self.memory.name
                        process = Process(self, 'swap_two_memory', [occupied_memory_name, entangled_memory_name])
                        event = Event(future_swap_time, process)
                        self.owner.timeline.schedule(event)
                        self.scheduled_events.append(event)
                    else:                                                         # no pre-generated entanglement pair
                        pass
                else:
                    pass


    def get_entanglement_memory_name(self, entanglement_pair: tuple) -> str:
        '''Given the entanglement_pair, return the entangled_memory to swap with self.memory
        Args:
            entantlement_pair: ((node_name, entangled_memory_name), (node_name, entangled_memory_name)), all names are str
        '''
        for node_name, memory_name in entanglement_pair:
            if node_name == self.owner.name:
                entangled_memory_name = memory_name
                return entangled_memory_name
        else:
            raise Exception(f'{self.owner.name} not in {entanglement_pair}')


    def swap_two_memory(self, occupied_memory_name: str, entangled_memory_name: str):
        '''swap memory between self.memory and the memory that entangled_memory_name is referring to
        Args:
            occupied_memory_name:  the name of the occupied memory (i.e., self.memory of the entanglement generation protocol)
            entangled_memory_name: the name of the entangled memory (generated by the adaptive continuous protocol) on this node
        '''
        if self.check_entangled_memory(entangled_memory_name) is False:
            # Adaptive continuous protocol's reservation expire in the middle of swap_memory protocol
            log.logger.info(f'{self.owner.name} Swap memory failed between {occupied_memory_name} and {entangled_memory_name}!')
            self.update_resource_manager(self.memory, MemoryInfo.RAW)
            return

        if self not in self.owner.protocols:
            # Request's reservation expire in the middle of swap_memory protocol
            log.logger.info(f'{self.owner.name} Swap memory failed between {occupied_memory_name} and {entangled_memory_name}!')
            self.update_resource_manager(self.memory, MemoryInfo.RAW)
            return

        log.logger.info(f'{self.owner.name} Swap memory between {occupied_memory_name} and {entangled_memory_name}')
        self.owner.resource_manager.swap_two_memory(occupied_memory_name, entangled_memory_name) # the memory_array is updated, but more needs to update

        memory_manager = self.get_memory_manager()
        memory_array = memory_manager.get_memory_array()
        # after swapping, the entanged memory turns into occupied memory, while the occupied memory turns into entangled memory
        entangled_memory = memory_array.get_memory_by_name(occupied_memory_name)
        occupied_memory  = memory_array.get_memory_by_name(entangled_memory_name)

        # update self.memory (the current entangled memory)
        self.memory = entangled_memory
        self.memories = [self.memory]
        self.memory.entangled_memory['memo_id'] = self.remote_memory_name
        mem_info = memory_manager.get_info_by_memory(entangled_memory)
        mem_info.remote_memo = self.remote_memory_name
        self.update_resource_manager_swap_memory(self, self.memory)

        # update the current occupied memory to RAW
        mem_info = memory_manager.get_info_by_memory(occupied_memory)
        mem_info.to_raw()
        self.update_resource_manager_swap_memory(None, occupied_memory)


    def check_entangled_memory(self, entangled_memory_name: str) -> bool:
        '''check if the parameter entangled_memory_name is indeed in an entangled state
           useful when the AC protocol's expire event interrupted the swapping protocol process
        
        Args:
            entanlged_memory_name: name of the memory that is in entangled state
        Return:
            True if the memory is indeed entangled, otherwise False
        '''
        return self.owner.resource_manager.check_entangled_memory(entangled_memory_name)


    def update_resource_manager_swap_memory(self, protocol: Optional[EntanglementProtocol], memory: Memory):
        '''update the resource manager when using the swap memory, use resource_manager.update_swap_memory()
        '''
        self.owner.resource_manager.update_swap_memory(protocol, memory)


    def get_memory_manager(self) -> MemoryManager:
        '''get the memory manager that is associated to self.owner
        '''
        return self.owner.resource_manager.memory_manager


    def update_memory(self) -> bool:
        """Method to handle necessary memory operations.

        Called on both nodes.
        Will check the state of the memory and protocol.

        Returns:
            bool: if current round was successfull.

        Side Effects:
            May change state of attached memory.
            May update memory state in the attached node's resource manager.
        """

        # to avoid start after protocol removed
        if self not in self.owner.protocols:
            return

        self.ent_round += 1

        if self.ent_round == 1:
            return True

        elif self.ent_round == 2 and self.bsm_res[0] != -1:
            self.owner.timeline.quantum_manager.run_circuit(EntanglementGenerationAadaptive._flip_circuit, [self._qstate_key])
            return True
        
        elif self.ent_round == 3 and self.bsm_res[1] != -1:
            # entanglement succeeded, correction
            if self.primary:
                self.owner.timeline.quantum_manager.run_circuit(EntanglementGenerationAadaptive._flip_circuit, [self._qstate_key])
            elif self.bsm_res[0] != self.bsm_res[1]:
                self.owner.timeline.quantum_manager.run_circuit(EntanglementGenerationAadaptive._z_circuit, [self._qstate_key])
            self._entanglement_succeed()
            return True

        else:
            # entanglement failed
            self._entanglement_fail()
            return False


    def emit_event(self) -> None:
        """Method to set up memory and emit photons.

        If the protocol is in round 1, the memory will be first set to the |+> state.
        Otherwise, it will apply an x_gate to the memory.
        Regardless of the round, the memory `excite` method will be invoked.

        Side Effects:
            May change state of attached memory.
            May cause attached memory to emit photon.
        """

        if self.ent_round == 1:
            self.memory.update_state(EntanglementGenerationAadaptive._plus_state)
        self.memory.excite(self.middle)

    def received_message(self, src: str, msg: EntanglementGenerationMessage) -> None:
        """Method to receive messages.

        This method receives messages from other entanglement generation protocols.
        Depending on the message, different actions may be taken by the protocol.

        Args:
            src (str): name of the source node sending the message.
            msg (EntanglementGenerationMessage): message received.

        Side Effects:
            May schedule various internal and hardware events.
        """

        if src not in [self.middle, self.remote_node_name]:
            return

        msg_type = msg.msg_type

        log.logger.debug("{} {} received message from node {} of type {}, round={}".format(
                         self.owner.name, self.name, src, msg.msg_type, self.ent_round))

        if msg_type is GenerationMsgType.NEGOTIATE:  # primary -> non-primary
            # configure params
            other_qc_delay = msg.qc_delay
            self.qc_delay = self.owner.qchannels[self.middle].delay
            cc_delay = int(self.owner.cchannels[src].delay)
            total_quantum_delay = max(self.qc_delay, other_qc_delay)  # two qc_delays are the same for "meet_in_the_middle"

            # get time for first excite event
            memory_excite_time = self.memory.next_excite_time
            min_time = max(self.owner.timeline.now(), memory_excite_time) + total_quantum_delay - self.qc_delay + cc_delay  # cc_delay time for NEGOTIATE_ACK
            emit_time = self.owner.schedule_qubit(self.middle, min_time)  # used to send memory
            self.expected_time = emit_time + self.qc_delay  # expected time for middle BSM node to receive the photon

            # schedule emit
            process = Process(self, "emit_event", [])
            event = Event(emit_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

            # send negotiate_ack
            other_emit_time = emit_time + self.qc_delay - other_qc_delay
            message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE_ACK, self.remote_protocol_name, emit_time=other_emit_time)
            self.owner.send_message(src, message)

            # schedule start if necessary (current is first round, need second round), else schedule update_memory (currently second round)
            # TODO: base future start time on resolution
            future_start_time = self.expected_time + self.owner.cchannels[self.middle].delay + 10  # delay is for sending the BSM_RES to end nodes, 10 is a small gap
            if self.ent_round == 1:
                process = Process(self, "start", [])  # for the second round
            else:
                process = Process(self, "update_memory", [])
            event = Event(future_start_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

        elif msg_type is GenerationMsgType.NEGOTIATE_ACK:  # non-primary --> primary
            # configure params
            self.expected_time = msg.emit_time + self.qc_delay  # expected time for middle BSM node to receive the photon

            if msg.emit_time < self.owner.timeline.now():  # emit time calculated by the non-primary node
                msg.emit_time = self.owner.timeline.now()

            # schedule emit
            emit_time = self.owner.schedule_qubit(self.middle, msg.emit_time)
            assert emit_time == msg.emit_time, \
                "Invalid eg emit times {} {} {}".format(emit_time, msg.emit_time, self.owner.timeline.now())

            process = Process(self, "emit_event", [])
            event = Event(msg.emit_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

            # schedule start if necessary (current is first round, need second round), else schedule update_memory (currently second round)
            # TODO: base future start time on resolution
            future_start_time = self.expected_time + self.owner.cchannels[self.middle].delay + 10
            if self.ent_round == 1:
                process = Process(self, "start", [])  # for the second round
            else:
                process = Process(self, "update_memory", [])
            event = Event(future_start_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

        elif msg_type is GenerationMsgType.MEAS_RES:  # from middle BSM to both non-primary and primary
            detector = msg.detector
            time = msg.time
            resolution = msg.resolution

            log.logger.debug("{} received MEAS_RES={} at time={:,}, expected={:,}, resolution={}, round={}".format(
                             self.owner.name, detector, time, self.expected_time, resolution, self.ent_round))

            if valid_trigger_time(time, self.expected_time, resolution):
                # record result if we don't already have one
                i = self.ent_round - 1
                if self.bsm_res[i] == -1:
                    self.bsm_res[i] = detector  # save the measurement results (detector number)
                else:
                    self.bsm_res[i] = -1  # BSM measured 1, 1 and both didn't lost
            else:
                log.logger.debug('{} BSM trigger time not valid'.format(self.owner.name))


        elif msg_type is GenerationMsgType.INFORM_EP:

            if self.remote_protocol_name is None:                       # protocol not paired with remote
                self.matched_entanglement_pair = msg.entanglement_pair  # save msg.entanglement_pair
            else:                                                       # already paired with remote
                adaptive_continuous = self.owner.adaptive_continuous
                try:
                    entangled_memory_name = self.get_entanglement_memory_name(msg.entanglement_pair)
                    adaptive_continuous.remove_entanglement_pair(msg.entanglement_pair)
                    self.swap_two_memory(self.memory.name, entangled_memory_name)
                except Exception as e:
                    log.logger.warning(f'{self.owner.name} Swap memory failed between {self.memory.name} and {entangled_memory_name}! Error message: {e}. ')
                    self.update_resource_manager(self.memory, MemoryInfo.RAW)

        else:
            raise Exception("Invalid message {} received by EG on node {}".format(msg_type, self.owner.name))

    def is_ready(self) -> bool:
        return self.remote_protocol_name is not None

    def memory_expire(self, memory: "Memory") -> None:
        """Method to receive expired memories."""

        assert memory == self.memory

        self.update_resource_manager(memory, MemoryInfo.RAW)
        for event in self.scheduled_events:
            if event.time >= self.owner.timeline.now():
                self.owner.timeline.remove_event(event)

    def _entanglement_succeed(self):
        log.logger.info(self.owner.name + " successful entanglement of memory {}".format(self.memory))
        self.memory.entangled_memory["node_id"] = self.remote_node_name
        self.memory.entangled_memory["memo_id"] = self.remote_memory_name
        self.memory.fidelity = self.memory.raw_fidelity

        self.update_resource_manager(self.memory, MemoryInfo.ENTANGLED)

    def _entanglement_fail(self):
        for event in self.scheduled_events:
            self.owner.timeline.remove_event(event)
        log.logger.info(self.owner.name + " failed entanglement of memory {}".format(self.memory))
        
        self.update_resource_manager(self.memory, MemoryInfo.RAW)



class EntanglementGenerationBadaptive(EntanglementProtocol):
    """Entanglement generation protocol for BSM node.

    The EntanglementGenerationB protocol should be instantiated on a BSM node.
    Instances will communicate with the A instance on neighboring quantum router nodes to generate entanglement.

    Attributes:
        own (BSMNode): node that protocol instance is attached to.
        name (str): label for protocol instance.
        others (List[str]): list of neighboring quantum router nodes
    """

    def __init__(self, owner: "BSMNode", name: str, others: List[str]):
        """Constructor for entanglement generation B protocol.

        Args:
            own (Node): attached node.
            name (str): name of protocol instance.
            others (List[str]): name of protocol instance on end nodes.
        """

        super().__init__(owner, name)
        assert len(others) == 2
        self.others = others  # end nodes

    def bsm_update(self, bsm: "SingleAtomBSM", info: Dict[str, Any]):
        """Method to receive detection events from BSM on node.

        Args:
            bsm (SingleAtomBSM): bsm object calling method.
            info (Dict[str, any]): information passed from bsm.
        """

        assert info['info_type'] == "BSM_res"

        res = info["res"]
        time = info["time"]
        resolution = bsm.resolution

        for node in self.others:
            message = EntanglementGenerationMessage(GenerationMsgType.MEAS_RES, None, detector=res, time=time, resolution=resolution) # receiver is None (not paired)
            self.owner.send_message(node, message)


    def received_message(self, src: str, msg: EntanglementGenerationMessage):
        raise Exception("EntanglementGenerationB protocol '{}' should not "
                        "receive message".format(self.name))

    def start(self) -> None:
        pass

    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        pass

    def is_ready(self) -> bool:
        return True

    def memory_expire(self, memory: "Memory") -> None:
        raise Exception("Memory expire called for EntanglementGenerationB protocol '{}'".format(self.name))



###### Single Heralded Entanglement Generation Protocol ########

class ShEntanglementGenerationAadaptive(EntanglementProtocol):
    """Single heralded entanglement generation protocol for quantum router.

    Uses Bell diagonal state and compute fidelity analytically

    Customized for the Adaptive Continuous Protocol
    
    The EntanglementGenerationA protocol should be instantiated on a quantum router node.
    Instances will communicate with each other (and with the B instance on a BSM node) to generate entanglement.

    Attributes:
        own (QuantumRouter): node that protocol instance is attached to.
        name (str): label for protocol instance.
        middle (str): name of BSM measurement node where emitted photons should be directed.
        remote_node_name (str): name of distant QuantumRouter node, containing a memory to be entangled with local memory.
        memory (Memory): quantum memory object to attempt entanglement for.
        from_app_request (bool): if true, then the EG protocol is generated by a request from an app
                                 if False, then the EG protocol is generated by a AC protocol
        raw_epr_errors (list): assuming BDS form of raw EPR pair, probability distribution of X, Y, Z Pauli errors
    """

    # No circuit
    ENCODING_TYPE = 'single_heralded'

    def __init__(self, owner: "Node", name: str, middle: str, other: str, memory: "Memory", from_app_request: bool, raw_epr_errors: List[float]):
        """Constructor for entanglement generation A class.

        Args:
            owner (Node): node to attach protocol to.
            name (str): name of protocol instance.
            middle (str): name of middle measurement node.
            other (str): name of other node.
            memory (Memory): memory to entangle.
            from_app_request (bool): if true, then the EG protocol is generated by a request from an app
                                     if False, then the EG protocol is generated by a AC protocol
            raw_epr_errors (list): assuming BDS form of raw EPR pair, probability distribution of X, Y, Z Pauli errors
        """

        super().__init__(owner, name)
        self.middle: str = middle
        self.remote_node_name: str = other
        self.remote_protocol_name: str = None

        if self.owner:
            assert self.owner.timeline.quantum_manager.formalism == BELL_DIAGONAL_STATE_FORMALISM, \
                    "Currently single heralded protocol requires Bell diagonal state formalism."
        
        # memory info
        self.memory: Memory = memory
        self.memories: List[Memory] = [memory]
        self.remote_memory_name: str = ""  # memory index used by corresponding protocol on other node

        # network and hardware info
        self.raw_fidelity = memory.raw_fidelity
        assert 0.5 <= self.raw_fidelity <= 1, "Raw fidelity of EPR pair must be above 1/2."

        self.raw_epr_errors = raw_epr_errors

        self.qc_delay: int = 0
        self.expected_time: int = -1   # expected time for middle BSM node to receive the photon

        # memory internal info
        self.ent_round = 0     # keep track of current stage of protocol
        self.bsm_res = [0, 0]  # keep track of how many times each detector are triggered, can potentially see number of dark counts if greater than 1

        self.scheduled_events = []

        # misc
        self.primary: bool = False  # one end node is the "primary" that initiates negotiation

        self._qstate_key: int = self.memory.qstate_key

        self.from_app_request: bool = from_app_request

        self.node_send_resource_management_request: bool = False
        self.select_ep = False    # this node select the EP for memory assignment
        self.matched_entanglement_pair = None


    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        """Method to set other entanglement protocol instance.

        Args:
            protocol (str): other protocol name.
            node (str): other node name.
            memories (List[str]): the list of memory names used on other node.
        """
        assert self.remote_protocol_name is None
        self.remote_protocol_name = protocol
        self.remote_memory_name = memories[0]
        self.primary = self.owner.name > self.remote_node_name

    
    def start(self) -> None:
        """Method to start "one round" in the entanglement generation protocol (there are two rounds in Barrett-Kok).

        Will start negotiations with other protocol (if primary).

        Side Effects:
            Will send message through attached node.
        """

        log.logger.info(f"{self.name} protocol start with partner {self.remote_protocol_name}")

        # to avoid start after remove protocol
        if self not in self.owner.protocols:
            return

        # update memory, and if necessary start negotiations for round
        if self.update_memory():
            if self.primary:

                if self.from_app_request is False:   # EGA protocol is generated from the adaptive continuous protocol
                    self.qc_delay = self.owner.qchannels[self.middle].delay          # send NEGOTIATE message as normal
                    frequency = self.memory.frequency
                    message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE, self.remote_protocol_name, qc_delay=self.qc_delay, frequency=frequency, encoding_type=self.ENCODING_TYPE)
                    self.owner.send_message(self.remote_node_name, message)

                else:                                # EGA protocol is generated from the request
                    if self.matched_entanglement_pair is None:                       # if not informed EP
                        adaptive_continuous: AdaptiveContinuousProtocol = self.owner.adaptive_continuous         # first check if there is pre-generated entanglement pair
                        this_node_name = self.owner.name
                        remote_node_name = self.remote_node_name
                        matched_entanglement_pair = adaptive_continuous.match_generated_entanglement_pair(this_node_name, remote_node_name)
                        if matched_entanglement_pair is None:                        # no pre-generated entanglement pair
                            self.qc_delay = self.owner.qchannels[self.middle].delay  # send NEGOTIATE message as normal
                            frequency = self.memory.frequency
                            message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE, self.remote_protocol_name, qc_delay=self.qc_delay, frequency=frequency, encoding_type=self.ENCODING_TYPE)
                            self.owner.send_message(self.remote_node_name, message)
                        else:                                                        # has pre-generated entanglement pair
                            log.logger.info(f'{this_node_name} match pre-generated entanglement pair {matched_entanglement_pair}')
                            adaptive_continuous.remove_entanglement_pair(matched_entanglement_pair)
                            msg = EntanglementGenerationMessage(GenerationMsgType.INFORM_EP, self.remote_protocol_name, entanglement_pair=matched_entanglement_pair, encoding_type=self.ENCODING_TYPE)
                            self.owner.send_message(self.remote_node_name, msg)
                            # swap the memory at a future time
                            entangled_memory_name = self.get_entanglement_memory_name(matched_entanglement_pair)
                            classical_delay = self.owner.cchannels[self.remote_node_name].delay
                            future_swap_time = self.owner.timeline.now() + classical_delay
                            occupied_memory_name = self.memory.name
                            process = Process(self, 'swap_two_memory', [occupied_memory_name, entangled_memory_name])
                            event = Event(future_swap_time, process)
                            self.owner.timeline.schedule(event)
                            self.scheduled_events.append(event)
                    
                    else:                                                            # if informed EP
                        adaptive_continuous = self.owner.adaptive_continuous
                        try:
                            entangled_memory_name = self.get_entanglement_memory_name(self.matched_entanglement_pair)
                            adaptive_continuous.remove_entanglement_pair(self.matched_entanglement_pair)
                            self.swap_two_memory(self.memory.name, entangled_memory_name)
                        except Exception as e:
                            log.logger.warning(f'{self.owner.name} Swap memory failed between {self.memory.name} and {entangled_memory_name}! Error message: {e}. ')
                            self.update_resource_manager(self.memory, MemoryInfo.RAW)

            else:  # not primary
                
                if self.from_app_request is True and self.node_send_resource_management_request is False:  # is from app request and not sent resource_management REQUEST
                    # select EP and inform to other node
                    adaptive_continuous = self.owner.adaptive_continuous         # first check if there is pre-generated entanglement pair
                    this_node_name = self.owner.name
                    remote_node_name = self.remote_node_name
                    self.matched_entanglement_pair = adaptive_continuous.match_generated_entanglement_pair(this_node_name, remote_node_name)
                    if self.matched_entanglement_pair is not None:               # has pre-generated entanglement pair
                        log.logger.info(f'{this_node_name} match pre-generated entanglement pair {self.matched_entanglement_pair}')
                        adaptive_continuous.remove_entanglement_pair(self.matched_entanglement_pair)
                        msg = EntanglementGenerationMessage(GenerationMsgType.INFORM_EP, self.remote_protocol_name, entanglement_pair=self.matched_entanglement_pair, encoding_type=self.ENCODING_TYPE)
                        self.owner.send_message(self.remote_node_name, msg, priority=0)
                        # swap the memory at a future time
                        entangled_memory_name = self.get_entanglement_memory_name(self.matched_entanglement_pair)
                        classical_delay = self.owner.cchannels[self.remote_node_name].delay
                        future_swap_time = self.owner.timeline.now() + classical_delay
                        occupied_memory_name = self.memory.name
                        process = Process(self, 'swap_two_memory', [occupied_memory_name, entangled_memory_name])
                        event = Event(future_swap_time, process)
                        self.owner.timeline.schedule(event)
                        self.scheduled_events.append(event)
                    else:                                                         # no pre-generated entanglement pair
                        pass
                else:
                    pass


    def get_entanglement_memory_name(self, entanglement_pair: tuple) -> str:
        '''Given the entanglement_pair, return the entangled_memory to swap with self.memory
        Args:
            entantlement_pair: ((node_name, entangled_memory_name), (node_name, entangled_memory_name)), all names are str
        '''
        for node_name, memory_name in entanglement_pair:
            if node_name == self.owner.name:
                entangled_memory_name = memory_name
                return entangled_memory_name
        else:
            raise Exception(f'{self.owner.name} not in {entanglement_pair}')


    def swap_two_memory(self, occupied_memory_name: str, entangled_memory_name: str):
        '''swap memory between self.memory and the memory that entangled_memory_name is referring to
        Args:
            occupied_memory_name:  the name of the occupied memory (i.e., self.memory of the entanglement generation protocol)
            entangled_memory_name: the name of the entangled memory (generated by the adaptive continuous protocol) on this node
        '''
        if self.check_entangled_memory(entangled_memory_name) is False:
            # Adaptive continuous protocol's reservation expire in the middle of swap_memory protocol
            log.logger.warning(f'{self.owner.name} Swap memory failed between {occupied_memory_name} and {entangled_memory_name}!')
            self.update_resource_manager(self.memory, MemoryInfo.RAW)
            return

        if self not in self.owner.protocols:
            # Request's reservation expire in the middle of swap_memory protocol
            log.logger.warning(f'{self.owner.name} Swap memory failed between {occupied_memory_name} and {entangled_memory_name}!')
            self.update_resource_manager(self.memory, MemoryInfo.RAW)
            return

        log.logger.info(f'{self.owner.name} Swap memory between {occupied_memory_name} and {entangled_memory_name}')
        memory_manager = self.get_memory_manager()
        memory_array = memory_manager.get_memory_array()

        # udpate the memory fidelity here. Note: for two entangled memories at two nodes,
        # only the node that first run the code will success, the node that runs second will fail,
        # because in the second run, `other_memory` is already swapped at the remote node, but not reflected here
        try:
            entangled_memory: Memory = memory_array.get_memory_by_name(entangled_memory_name)
            mem_info: MemoryInfo = memory_manager.get_info_by_memory(entangled_memory)
            other_memory: Memory = self.owner.timeline.get_entity_by_name(mem_info.remote_memo)
            entangled_memory.bds_decohere()
            other_memory.bds_decohere()
        except Exception as e:
            log.logger.error(f'{self.name}: key error {e}')
        finally:
            mem_info.fidelity = entangled_memory.fidelity = entangled_memory.get_bds_fidelity()

        # the swapping of attributes in memory and mem_info object
        self.owner.resource_manager.swap_two_memory(occupied_memory_name, entangled_memory_name) # the memory_array is updated, but more needs to update

        # update self.memory (the current entangled memory)
        self.memory.entangled_memory['memo_id'] = self.remote_memory_name
        mem_info = memory_manager.get_info_by_memory(self.memory)
        mem_info.remote_memo = self.remote_memory_name
        self.update_resource_manager_swap_memory(self, self.memory)

        # update the current occupied memory to RAW
        # after swapping, the entanged memory turns into occupied memory, while the occupied memory turns into entangled memory
        occupied_memory  = memory_array.get_memory_by_name(entangled_memory_name)
        mem_info = memory_manager.get_info_by_memory(occupied_memory)
        mem_info.to_raw()
        self.update_resource_manager_swap_memory(None, occupied_memory)


    def check_entangled_memory(self, entangled_memory_name: str) -> bool:
        '''check if the parameter entangled_memory_name is indeed in an entangled state
           useful when the AC protocol's expire event interrupted the swapping protocol process
        
        Args:
            entanlged_memory_name: name of the memory that is in entangled state
        Return:
            True if the memory is indeed entangled, otherwise False
        '''
        return self.owner.resource_manager.check_entangled_memory(entangled_memory_name)


    def update_resource_manager_swap_memory(self, protocol: Optional[EntanglementProtocol], memory: Memory):
        '''update the resource manager when using the swap memory, use resource_manager.update_swap_memory()
        '''
        self.owner.resource_manager.update_swap_memory(protocol, memory)


    def get_memory_manager(self) -> MemoryManager:
        '''get the memory manager that is associated to self.owner
        '''
        return self.owner.resource_manager.memory_manager


    def update_memory(self) -> bool:
        """Method to handle necessary memory operations.

        Called on both nodes.
        Will check the state of the memory and protocol.

        Returns:
            bool: if current round was successfull.

        Side Effects:
            May change state of attached memory.
            May update memory state in the attached node's resource manager.
        """

        # to avoid start after protocol removed
        if self not in self.owner.protocols:
            return

        self.ent_round += 1

        if self.ent_round == 1:
            return True

        elif self.ent_round == 2:
            # success when both detectors in BSM are triggered
            if self.bsm_res[0] >= 1 and self.bsm_res[1] >= 1:
                # successful entanglement
                # Bell diagonal state assignment to both memories
                quantum_manager = self.owner.timeline.quantum_manager
                self_key = self._qstate_key
                remote_memory: Memory = self.owner.timeline.get_entity_by_name(self.remote_memory_name)

                remote_key = remote_memory.qstate_key
                keys = [self_key, remote_key]

                if self_key not in quantum_manager.states:
                    infidelity = 1 - self.raw_fidelity
                    x_elem, y_elem, z_elem = [error * infidelity for error in self.raw_epr_errors]
                    state = [self.raw_fidelity, z_elem, x_elem, y_elem]
                    quantum_manager.set(keys, state)
                    self.memory.bds_decohere()
                    remote_memory.bds_decohere()

                self._entanglement_succeed()

            else:
                # entanglement failed
                self._entanglement_fail()
                return False

        return True

    def emit_event(self) -> None:
        """Method to set up memory and emit photons.

        If the protocol is in round 1, the memory will be first set to the |+> state.
        Otherwise, it will apply an x_gate to the memory.
        Regardless of the round, the memory `excite` method will be invoked.

        Side Effects:
            May change state of attached memory.
            May cause attached memory to emit photon.
        """
        if self.is_valid() is False:
            log.logger.info(f'{self} is not valid. emit_event() failed')
            return
        
        if self.ent_round == 1:
            self.memory.update_state(EntanglementGenerationAadaptive._plus_state)
        self.memory.excite(self.middle, protocol="sh")

    def received_message(self, src: str, msg: EntanglementGenerationMessage) -> None:
        """Method to receive messages.

        This method receives messages from other entanglement generation protocols.
        Depending on the message, different actions may be taken by the protocol.

        Args:
            src (str): name of the source node sending the message.
            msg (EntanglementGenerationMessage): message received.

        Side Effects:
            May schedule various internal and hardware events.
        """

        if src not in [self.middle, self.remote_node_name]:
            return

        msg_type = msg.msg_type

        log.logger.debug("{} {} received message from node {} of type {}, round={}".format(self.owner.name, self.name, src, msg.msg_type, self.ent_round))

        if msg_type is GenerationMsgType.NEGOTIATE:  # primary -> non-primary
            # configure params
            other_qc_delay = msg.qc_delay
            self.qc_delay = self.owner.qchannels[self.middle].delay
            cc_delay = int(self.owner.cchannels[src].delay)
            total_quantum_delay = max(self.qc_delay, other_qc_delay)  # two qc_delays are the same for "meet_in_the_middle"

            # get time for first excite event
            memory_excite_time = self.memory.next_excite_time
            min_time = max(self.owner.timeline.now(), memory_excite_time) + total_quantum_delay - self.qc_delay + cc_delay  # cc_delay time for NEGOTIATE_ACK
            emit_time = self.owner.schedule_qubit(self.middle, min_time)  # used to send memory
            self.expected_time = emit_time + self.qc_delay  # expected time for middle BSM node to receive the photon

            # schedule emit
            process = Process(self, "emit_event", [])
            event = Event(emit_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

            # send negotiate_ack
            other_emit_time = emit_time + self.qc_delay - other_qc_delay
            message = EntanglementGenerationMessage(GenerationMsgType.NEGOTIATE_ACK, self.remote_protocol_name, emit_time=other_emit_time, encoding_type=self.ENCODING_TYPE)
            self.owner.send_message(src, message)

            # schedule start if necessary (current is first round, need second round), else schedule update_memory (currently second round)
            # TODO: base future start time on resolution
            future_start_time = self.expected_time + self.owner.cchannels[self.middle].delay + 10  # delay is for sending the BSM_RES to end nodes, 10 is a small gap

            process = Process(self, "update_memory", [])
            priority = self.owner.timeline.schedule_counter
            event = Event(future_start_time, process, priority)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

        elif msg_type is GenerationMsgType.NEGOTIATE_ACK:  # non-primary --> primary
            # configure params
            self.expected_time = msg.emit_time + self.qc_delay  # expected time for middle BSM node to receive the photon

            if msg.emit_time < self.owner.timeline.now():  # emit time calculated by the non-primary node
                msg.emit_time = self.owner.timeline.now()

            # schedule emit
            emit_time = self.owner.schedule_qubit(self.middle, msg.emit_time)
            assert emit_time == msg.emit_time, \
                "Invalid eg emit times {} {} {}".format(emit_time, msg.emit_time, self.owner.timeline.now())

            process = Process(self, "emit_event", [])
            event = Event(msg.emit_time, process)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

            # schedule start if necessary (current is first round, need second round), else schedule update_memory (currently second round)
            # TODO: base future start time on resolution
            future_start_time = self.expected_time + self.owner.cchannels[self.middle].delay + 10

            process = Process(self, "update_memory", [])
            priority = self.owner.timeline.schedule_counter
            event = Event(future_start_time, process, priority)
            self.owner.timeline.schedule(event)
            self.scheduled_events.append(event)

        elif msg_type is GenerationMsgType.MEAS_RES:  # from middle BSM to both non-primary and primary
            detector = msg.detector
            time = msg.time
            resolution = msg.resolution

            log.logger.debug("{} received MEAS_RES={} at time={:,}, expected={:,}, resolution={}, round={}".format(
                             self.owner.name, detector, time, self.expected_time, resolution, self.ent_round))

            if valid_trigger_time(time, self.expected_time, resolution):
                self.bsm_res[detector] += 1  # record one trigger of the detector (here `detector` is the index of detector object)
            else:
                pass
                # log.logger.debug('{} BSM trigger time not valid'.format(self.owner.name))


        elif msg_type is GenerationMsgType.INFORM_EP:

            if self.remote_protocol_name is None:                       # primary node: protocol not paired with remote
                self.matched_entanglement_pair = msg.entanglement_pair  # save msg.entanglement_pair
            else:                                                       # non-primary node: already paired with remote
                adaptive_continuous = self.owner.adaptive_continuous
                try:
                    entangled_memory_name = self.get_entanglement_memory_name(msg.entanglement_pair)
                    adaptive_continuous.remove_entanglement_pair(msg.entanglement_pair)
                    self.swap_two_memory(self.memory.name, entangled_memory_name)
                except Exception as e:
                    log.logger.warning(f'{self.owner.name} Swap memory failed between {self.memory.name} and {entangled_memory_name}! Error message: {e}. ')
                    self.update_resource_manager(self.memory, MemoryInfo.RAW)

        else:
            raise Exception("Invalid message {} received by EG on node {}".format(msg_type, self.owner.name))

    def is_ready(self) -> bool:
        return self.remote_protocol_name is not None

    def memory_expire(self, memory: "Memory") -> None:
        """Method to receive expired memories."""

        assert memory == self.memory

        self.update_resource_manager(memory, MemoryInfo.RAW)
        for event in self.scheduled_events:
            if event.time >= self.owner.timeline.now():
                self.owner.timeline.remove_event(event)

    def _entanglement_succeed(self):
        log.logger.info(self.owner.name + " successful entanglement of memory {}".format(self.memory))
        self.memory.entangled_memory["node_id"] = self.remote_node_name
        self.memory.entangled_memory["memo_id"] = self.remote_memory_name
        self.memory.fidelity = self.memory.get_bds_fidelity()

        self.update_resource_manager(self.memory, MemoryInfo.ENTANGLED)

    def _entanglement_fail(self):
        for event in self.scheduled_events:
            self.owner.timeline.remove_event(event)
        log.logger.info(self.owner.name + " failed entanglement of memory {}".format(self.memory))
        
        self.update_resource_manager(self.memory, MemoryInfo.RAW)

    def is_valid(self) -> bool:
        """Method to check if this protocol is valid or not by checking if the protocol exists in self.owners.protocols
           checking existance in self.rule.protocols should also work

           NOTE: may add to parent class
        
        Return:
            bool: if this protocol is valid
        """
        return self in self.owner.protocols



class ShEntanglementGenerationBadaptive(EntanglementProtocol):
    """Single heralded entanglement generation protocol for BSM node.

    The ShEntanglementGenerationBadaptive protocol should be instantiated on a BSM node.
    Instances will communicate with the A instance on neighboring quantum router nodes to generate entanglement.

    Attributes:
        own (BSMNode): node that protocol instance is attached to.
        name (str): label for protocol instance.
        others (List[str]): list of neighboring quantum router nodes
    """

    ENCODING_TYPE = 'single_heralded'

    def __init__(self, owner: "BSMNode", name: str, others: List[str]):
        """Constructor for entanglement generation B protocol.

        Args:
            own (Node): attached node.
            name (str): name of protocol instance.
            others (List[str]): name of protocol instance on end nodes.
        """

        super().__init__(owner, name)
        assert len(others) == 2
        self.others = others  # end nodes

    def bsm_update(self, bsm: SingleHeraldedBSM, info: Dict[str, Any]):
        """Method to receive detection events from BSM on node.

        Args:
            bsm (SingleHeraldedBSM): bsm object calling method.
            info (Dict[str, any]): information passed from bsm.
        """

        assert info['info_type'] == "BSM_res"

        res = info["res"]
        time = info["time"]
        resolution = bsm.resolution

        for node in self.others:
            message = EntanglementGenerationMessage(GenerationMsgType.MEAS_RES, None, detector=res, time=time, 
                                                    resolution=resolution, encoding_type=self.ENCODING_TYPE) # receiver is None (not paired)
            self.owner.send_message(node, message)


    def received_message(self, src: str, msg: EntanglementGenerationMessage):
        raise Exception("EntanglementGenerationB protocol '{}' should not "
                        "receive message".format(self.name))

    def start(self) -> None:
        pass

    def set_others(self, protocol: str, node: str, memories: List[str]) -> None:
        pass

    def is_ready(self) -> bool:
        return True

    def memory_expire(self, memory: "Memory") -> None:
        raise Exception("Memory expire called for EntanglementGenerationB protocol '{}'".format(self.name))
