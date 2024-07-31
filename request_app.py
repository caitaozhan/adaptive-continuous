'''the request app customized for the adaptive continuous protocol
'''

from typing import TYPE_CHECKING
from sequence.app.request_app import RequestApp
import sequence.utils.log as log
from collections import defaultdict
from reservation import ReservationAdaptive

if TYPE_CHECKING:
    from sequence.topology.node import QuantumRouter
    from sequence.network_management.reservation import Reservation
    from sequence.resource_management.memory_manager import MemoryInfo




class RequestAppAdaptive(RequestApp):
    '''adding a feature to record the time-to-serve (latency) data
    '''

    def __init__(self, node: "QuantumRouter"):
        super().__init__(node)
        self.entangled_timestamps = defaultdict(list)
    

    def get_memory(self, info: "MemoryInfo") -> None:
        """Method to receive entangled memories.

        Will check if the received memory is qualified.
        If it's a qualified memory, the application sets memory to RAW state
        and release back to resource manager.
        The counter of entanglement memories, 'memory_counter', is added.
        Otherwise, the application does not modify the state of memory and
        release back to the resource manager.

        Args:
            info (MemoryInfo): info on the qualified entangled memory.
        """

        if info.state != "ENTANGLED":
            return

        if info.index in self.memo_to_reserve:
            reservation = self.memo_to_reserve[info.index]
            if info.remote_node == reservation.initiator and info.fidelity >= reservation.fidelity:   # the responder
                self.node.resource_manager.update(None, info.memory, "RAW")
                self.cache_entangled_path(reservation.path)
            elif info.remote_node == reservation.responder and info.fidelity >= reservation.fidelity: # the initiator
                self.memory_counter += 1
                self.entangled_timestamps[reservation].append(self.node.timeline.now())
                log.logger.info("Successfully generated entanglement. Counter is at {}.".format(self.memory_counter))
                self.node.resource_manager.update(None, info.memory, "RAW")
                self.cache_entangled_path(reservation.path)
                self.send_entangled_path(reservation)


    def get_time_stamps(self) -> list:
        '''get the entangled time stamps (for the "first" reservations)
        '''
        for reservation, entangled_timestamps in self.entangled_timestamps.items():
            return entangled_timestamps   


    def get_time_to_service(self) -> list:
        '''compute the time to service (for the "first" reservations)
        '''
        time_to_sevice = []
        for reservation, entangled_timestamps in self.entangled_timestamps.items():
            assert len(entangled_timestamps) > 0
            time_to_sevice.append(entangled_timestamps[0] - reservation.start_time)
            for i in range(1, len(entangled_timestamps)):
                time_to_sevice.append(entangled_timestamps[i] - entangled_timestamps[i-1])
            break
        return time_to_sevice


    def cache_entangled_path(self, path: list):
        '''save the entanlged path to the AC protocol at this node
        '''
        timestamp = self.node.timeline.now()
        cache = self.node.adaptive_continuous.cache
        cache.append((timestamp, path))
        log.logger.info(f'{self.node.name} added {(timestamp, path)} to cache')


    def send_entangled_path(self, reservation: ReservationAdaptive):
        '''send the entangled path to nodes other than the initiator and responder
        '''
        path = reservation.path
        if len(path) > 2:
            for i in range(1, len(path) - 1):
                node = path[i]
                time = self.node.timeline.now()
                self.node.adaptive_continuous.send_entanglement_path(node, time, reservation)
