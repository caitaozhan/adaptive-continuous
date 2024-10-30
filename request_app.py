'''the request app customized for the adaptive continuous protocol
'''

import numpy as np
from typing import TYPE_CHECKING
from sequence.app.request_app import RequestApp
import sequence.utils.log as log
from collections import defaultdict
from reservation import ReservationAdaptive
from sequence.constants import SECOND
from sequence.resource_management.memory_manager import MemoryInfo
from sequence.components.memory import Memory

if TYPE_CHECKING:
    from node import QuantumRouterAdaptive
    from sequence.network_management.reservation import Reservation



class RequestAppThroughput(RequestApp):
    '''for the throughput metric

    The RequestApp can only handle one request (for a node) at a time, it cannot handle multiple requests at the same time.
    It can handle multiple requests one by one (no timing overlap between consequtive requests)
    '''

    def __init__(self, node: "QuantumRouterAdaptive"):
        super().__init__(node)
        self.entanglement_timestamps = defaultdict(list)  # reservation -> list[float]
        self.entanglement_fidelities = defaultdict(list)  # reservation -> list[float]

    def start(self, responder: str, start_t: int, end_t: int, memo_size: int, fidelity: float, entanglement_number: int = 1, id: int = 0):
        """Method to start the application.

            This method will use arguments to create a request and send to the network.

        Side Effects:
            Will create request for network manager on node.
        """
        assert 0 < fidelity <= 1
        assert 0 <= start_t <= end_t
        assert 0 < memo_size
        self.responder = responder
        self.start_t = start_t
        self.end_t = end_t
        self.memo_size = memo_size
        self.fidelity = fidelity
        self.entanglement_number = entanglement_number
        self.id = id

        self.node.reserve_net_resource(responder, start_t, end_t, memo_size, fidelity, entanglement_number, id)

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

        if info.index in self.memo_to_reservation:
            reservation = self.memo_to_reservation[info.index]
            if info.remote_node == reservation.initiator:
                if info.fidelity >= reservation.fidelity:   # the responder
                    self.node.resource_manager.update(None, info.memory, "RAW")
                    self.cache_entangled_path(reservation.path)
                    log.logger.info(f"{self.name}: Successfully generated entanglement. {reservation}: {len(self.entanglement_timestamps[reservation])}, {info.fidelity:.6f}")
                else:
                    log.logger.info(f'{self.name}: Successfully generated entanglement. BUT the fidelity={info.fidelity:.6f} does not meet requirement ({reservation.fidelity})')
            elif info.remote_node == reservation.responder:
                if info.fidelity >= reservation.fidelity: # the initiator
                    self.entanglement_timestamps[reservation].append(self.node.timeline.now())
                    self.entanglement_fidelities[reservation].append(info.fidelity)
                    log.logger.info(f"{self.name}: Successfully generated entanglement. {reservation}: {len(self.entanglement_timestamps[reservation])}, {info.fidelity:.6f}")
                    self.node.resource_manager.update(None, info.memory, "RAW")
                    self.cache_entangled_path(reservation.path)
                    self.send_entangled_path(reservation)
                else:
                    log.logger.info(f'{self.name}: Successfully generated entanglement. BUT the fidelity={info.fidelity:.6f} does not meet requirement ({reservation.fidelity})')


    def get_time_stamps(self) -> list:
        '''get the entangled time stamps (for the "first" reservations)
        '''
        for reservation, entangled_timestamps in self.entanglement_timestamps.items():
            return entangled_timestamps   


    def get_time_to_service(self) -> list:
        '''compute the time to service (for the "first" reservation)
        '''
        time_to_sevice = []
        for reservation, entangled_timestamps in self.entanglement_timestamps.items():
            assert len(entangled_timestamps) > 0
            time_to_sevice.append(entangled_timestamps[0] - reservation.start_time)
            for i in range(1, len(entangled_timestamps)):
                time_to_sevice.append(entangled_timestamps[i] - entangled_timestamps[i-1])
            break
        return time_to_sevice
    
    def get_fidelity(self) -> list:
        '''get the entanglement's fidelity (for the "first request)
        '''
        for _, fidelities in self.entanglement_fidelities.items():
            return fidelities

    def cache_entangled_path(self, path: list):
        '''save the entanlged path to the AC protocol at this node
        '''
        timestamp = self.node.timeline.now()
        cache = self.node.adaptive_continuous.cache
        cache.append((timestamp, path))
        log.logger.debug(f'{self.node.name} added {(timestamp, path)} to cache')


    def send_entangled_path(self, reservation: ReservationAdaptive):
        '''send the entangled path to nodes other than the initiator and responder
        '''
        path = reservation.path
        if len(path) > 2:
            for i in range(1, len(path) - 1):
                node = path[i]
                time = self.node.timeline.now()
                self.node.adaptive_continuous.send_entanglement_path(node, time, reservation)

    def get_request_to_throughput(self) -> dict:
        '''each request maps to a reservation
        Return:
            Dict[Reservation, float]
        '''
        request_to_throughput = {}
        for reservation, entanglement_timestamps in self.entanglement_timestamps.items():
            time_elapse = (reservation.end_time - reservation.start_time) / SECOND
            request_to_throughput[reservation] = len(entanglement_timestamps) / time_elapse
        return request_to_throughput


