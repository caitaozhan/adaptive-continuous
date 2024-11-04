'''memory manager customized for the adaptive continuous protocol
'''

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sequence.resource_management.memory_manager import MemoryArray

from sequence.resource_management.memory_manager import MemoryManager


class MemoryManagerAdaptive(MemoryManager):
    '''Class to manage a node's memories customized for the adaptive continuous protocol

    The memory manager tracks the entanglement state of a node's memories, along with other information (such as fidelity).

    Attributes:
        memory_array (MemoryArray): memory array object to be tracked.
        memory_map (List[MemoryInfo]): array of memory info objects corresponding to memory array.
        resource_manager (ResourceManager): resource manager object using the memory manager.
    '''

    def __init__(self, memory_array: "MemoryArray"):
        """Constructor for memory manager.

        Args:
            memory_array (MemoryArray): memory array to monitor and manage.
        """
        super().__init__(memory_array)
    

    def get_memory_array(self) -> "MemoryArray":
        return self.memory_array
    

    def swap_two_memory(self, memory1_name: str, memory2_name: str):
        """swap two quantum memories

        Args:
            memory1_name: the name of one memory
            memory2_name: the name of the other memory
        """
        i = self.memory_array.memory_name_to_index[memory1_name]
        j = self.memory_array.memory_name_to_index[memory2_name]

        # swap all memory's attributes except the name, memory_array, timeline, observers, and receivers
        self.memory_array[i].fidelity, self.memory_array[j].fidelity                 = self.memory_array[j].fidelity, self.memory_array[i].fidelity
        self.memory_array[i].raw_fidelity, self.memory_array[j].raw_fidelity         = self.memory_array[j].raw_fidelity, self.memory_array[i].raw_fidelity
        self.memory_array[i].frequency, self.memory_array[j].frequency               = self.memory_array[j].frequency, self.memory_array[i].frequency
        self.memory_array[i].efficiency, self.memory_array[j].efficiency             = self.memory_array[j].efficiency, self.memory_array[i].efficiency
        self.memory_array[i].coherence_time, self.memory_array[j].coherence_time     = self.memory_array[j].coherence_time, self.memory_array[i].coherence_time
        self.memory_array[i].wavelength, self.memory_array[j].wavelength             = self.memory_array[j].wavelength, self.memory_array[i].wavelength
        self.memory_array[i].qstate_key, self.memory_array[j].qstate_key             = self.memory_array[j].qstate_key, self.memory_array[i].qstate_key
        self.memory_array[i].encoding, self.memory_array[j].encoding                 = self.memory_array[j].encoding, self.memory_array[i].encoding
        self.memory_array[i].previous_bsm, self.memory_array[j].previous_bsm         = self.memory_array[j].previous_bsm, self.memory_array[i].previous_bsm
        self.memory_array[i].entangled_memory, self.memory_array[j].entangled_memory = self.memory_array[j].entangled_memory, self.memory_array[i].entangled_memory
        self.memory_array[i].expiration_event, self.memory_array[j].expiration_event = self.memory_array[j].expiration_event, self.memory_array[i].expiration_event
        self.memory_array[i].excited_photon, self.memory_array[j].excited_photon     = self.memory_array[j].excited_photon, self.memory_array[i].excited_photon
        self.memory_array[i].next_excite_time, self.memory_array[j].next_excite_time = self.memory_array[j].next_excite_time, self.memory_array[i].next_excite_time
        if 'decoherence_errors' in dir(self.memory_array[i]):   # single heralded
            self.memory_array[i].decoherence_errors, self.memory_array[j].decoherence_errors = self.memory_array[j].decoherence_errors, self.memory_array[i].decoherence_errors
            self.memory_array[i].cutoff_ratio, self.memory_array[j].cutoff_ratio             = self.memory_array[j].cutoff_ratio, self.memory_array[i].cutoff_ratio
            self.memory_array[i].generation_time, self.memory_array[j].generation_time       = self.memory_array[j].generation_time, self.memory_array[i].generation_time
            self.memory_array[i].last_update_time, self.memory_array[j].last_update_time     = self.memory_array[j].last_update_time, self.memory_array[i].last_update_time
            self.memory_array[i].is_in_application, self.memory_array[j].is_in_application   = self.memory_array[j].is_in_application, self.memory_array[i].is_in_application
    
        # swap all memory_info's attributes except the index, and memory (it's attributes are already swapped)
        self.memory_map[i].state, self.memory_map[j].state                 = self.memory_map[j].state, self.memory_map[i].state
        self.memory_map[i].remote_node, self.memory_map[j].remote_node     = self.memory_map[j].remote_node, self.memory_map[i].remote_node
        self.memory_map[i].remote_memo, self.memory_map[j].remote_memo     = self.memory_map[j].remote_memo, self.memory_map[i].remote_memo
        self.memory_map[i].fidelity, self.memory_map[j].fidelity           = self.memory_map[j].fidelity, self.memory_map[i].fidelity
        self.memory_map[i].expire_event, self.memory_map[j].expire_event   = self.memory_map[j].expire_event, self.memory_map[i].expire_event
        self.memory_map[i].entangle_time, self.memory_map[j].entangle_time = self.memory_map[j].entangle_time, self.memory_map[i].entangle_time
    

    def check_entangled_memory(self, entangled_memory_name: str) -> bool:
        '''return True if the memory by parameter entangled_memory_name is indeed entangled, otherwise False

        Args:
            entangled_memory_name (str): the name of the memory
        '''
        i = self.memory_array.memory_name_to_index[entangled_memory_name]
        if self.memory_array[i].entangled_memory['node_id'] is None:
            return False
        else:
            return True