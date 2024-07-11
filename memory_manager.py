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
    
    
    def swap_two_memory(self, memory1_name: str, memory2_name: str):
        """swap two quantum memories

        Args:
            memory1_name: the name of one memory
            memory2_name: the name of the other memory
        """
        memory1_idx = self.memory_array.memory_name_to_index[memory1_name]
        memory2_idx = self.memory_array.memory_name_to_index[memory2_name]

        print('memory1', self.memory_array[memory1_idx])
        print('memory2', self.memory_array[memory2_idx])

        # swap memory in the memory_array
        self.memory_array[memory1_idx], self.memory_array[memory2_idx] = self.memory_array[memory2_idx], self.memory_array[memory1_idx]
        # swap the name (name is swapped twice, so no change relative to the memory_array)
        self.memory_array[memory1_idx].name, self.memory_array[memory2_idx].name = self.memory_array[memory2_idx].name, self.memory_array[memory1_idx].name
        # swap the memory info
        self.memory_map[memory1_idx], self.memory_map[memory2_idx] = self.memory_map[memory2_idx], self.memory_map[memory1_idx]

        print('memory1', self.memory_array[memory1_idx])
        print('memory2', self.memory_array[memory2_idx])