class RequestAppTimeToServe(RequestApp):
    '''for the time-to-serve (latency) metric

    The RequestApp can only handle one request (for a node) at a time, it cannot handle multiple requests at the same time.
    It can handle multiple requests one by one (no timing overlap between consequtive requests)
    '''

    def __init__(self, node: "QuantumRouterAdaptive"):
        super().__init__(node)
        self.entanglement_timestamps = defaultdict(list)  # reservation: list[float]
        self.time_to_serve = defaultdict(float)           # reservation: float
        self.entanglement_fidelities = defaultdict(list)  # reservation: list[float]
    
    def start(self, responder: str, start_t: int, end_t: int, memo_size: int, fidelity: float, entanglement_number: int = 1, id: int = 0):
        """Method to start the application.

            This method will use arguments to create a request and send to the network.

        Side Effects:
            Will create request for network manager on node.
        """
        assert 0 < fidelity <= 1
        assert 0 <= start_t <= end_t
        assert 0 < memo_size
        self.responder = responder
        self.start_t = start_t
        self.end_t = end_t
        self.memo_size = memo_size
        self.fidelity = fidelity
        self.entanglement_number = entanglement_number
        self.id = id

        self.node.reserve_net_resource(responder, start_t, end_t, memo_size, fidelity, entanglement_number, id)

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

        if info.index in self.memo_to_reservation:
            reservation = self.memo_to_reservation[info.index]
            if info.remote_node == reservation.initiator:
                if info.fidelity >= reservation.fidelity:   # the responder
                    self.entanglement_timestamps[reservation].append(self.node.timeline.now())
                    self.entanglement_fidelities[reservation].append(info.fidelity)
                    self.node.resource_manager.update(None, info.memory, MemoryInfo.RAW)
                    self.cache_entangled_path(reservation.path)
                    
                    entanglement_number = len(self.entanglement_timestamps[reservation])
                    if entanglement_number == reservation.entanglement_number:
                        # self.time_to_serve[reservation] = self.node.timeline.now() - reservation.start_time
                        self.node.resource_manager.expire_rules_by_reservation(reservation)
                else:
                    log.logger.info(f'Memory={info}, does not meet the fidelity threshold, {reservation}')

            elif info.remote_node == reservation.responder:
                if info.fidelity >= reservation.fidelity: # the initiator
                    self.entanglement_timestamps[reservation].append(self.node.timeline.now())
                    self.entanglement_fidelities[reservation].append(info.fidelity)
                    entanglement_number = len(self.entanglement_timestamps[reservation])

                    log.logger.info(f"Successfully generated entanglement. {reservation}: {entanglement_number}, {info.fidelity:.6f}")
                    self.node.resource_manager.update(None, info.memory, MemoryInfo.RAW)
                    self.cache_entangled_path(reservation.path)
                    self.send_entangled_path(reservation)

                    if entanglement_number == reservation.entanglement_number:
                        self.time_to_serve[reservation] = self.node.timeline.now() - reservation.start_time
                        self.node.resource_manager.expire_rules_by_reservation(reservation)
                        self.send_expire_rules_message(reservation)
                else:
                    log.logger.info(f'Memory={info} has not meet the threshold, {reservation}')


    def get_time_stamps(self) -> list:
        '''get the entangled time stamps (for the "first" reservations)
        '''
        for reservation, entangled_timestamps in self.entanglement_timestamps.items():
            return entangled_timestamps   


    def get_time_to_service(self) -> list:
        '''compute the time to service (for the "first" reservations)
        '''
        time_to_sevice = []
        for reservation, entangled_timestamps in self.entanglement_timestamps.items():
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
        log.logger.debug(f'{self.node.name} added {(timestamp, path)} to cache')


    def send_entangled_path(self, reservation: ReservationAdaptive):
        '''send the entangled path to nodes other than the initiator and responder

        Args:
            reservation: the path comes from this reservation
        '''
        path = reservation.path
        if len(path) > 2:
            for i in range(1, len(path) - 1):
                node = path[i]
                time = self.node.timeline.now()
                self.node.adaptive_continuous.send_entanglement_path(node, time, reservation)


    def send_expire_rules_message(self, reservation: ReservationAdaptive):
        '''send the expire rule message to nodes other than the initiator and responder

        Args:
            reservation: the rules to expires is generated for this reservation
        '''
        path = reservation.path
        if len(path) > 2:
            for i in range(1, len(path) - 1):
                node = path[i]
                self.node.adaptive_continuous.send_expire_rules_message(node, reservation)


    def get_request_to_throughput(self) -> dict:
        '''each request maps to a reservation
        Return:
            Dict[Reservation, float]
        '''
        request_to_throughput = {}
        for reservation, entanglement_timestamps in self.entanglement_timestamps.items():
            time_elapse = (reservation.end_time - reservation.start_time) / SECOND
            request_to_throughput[reservation] = len(entanglement_timestamps) / time_elapse
        return request_to_throughput
