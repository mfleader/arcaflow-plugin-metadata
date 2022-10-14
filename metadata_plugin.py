#!/usr/bin/env python3

import sys
import typing
from dataclasses import dataclass, field
from arcaflow_plugin_sdk import plugin
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.parsing.dataloader import DataLoader
from ansible.module_utils.common.collections import ImmutableDict
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.vars.manager import VariableManager
from ansible.utils.unsafe_proxy import AnsibleUnsafeText
from ansible import context

@dataclass
class InputParams:
    """
    This is the data structure for the input parameters of the step defined
    below.
    """
    pass


@dataclass
class SuccessOutput:
    """
    This is the output data structure for the success case.
    """
    metadata: typing.Any = field()


@dataclass
class ErrorOutput:
    """
    This is the output data structure in the error  case.
    """

    error: str


@plugin.step(
    id="collect-metadata",
    name="Collect Metadata",
    description="Collects ansible facts metadata",
    outputs={"success": SuccessOutput, "error": ErrorOutput},
)
def collect_metadata(
    params: InputParams,
) -> typing.Tuple[str, typing.Union[SuccessOutput, ErrorOutput]]:
    """The function is the implementation for the step. It needs the decorator
    above to make it into a step. The type hints for the params are required.

    :param params:

    :return: the string identifying which output it is, as well the output
        structure
    """
    host = 'localhost'
    
    context.CLIARGS = ImmutableDict(connection='local',
        #module_path=['/to/mymodules', '/usr/share/ansible'],
        forks=5,
        become=None,
        become_method=None,
        become_user=None,
        check=False,
        diff=False,
        verbosity=0
    )

    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=host + ',')
    variable_manager = VariableManager(loader=loader, inventory=inventory)

    # Must be initialized before play.load()
    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=dict(),
        #stdout_callback=results_callback,  # Use our custom callback instead of the ``default`` callback plugin, which prints to stdout
    )

    play_source = dict(
        name="Metadata Collection",
        hosts=[host],
        gather_facts=True,
        tasks=[],
    )

    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    try:
        result = tqm.run(play)
    finally:
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()
    
    vars = variable_manager.get_vars(play=play, include_hostvars=True)
    host_ansible_facts = vars["hostvars"][host]["ansible_facts"]
    # Convert to dict
    output =  convert_to_supported_type(host_ansible_facts)

    return "success", SuccessOutput(output)

def  convert_to_supported_type(ansible_value):
    type_of_val = type(ansible_value)
    if type_of_val == list:
        new_list = []
        for i in ansible_value:
            new_list.append( convert_to_supported_type(i))
        return new_list
    if type_of_val == dict:
        result = {}
        for k in ansible_value:
            result[ convert_to_supported_type(k)] =  convert_to_supported_type(ansible_value[k])
        return result
    if type_of_val == float or type_of_val == int or type_of_val == str or \
        type_of_val == bool or type_of_val == type(None):
        return ansible_value
    elif type_of_val == AnsibleUnsafeText:
        return str(ansible_value)
    else:
        print("Unknown type", type_of_val, "with val", str(ansible_value))
        return str(ansible_value)


if __name__ == "__main__":
    sys.exit(
        plugin.run(
            plugin.build_schema(
                # List your step functions here:
                collect_metadata,
            )
        )
    )